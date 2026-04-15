from __future__ import annotations

import asyncio
import time
from dataclasses import asdict

from app.core.data_center_collection.contract_state_poller import ContractStatePoller
from app.core.data_center_collection.market_feed_adapter import MarketFeedAdapter
from app.core.data_center_collection.second_state_assembler import assemble_second_state
from app.core.trend_research.feature_builder import FeatureBarBuilder


DEFAULT_BOOK_CHANNEL = 'books5'
DEFAULT_INTEGRITY_POLICY_VERSION = 'strict_v1'
DEFAULT_STATE_POLL_INTERVAL = 5.0


class CensusObservationRuntime:
    def __init__(
        self,
        *,
        storage,
        inst_id: str,
        snapshot_reader=None,
        fetcher=None,
        ws_manager=None,
        book_channel: str = DEFAULT_BOOK_CHANNEL,
        integrity_policy_version: str = DEFAULT_INTEGRITY_POLICY_VERSION,
        state_poll_interval: float = DEFAULT_STATE_POLL_INTERVAL,
        now_fn=time.time,
        sleep_fn=asyncio.sleep,
    ):
        self._storage = storage
        self._inst_id = inst_id
        self._snapshot_reader = snapshot_reader
        self._now_fn = now_fn
        self._sleep_fn = sleep_fn
        self._book_channel = book_channel
        self._integrity_policy_version = integrity_policy_version
        self._state_poll_interval = float(state_poll_interval)
        self._state_task = None
        self._flush_task = None
        self._builder = None
        self._market_feed = None
        self._state_poller = None
        if snapshot_reader is None:
            self._builder = FeatureBarBuilder(inst_id)
            self._market_feed = MarketFeedAdapter(
                ws_manager=ws_manager,
                inst_id=inst_id,
                book_channel=book_channel,
            )
            self._state_poller = ContractStatePoller(
                fetcher=fetcher,
                inst_id=inst_id,
            )

    async def start(self) -> dict[str, object]:
        if self._snapshot_reader is not None:
            return self.flush_once()
        if self._flush_task is not None and not self._flush_task.done():
            return self.flush_once()
        await self._market_feed.start(on_trade=self._on_trade, on_book=self._on_book)
        try:
            await self._sync_state_once()
            row = self.flush_once()
        except Exception:
            await self._teardown()
            raise
        self._state_task = asyncio.create_task(
            self._state_loop(),
            name=f'census_state_sync:{self._inst_id}',
        )
        self._flush_task = asyncio.create_task(
            self._flush_loop(),
            name=f'census_flush:{self._inst_id}',
        )
        return row

    async def stop(self) -> None:
        await self._teardown()

    def flush_once(self, second_bucket: int | None = None) -> dict[str, object]:
        row = self._read_snapshot(second_bucket=second_bucket)
        row['inst_id'] = self._inst_id
        self._storage.save_research_census_second_state(**row)
        return row

    def _read_snapshot(self, *, second_bucket: int | None) -> dict[str, object]:
        if self._snapshot_reader is not None:
            return dict(self._snapshot_reader())
        return self._build_live_snapshot(second_bucket=second_bucket or self._next_second_bucket())

    def _build_live_snapshot(self, *, second_bucket: int) -> dict[str, object]:
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
        payload['integrity_policy_version'] = self._integrity_policy_version
        return assemble_second_state(payload)

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
            self.flush_once()

    def _on_trade(self, event) -> None:
        self._builder.apply_trade(event)

    def _on_book(self, event) -> None:
        self._builder.apply_book(event)

    def _next_second_bucket(self) -> int:
        return int(self._now_fn())

    async def _teardown(self) -> None:
        tasks = []
        current_task = asyncio.current_task()
        for task in (self._state_task, self._flush_task):
            if task is None or task.done() or task is current_task:
                continue
            task.cancel()
            tasks.append(task)
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        self._state_task = None
        self._flush_task = None
        if self._market_feed is not None:
            await self._market_feed.stop()


def _resolve_age_seconds(now_ts: float, event_ts: float | None) -> float:
    if event_ts is None:
        return 1e9
    return max(now_ts - float(event_ts), 0.0)


def _seconds_until_next_boundary(now_ts: float) -> float:
    fractional = float(now_ts) - int(now_ts)
    if fractional <= 0.0:
        return 1.0
    return max(1.0 - fractional, 0.001)
