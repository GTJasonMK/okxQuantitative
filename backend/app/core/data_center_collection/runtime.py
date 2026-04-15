from __future__ import annotations

import asyncio
import time
from dataclasses import asdict

from app.core.data_center_collection.contract_state_poller import ContractStatePoller
from app.core.data_center_collection.market_feed_adapter import MarketFeedAdapter
from app.core.data_center_collection.runner import DataCollectionRunner
from app.core.data_center_collection.second_state_assembler import assemble_second_state
from app.core.storage_research_platform import SESSION_STATUS_FAILED
from app.core.storage_research_platform import SESSION_STATUS_FINISHED
from app.core.storage_research_platform import SESSION_STATUS_STOPPED
from app.core.trend_research.feature_builder import FeatureBarBuilder


TERMINAL_SESSION_STATES = {
    SESSION_STATUS_FINISHED,
    SESSION_STATUS_FAILED,
    SESSION_STATUS_STOPPED,
}
DEFAULT_STATE_POLL_INTERVAL = 5.0


class CollectionRuntime:
    def __init__(
        self,
        *,
        session,
        storage,
        fetcher,
        ws_manager,
        publish_event,
        after_flush=None,
        state_poll_interval: float = DEFAULT_STATE_POLL_INTERVAL,
        now_fn=time.time,
        sleep_fn=asyncio.sleep,
    ):
        self._session = session
        self._storage = storage
        self._now_fn = now_fn
        self._sleep_fn = sleep_fn
        self._state_poll_interval = float(state_poll_interval)
        self._builder = FeatureBarBuilder(str(session['inst_id']))
        self._market_feed = MarketFeedAdapter(
            ws_manager=ws_manager,
            inst_id=str(session['inst_id']),
            book_channel=str(session['book_channel']),
        )
        self._state_poller = ContractStatePoller(
            fetcher=fetcher,
            inst_id=str(session['inst_id']),
        )
        self._runner = DataCollectionRunner(
            session=session,
            storage=storage,
            next_second_bucket=self._next_second_bucket,
            accumulator=self,
            assembler=assemble_second_state,
            publish_event=publish_event,
            after_flush=after_flush,
        )
        self._state_task = None
        self._flush_task = None
        self._closed = False

    async def start(self) -> dict[str, object]:
        await self._market_feed.start(on_trade=self._on_trade, on_book=self._on_book)
        try:
            await self._sync_state_once()
            session = await self._runner.start()
        except Exception:
            await self._teardown()
            raise
        if session['status'] in TERMINAL_SESSION_STATES:
            await self._teardown()
            return session
        self._state_task = asyncio.create_task(
            self._state_loop(),
            name=f"collection_state_sync:{self._session['session_id']}",
        )
        self._flush_task = asyncio.create_task(
            self._flush_loop(),
            name=f"collection_flush:{self._session['session_id']}",
        )
        return session

    async def stop(self, *, stop_reason: str) -> dict[str, object]:
        await self._teardown()
        return await self._runner.stop(stop_reason=stop_reason)

    def _on_trade(self, event) -> None:
        self._builder.apply_trade(event)

    def _on_book(self, event) -> None:
        self._builder.apply_book(event)

    def flush(self, second_bucket: int) -> dict[str, object]:
        now_ts = float(self._now_fn())
        runtime_snapshot = self._builder.build_runtime_snapshot()
        bar = self._builder.flush(second_bucket)
        payload = asdict(bar)
        payload['has_trade_input'] = int(runtime_snapshot.has_trade_input)
        payload['has_book_input'] = int(runtime_snapshot.has_book_input)
        payload['has_state_input'] = int(runtime_snapshot.has_contract_state)
        payload['book_age_seconds'] = _resolve_age_seconds(now_ts, runtime_snapshot.last_book_ts_local)
        payload['state_age_seconds'] = _resolve_age_seconds(now_ts, runtime_snapshot.last_state_ts_local)
        payload['clock_skew_ms'] = abs(now_ts - float(second_bucket)) * 1000.0
        payload['integrity_policy_version'] = str(self._session['integrity_policy_version'])
        return payload

    async def _sync_state_once(self) -> None:
        snapshot = await asyncio.to_thread(self._state_poller.read_snapshot)
        self._builder.apply_contract_state(snapshot)

    async def _state_loop(self) -> None:
        while True:
            await self._sleep_fn(self._state_poll_interval)
            await self._sync_state_once()

    async def _flush_loop(self) -> None:
        while True:
            await self._sleep_fn(_seconds_until_next_boundary(self._now_fn()))
            session = await self._runner.flush_once()
            if session['status'] in TERMINAL_SESSION_STATES:
                await self._teardown()
                return

    def _next_second_bucket(self) -> int:
        return int(self._now_fn())

    async def _teardown(self) -> None:
        if self._closed:
            return
        self._closed = True
        current_task = asyncio.current_task()
        tasks = []
        for task in (self._state_task, self._flush_task):
            if task is None or task.done() or task is current_task:
                continue
            task.cancel()
            tasks.append(task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._state_task = None
        self._flush_task = None
        await self._market_feed.stop()


def build_collection_runtime(
    *,
    storage,
    session,
    fetcher,
    ws_manager,
    publish_event,
    after_flush=None,
    state_poll_interval: float = DEFAULT_STATE_POLL_INTERVAL,
):
    return CollectionRuntime(
        session=session,
        storage=storage,
        fetcher=fetcher,
        ws_manager=ws_manager,
        publish_event=publish_event,
        after_flush=after_flush,
        state_poll_interval=state_poll_interval,
    )


def _resolve_age_seconds(now_ts: float, event_ts: float | None) -> float:
    if event_ts is None:
        return 1e9
    return max(now_ts - float(event_ts), 0.0)


def _seconds_until_next_boundary(now_ts: float) -> float:
    fractional = float(now_ts) - int(now_ts)
    if fractional <= 0.0:
        return 1.0
    return max(1.0 - fractional, 0.001)
