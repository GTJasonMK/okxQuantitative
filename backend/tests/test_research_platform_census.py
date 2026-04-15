from __future__ import annotations

import asyncio
import json
import math
from pathlib import Path

import pytest

from app.core.data_storage import DataStorage
from app.core.research_platform.census.runtime import CensusObservationRuntime
from app.core.research_platform.census.service import ResearchCensusService
from app.core.research_platform.census.service import build_compact_boundary_state_v1
from app.core.research_platform.census.service import build_target_census_row


class _FakeObservationReader:
    def __init__(self, rows: list[dict[str, object]]):
        self.rows = list(rows)
        self.calls: list[tuple[str, int, int]] = []

    def list_for_inst(self, inst_id: str, end_ts: int, lookback_sec: int) -> list[dict[str, object]]:
        self.calls.append((inst_id, end_ts, lookback_sec))
        return list(self.rows)


class _FakeSessionActivityProvider:
    def __init__(self, active: bool):
        self.active = active
        self.calls: list[tuple[str, int]] = []

    def is_active(self, inst_id: str, decision_ts: int) -> bool:
        self.calls.append((inst_id, decision_ts))
        return self.active


@pytest.fixture
def storage(tmp_path: Path):
    instance = DataStorage(tmp_path / 'research_census.db')
    yield instance
    connection = getattr(instance, '_local', None)
    if connection is not None and getattr(connection, 'connection', None) is not None:
        connection.connection.close()
        connection.connection = None


@pytest.fixture
def census_service(storage):
    reader = _FakeObservationReader(_build_window_rows())
    activity = _FakeSessionActivityProvider(active=True)
    return ResearchCensusService(
        storage=storage,
        observation_reader=reader,
        session_activity_provider=activity,
    )


def _save_second_state(storage, second_bucket: int):
    storage.save_research_second_state(
        session_id='sess-1',
        inst_id='BTC-USDT-SWAP',
        second_bucket=second_bucket,
        ts_exchange=float(second_bucket),
        ts_local=float(second_bucket) + 0.2,
        bid_price=65000.0,
        ask_price=65000.5,
        bid_size=12.0,
        ask_size=10.0,
        bid_depth_10bps=40.0,
        ask_depth_10bps=20.0,
        mid_price=65000.25,
        microprice=65000.23,
        open_price=64999.0,
        high_price=65001.0,
        low_price=64998.5,
        close_price=65000.2,
        mark_price=65000.1,
        index_price=65000.0,
        trade_count=18,
        signed_trade_notional=230000.0,
        buy_notional=150000.0,
        sell_notional=80000.0,
        buy_count=10,
        sell_count=8,
        max_trade_notional=45000.0,
        buy_burst_count=2,
        sell_burst_count=1,
        buy_burst_notional=56000.0,
        sell_burst_notional=18000.0,
        open_interest=3200000.0,
        oi_delta=1200.0,
        funding_rate=0.0001,
        funding_delta=0.0,
        premium=1.5,
        basis_bps=2.1,
        spread_bps=0.08,
        book_level_count=5,
        multi_level_book_imbalance=0.11,
        book_slope=0.03,
        has_trade_input=1,
        has_book_input=1,
        has_state_input=1,
        book_age_seconds=0.0,
        state_age_seconds=0.0,
        clock_skew_ms=12.0,
        is_valid_second=1,
        quality_grade='A',
        invalid_reason='',
        integrity_policy_version='strict_v1',
    )


def test_census_service_writes_strict_target_census(storage, census_service):
    asyncio.run(census_service.run_once(inst_id='BTC-USDT-SWAP', decision_ts=1713000900))

    row = storage.get_research_target_census('BTC-USDT-SWAP', 1713000900)
    shift_state = json.loads(row['shift_state_blob_json'])

    assert row['deployment_eligible'] in {0, 1}
    assert row['census_policy_version'] == 'deployment_eligible_boundary_census_v1'
    assert row['shift_state_definition_version'] == 'compact_boundary_state_v1'
    assert sorted(shift_state.keys()) == sorted(
        [
            'book_stale_ratio_60s',
            'depth_10bps_log',
            'funding_countdown_min',
            'imbalance_10bps',
            'near_funding_flag',
            'range_15m_bps',
            'range_2h_bps',
            'ret_15m_bps',
            'ret_2h_bps',
            'rv_15m_bps',
            'rv_2h_bps',
            'session_active_flag',
            'slot_15m',
            'source_health_flag',
            'spread_last_bps',
            'spread_median_60s_bps',
            'state_stale_ratio_60s',
            'trade_count_60s',
            'trade_notional_60s_log',
            'weekend_flag',
        ]
    )
    assert shift_state['depth_10bps_log'] == pytest.approx(math.log(61.0))
    assert shift_state['imbalance_10bps'] == pytest.approx((40.0 - 20.0) / 60.0)
    assert shift_state['source_health_flag'] == 1


def test_census_service_reads_independent_observation_and_provider(storage):
    reader = _FakeObservationReader([])
    activity = _FakeSessionActivityProvider(active=True)
    service = ResearchCensusService(
        storage=storage,
        observation_reader=reader,
        session_activity_provider=activity,
    )
    _save_second_state(storage, 1713000899)

    asyncio.run(service.run_once(inst_id='BTC-USDT-SWAP', decision_ts=1713000900))

    row = storage.get_research_target_census('BTC-USDT-SWAP', 1713000900)
    shift_state = json.loads(row['shift_state_blob_json'])

    assert reader.calls == [('BTC-USDT-SWAP', 1713000900, 7200)]
    assert activity.calls == [('BTC-USDT-SWAP', 1713000900)]
    assert shift_state['source_health_flag'] == 0
    assert shift_state['session_active_flag'] == 1
    assert row['session_active_flag'] == 1
    assert row['observation_source_kind'] == 'independent_census_runtime_v1'


def test_census_observation_runtime_writes_independent_second_states(storage):
    runtime = CensusObservationRuntime(
        storage=storage,
        inst_id='BTC-USDT-SWAP',
        snapshot_reader=lambda: _build_runtime_snapshot_row(second_bucket=1713000899),
    )

    runtime.flush_once()

    rows = storage.list_research_census_second_states_for_inst(
        'BTC-USDT-SWAP',
        end_ts=1713000900,
        lookback_sec=5,
    )

    assert len(rows) == 1
    assert rows[0]['inst_id'] == 'BTC-USDT-SWAP'
    assert storage.list_research_second_states('sess-1', limit=10) == []


def test_compact_boundary_state_marks_source_unhealthy_when_any_recent_second_is_stale():
    rows = _build_window_rows()
    rows[-1]['book_age_seconds'] = 2.5

    shift_state = build_compact_boundary_state_v1(
        rows=rows,
        decision_ts=1713000900,
        session_active_flag=False,
    )

    assert shift_state['book_stale_ratio_60s'] > 0.0
    assert shift_state['source_health_flag'] == 0


def test_compact_boundary_state_uses_injected_session_active_flag():
    shift_state = build_compact_boundary_state_v1(
        rows=[],
        decision_ts=1713000900,
        session_active_flag=True,
    )

    assert shift_state['session_active_flag'] == 1


def test_compact_boundary_state_uses_total_trade_notional_without_side_cancellation():
    row = dict(_build_window_rows()[0])
    row['buy_notional'] = 10.0
    row['sell_notional'] = 12.0
    row['signed_trade_notional'] = -2.0

    shift_state = build_compact_boundary_state_v1(
        rows=[row],
        decision_ts=int(row['second_bucket']) + 1,
        session_active_flag=True,
    )

    assert shift_state['trade_notional_60s_log'] == pytest.approx(math.log1p(22.0))


def test_build_target_census_row_keeps_deployment_eligibility_independent_from_session_flag():
    row = build_target_census_row(
        inst_id='BTC-USDT-SWAP',
        decision_ts=1713000900,
        shift_state={
            'slot_15m': 0,
            'weekend_flag': 0,
            'ret_15m_bps': 0.0,
            'ret_2h_bps': 0.0,
            'rv_15m_bps': 0.0,
            'rv_2h_bps': 80.0,
            'range_15m_bps': 0.0,
            'range_2h_bps': 0.0,
            'spread_last_bps': 0.08,
            'spread_median_60s_bps': 0.08,
            'depth_10bps_log': math.log(61.0),
            'imbalance_10bps': 0.0,
            'trade_count_60s': 0,
            'trade_notional_60s_log': 0.0,
            'funding_countdown_min': 300,
            'near_funding_flag': 0,
            'book_stale_ratio_60s': 0.0,
            'state_stale_ratio_60s': 0.0,
            'source_health_flag': 1,
            'session_active_flag': 0,
            '_window_2h_complete': True,
            '_window_15m_complete': True,
            '_window_invalid_reason': '',
        },
    )

    assert row['deployment_eligible'] == 1
    assert row['invalid_reason'] == ''


def _build_window_rows() -> list[dict[str, object]]:
    rows = []
    for second_bucket in range(1713000840, 1713000900):
        rows.append(
            {
                'second_bucket': second_bucket,
                'close_price': 65000.2,
                'high_price': 65001.0,
                'low_price': 64998.5,
                'spread_bps': 0.08,
                'bid_size': 12.0,
                'ask_size': 10.0,
                'bid_depth_10bps': 40.0,
                'ask_depth_10bps': 20.0,
                'multi_level_book_imbalance': 0.11,
                'trade_count': 18,
                'signed_trade_notional': 230000.0,
                'book_age_seconds': 0.0,
                'state_age_seconds': 0.0,
                'is_valid_second': 1,
                'integrity_policy_version': 'strict_v1',
            }
        )
    return rows


def _build_runtime_snapshot_row(*, second_bucket: int) -> dict[str, object]:
    return {
        'second_bucket': second_bucket,
        'ts_exchange': float(second_bucket),
        'ts_local': float(second_bucket) + 0.2,
        'bid_price': 65000.0,
        'ask_price': 65000.5,
        'bid_size': 12.0,
        'ask_size': 10.0,
        'bid_depth_10bps': 40.0,
        'ask_depth_10bps': 20.0,
        'mid_price': 65000.25,
        'microprice': 65000.23,
        'open_price': 64999.0,
        'high_price': 65001.0,
        'low_price': 64998.5,
        'close_price': 65000.2,
        'mark_price': 65000.1,
        'index_price': 65000.0,
        'trade_count': 18,
        'signed_trade_notional': 230000.0,
        'buy_notional': 150000.0,
        'sell_notional': 80000.0,
        'buy_count': 10,
        'sell_count': 8,
        'max_trade_notional': 45000.0,
        'buy_burst_count': 2,
        'sell_burst_count': 1,
        'buy_burst_notional': 56000.0,
        'sell_burst_notional': 18000.0,
        'open_interest': 3200000.0,
        'oi_delta': 1200.0,
        'funding_rate': 0.0001,
        'funding_delta': 0.0,
        'premium': 1.5,
        'basis_bps': 2.1,
        'spread_bps': 0.08,
        'book_level_count': 5,
        'multi_level_book_imbalance': 0.11,
        'book_slope': 0.03,
        'has_trade_input': 1,
        'has_book_input': 1,
        'has_state_input': 1,
        'book_age_seconds': 0.0,
        'state_age_seconds': 0.0,
        'clock_skew_ms': 12.0,
        'is_valid_second': 1,
        'quality_grade': 'A',
        'invalid_reason': '',
        'integrity_policy_version': 'strict_v1',
    }
