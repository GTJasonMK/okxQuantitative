from __future__ import annotations

import asyncio

from app.core.research_platform.census.scheduler import TargetCensusScheduler


class _FakeCensusService:
    def __init__(self):
        self.calls: list[tuple[str, int]] = []
        self.last_decision_ts = None

    async def run_once(self, *, inst_id: str, decision_ts: int) -> dict[str, object]:
        self.calls.append((inst_id, decision_ts))
        self.last_decision_ts = int(decision_ts)
        return {'inst_id': inst_id, 'decision_ts': decision_ts}


def test_scheduler_runs_each_boundary_once_for_known_instruments():
    now = {'value': 1801.2}
    census = _FakeCensusService()
    scheduler = TargetCensusScheduler(
        census_service=census,
        inst_id_provider=lambda: ['BTC-USDT-SWAP', 'BTC-USDT-SWAP', 'ETH-USDT-SWAP'],
        now_fn=lambda: now['value'],
    )

    first = asyncio.run(scheduler.run_due_once())
    second = asyncio.run(scheduler.run_due_once())
    now['value'] = 2701.2
    third = asyncio.run(scheduler.run_due_once())

    assert [(row['inst_id'], row['decision_ts']) for row in first] == [
        ('BTC-USDT-SWAP', 1800),
        ('ETH-USDT-SWAP', 1800),
    ]
    assert second == []
    assert [(row['inst_id'], row['decision_ts']) for row in third] == [
        ('BTC-USDT-SWAP', 2700),
        ('ETH-USDT-SWAP', 2700),
    ]
    assert census.calls == [
        ('BTC-USDT-SWAP', 1800),
        ('ETH-USDT-SWAP', 1800),
        ('BTC-USDT-SWAP', 2700),
        ('ETH-USDT-SWAP', 2700),
    ]


def test_scheduler_skips_when_no_instrument_is_known():
    scheduler = TargetCensusScheduler(
        census_service=_FakeCensusService(),
        inst_id_provider=lambda: [],
        now_fn=lambda: 1801.2,
    )

    result = asyncio.run(scheduler.run_due_once())

    assert result == []


def test_scheduler_reports_normalized_universe_count():
    scheduler = TargetCensusScheduler(
        census_service=_FakeCensusService(),
        inst_id_provider=lambda: ['BTC-USDT-SWAP', '', 'BTC-USDT-SWAP', 'ETH-USDT-SWAP'],
        now_fn=lambda: 1801.2,
    )

    assert scheduler.universe_count == 2
