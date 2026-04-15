from __future__ import annotations

import asyncio

from app.core.research_platform.census.orchestrator import CensusOrchestrator


class _FakeScheduler:
    def __init__(self):
        self.enabled = True
        self.last_decision_ts = None
        self.universe_count = 0
        self.start_calls = 0
        self.stop_calls = 0

    async def start(self):
        self.start_calls += 1

    async def stop(self):
        self.stop_calls += 1


class _FakeUniverseProvider:
    def list_inst_ids(self):
        return ['BTC-USDT-SWAP', '', 'BTC-USDT-SWAP', 'ETH-USDT-SWAP']


class _FakeRuntime:
    def __init__(self, inst_id: str, log: list[tuple[str, str]]):
        self._inst_id = inst_id
        self._log = log

    async def start(self):
        self._log.append(('start', self._inst_id))

    async def stop(self):
        self._log.append(('stop', self._inst_id))


def test_census_orchestrator_starts_and_stops_runtime_per_universe_member():
    scheduler = _FakeScheduler()
    events: list[tuple[str, str]] = []
    orchestrator = CensusOrchestrator(
        scheduler=scheduler,
        universe_provider=_FakeUniverseProvider(),
        runtime_factory=lambda inst_id: _FakeRuntime(inst_id, events),
    )

    asyncio.run(orchestrator.start())
    asyncio.run(orchestrator.stop())

    assert scheduler.start_calls == 1
    assert scheduler.stop_calls == 1
    assert orchestrator.universe_count == 2
    assert events == [
        ('start', 'BTC-USDT-SWAP'),
        ('start', 'ETH-USDT-SWAP'),
        ('stop', 'BTC-USDT-SWAP'),
        ('stop', 'ETH-USDT-SWAP'),
    ]
