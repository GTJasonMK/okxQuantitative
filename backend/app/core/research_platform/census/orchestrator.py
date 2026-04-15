from __future__ import annotations

from .constants import normalize_inst_ids as _normalize_inst_ids


class CensusOrchestrator:
    def __init__(self, *, scheduler, universe_provider, runtime_factory):
        self._scheduler = scheduler
        self._universe_provider = universe_provider
        self._runtime_factory = runtime_factory
        self._runtimes: dict[str, object] = {}

    @property
    def enabled(self) -> bool:
        return bool(self._scheduler.enabled)

    @property
    def last_decision_ts(self) -> int | None:
        return self._scheduler.last_decision_ts

    @property
    def universe_count(self) -> int:
        return len(_normalize_inst_ids(self._universe_provider.list_inst_ids()))

    async def start(self) -> None:
        inst_ids = _normalize_inst_ids(self._universe_provider.list_inst_ids())
        await self._start_missing_runtimes(inst_ids)
        await self._scheduler.start()

    async def stop(self) -> None:
        await self._scheduler.stop()
        await self._stop_all_runtimes()

    async def _start_missing_runtimes(self, inst_ids: list[str]) -> None:
        for inst_id in inst_ids:
            if inst_id in self._runtimes:
                continue
            runtime = self._runtime_factory(inst_id)
            self._runtimes[inst_id] = runtime
            await runtime.start()

    async def _stop_all_runtimes(self) -> None:
        runtimes = list(self._runtimes.items())
        self._runtimes.clear()
        for _, runtime in runtimes:
            await runtime.stop()
