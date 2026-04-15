from __future__ import annotations

import asyncio
import time

from ..dataset.constants import LABEL_WINDOW_SECONDS_15M


BOUNDARY_OBSERVATION_LAG_SECONDS = 1
MIN_POLL_SECONDS = 0.1


class TargetCensusScheduler:
    def __init__(
        self,
        *,
        census_service,
        inst_id_provider,
        now_fn=time.time,
        sleep_fn=asyncio.sleep,
    ):
        self._census_service = census_service
        self._inst_id_provider = inst_id_provider
        self._now_fn = now_fn
        self._sleep_fn = sleep_fn
        self._task = None
        self._last_scheduled_decision_ts: int | None = None
        self.enabled = True

    @property
    def last_decision_ts(self) -> int | None:
        return self._census_service.last_decision_ts

    @property
    def universe_count(self) -> int:
        return len(_normalize_inst_ids(self._inst_id_provider()))

    async def start(self) -> None:
        if not self.enabled:
            return
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(
            self._run_loop(),
            name='research_target_census_scheduler',
        )

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        await asyncio.gather(self._task, return_exceptions=True)
        self._task = None

    async def run_due_once(self) -> list[dict[str, object]]:
        if not self.enabled:
            return []
        decision_ts = _resolve_latest_closed_boundary(self._now_fn())
        if decision_ts is None or decision_ts == self._last_scheduled_decision_ts:
            return []
        inst_ids = _normalize_inst_ids(self._inst_id_provider())
        if not inst_ids:
            return []
        results = []
        for inst_id in inst_ids:
            results.append(
                await self._census_service.run_once(
                    inst_id=inst_id,
                    decision_ts=decision_ts,
                )
            )
        self._last_scheduled_decision_ts = int(decision_ts)
        return results

    async def _run_loop(self) -> None:
        while True:
            await self.run_due_once()
            await self._sleep_fn(_seconds_until_next_due(self._now_fn()))


def _resolve_latest_closed_boundary(now_ts: float) -> int | None:
    observed_ts = int(now_ts) - BOUNDARY_OBSERVATION_LAG_SECONDS
    if observed_ts < 0:
        return None
    return (observed_ts // LABEL_WINDOW_SECONDS_15M) * LABEL_WINDOW_SECONDS_15M


def _seconds_until_next_due(now_ts: float) -> float:
    observed_ts = int(now_ts) - BOUNDARY_OBSERVATION_LAG_SECONDS
    next_boundary = ((max(observed_ts, 0) // LABEL_WINDOW_SECONDS_15M) + 1) * LABEL_WINDOW_SECONDS_15M
    next_due_ts = next_boundary + BOUNDARY_OBSERVATION_LAG_SECONDS
    return max(next_due_ts - float(now_ts), MIN_POLL_SECONDS)


def _normalize_inst_ids(inst_ids) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for inst_id in inst_ids or []:
        value = str(inst_id or '').strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized
