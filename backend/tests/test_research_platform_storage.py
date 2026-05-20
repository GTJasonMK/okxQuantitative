from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.data_storage import DataStorage


@pytest.fixture
def storage(tmp_path: Path):
    db_path = tmp_path / 'research_platform.db'
    instance = DataStorage(db_path)
    yield instance
    connection = getattr(instance, '_local', None)
    if connection is not None and getattr(connection, 'connection', None) is not None:
        connection.connection.close()
        connection.connection = None


def test_storage_initializes_research_platform_tables(storage):
    table_names = set(storage.list_table_names())
    assert 'research_collection_sessions' in table_names
    assert 'research_second_states' in table_names
    assert 'research_census_second_states' in table_names
    assert 'research_target_census_15m' in table_names


def test_storage_round_trips_collection_session(storage):
    session_id = storage.create_research_collection_session(
        inst_id='BTC-USDT-SWAP',
        planned_duration_sec=3600,
        trigger_mode='manual',
        trigger_note='operator-started',
        sampling_policy_id='manual_session_v1',
        integrity_policy_version='strict_v1',
        collector_version='research_collector_v1',
        source_config_hash='cfg-1',
        feature_recipe_version='second_state_causal_tensor_v1',
        book_channel='books5',
    )

    row = storage.get_research_collection_session(session_id)

    assert row['inst_id'] == 'BTC-USDT-SWAP'
    assert row['status'] == 'starting'
    assert row['stop_reason'] == ''
    assert row['last_error_code'] == ''
    assert row['last_error_message'] == ''
    assert row['failed_at'] is None
    assert row['trigger_note'] == 'operator-started'
    assert row['sampling_policy_id'] == 'manual_session_v1'
    assert row['collector_version'] == 'research_collector_v1'


def test_storage_round_trips_second_state_and_census(storage):
    storage.save_research_second_state(**_build_second_state_row(session_id='sess-1'))
    storage.save_research_target_census(
        census_id='census-1',
        inst_id='BTC-USDT-SWAP',
        decision_ts=1713000900,
        deployment_eligible=1,
        census_policy_version='deployment_eligible_boundary_census_v1',
        shift_state_definition_version='compact_boundary_state_v1',
        shift_state_blob_json=json.dumps(
            {
                'slot_15m': 32,
                'weekend_flag': 0,
                'ret_15m_bps': 18.0,
                'ret_2h_bps': 44.0,
                'rv_15m_bps': 31.0,
                'rv_2h_bps': 85.0,
                'range_15m_bps': 47.0,
                'range_2h_bps': 126.0,
                'spread_last_bps': 0.08,
                'spread_median_60s_bps': 0.09,
                'depth_10bps_log': 7.4,
                'imbalance_10bps': 0.11,
                'trade_count_60s': 850,
                'trade_notional_60s_log': 14.2,
                'funding_countdown_min': 110,
                'near_funding_flag': 0,
                'book_stale_ratio_60s': 0.0,
                'state_stale_ratio_60s': 0.0,
                'source_health_flag': 1,
                'session_active_flag': 1,
            }
        ),
        hour_of_day=8,
        day_of_week=6,
        realized_vol_proxy_2h=85.0,
        spread_snapshot_bps=0.08,
        liquidity_snapshot_bin=2,
        funding_regime='neutral',
        session_active_flag=1,
        source_health_flag=1,
        invalid_reason='',
        observation_source_kind='independent_census_runtime_v1',
    )

    second_row = storage.list_research_second_states('sess-1', limit=1)[0]
    census_row = storage.get_research_target_census('BTC-USDT-SWAP', 1713000900)
    shift_state = json.loads(census_row['shift_state_blob_json'])

    assert second_row['integrity_policy_version'] == 'strict_v1'
    assert census_row['shift_state_definition_version'] == 'compact_boundary_state_v1'
    assert census_row['census_policy_version'] == 'deployment_eligible_boundary_census_v1'
    assert census_row['observation_source_kind'] == 'independent_census_runtime_v1'
    assert shift_state['depth_10bps_log'] == 7.4
    assert shift_state['session_active_flag'] == 1


def test_storage_round_trips_independent_census_second_state(storage):
    storage.save_research_census_second_state(**_build_second_state_row(session_id='ignored-session'))

    rows = storage.list_research_census_second_states_for_inst(
        'BTC-USDT-SWAP',
        end_ts=1713000900,
        lookback_sec=60,
    )

    assert len(rows) == 1
    assert rows[0]['inst_id'] == 'BTC-USDT-SWAP'
    assert rows[0]['second_bucket'] == 1713000899
    assert storage.list_research_census_inst_ids() == ['BTC-USDT-SWAP']


def test_storage_round_trips_target_census_observation_source_kind(storage):
    storage.save_research_target_census(
        census_id='census-1',
        inst_id='BTC-USDT-SWAP',
        decision_ts=1713000900,
        deployment_eligible=1,
        census_policy_version='deployment_eligible_boundary_census_v1',
        shift_state_definition_version='compact_boundary_state_v1',
        shift_state_blob_json='{}',
        hour_of_day=8,
        day_of_week=1,
        realized_vol_proxy_2h=80.0,
        spread_snapshot_bps=0.08,
        liquidity_snapshot_bin=2,
        funding_regime='neutral',
        session_active_flag=0,
        source_health_flag=1,
        invalid_reason='',
        observation_source_kind='independent_census_runtime_v1',
    )

    row = storage.get_research_target_census('BTC-USDT-SWAP', 1713000900)

    assert row['observation_source_kind'] == 'independent_census_runtime_v1'


def test_storage_target_census_schema_defaults_to_independent_runtime(storage):
    with storage._get_cursor() as cursor:
        cursor.execute("PRAGMA table_info(research_target_census_15m)")
        columns = {
            row['name']: row['dflt_value']
            for row in cursor.fetchall()
        }

    assert columns['observation_source_kind'] == "'independent_census_runtime_v1'"


def test_storage_round_trips_research_artifacts(storage):
    storage.save_research_artifact(
        artifact_ref='artifact://dataset/dataset-1/strata-fit-by-origin.json',
        artifact_kind='dataset_strata_fit',
        payload={'fit_cutpoints': {'rv_2h_bps': [1.0, 2.0]}},
    )

    row = storage.get_research_artifact('artifact://dataset/dataset-1/strata-fit-by-origin.json')

    assert row is not None
    assert row['artifact_kind'] == 'dataset_strata_fit'
    assert json.loads(row['artifact_json']) == {'fit_cutpoints': {'rv_2h_bps': [1.0, 2.0]}}


def _build_second_state_row(*, session_id: str) -> dict[str, object]:
    return {
        'session_id': session_id,
        'inst_id': 'BTC-USDT-SWAP',
        'second_bucket': 1713000899,
        'ts_exchange': 1713000899.0,
        'ts_local': 1713000899.2,
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
