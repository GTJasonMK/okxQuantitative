from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.core.data_center_collection.runner import DataCollectionRunner
from app.core.data_storage import DataStorage


@pytest.fixture
def storage(tmp_path: Path):
    instance = DataStorage(tmp_path / 'collection_runner.db')
    yield instance
    connection = getattr(instance, '_local', None)
    if connection is not None and getattr(connection, 'connection', None) is not None:
        connection.connection.close()
        connection.connection = None


def valid_snapshot(second_bucket: int):
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
        'open_price': 65000.25,
        'high_price': 65000.25,
        'low_price': 65000.25,
        'close_price': 65000.25,
        'mark_price': 65000.1,
        'index_price': 65000.0,
        'trade_count': 1,
        'signed_trade_notional': 0.0,
        'buy_notional': 0.0,
        'sell_notional': 0.0,
        'buy_count': 0,
        'sell_count': 0,
        'max_trade_notional': 0.0,
        'buy_burst_count': 0,
        'sell_burst_count': 0,
        'buy_burst_notional': 0.0,
        'sell_burst_notional': 0.0,
        'open_interest': 3200000.0,
        'oi_delta': 0.0,
        'funding_rate': 0.0001,
        'funding_delta': 0.0,
        'premium': 1.5,
        'basis_bps': 0.0,
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


class _FakeAccumulator:
    def __init__(self, snapshots):
        self._snapshots = list(snapshots)

    def flush(self, second_bucket):
        return self._snapshots.pop(0) if self._snapshots else {'second_bucket': second_bucket}


def _fail_assembler(row):
    raise RuntimeError('boom')


def _create_session(storage, *, planned_duration_sec):
    session_id = storage.create_research_collection_session(
        inst_id='BTC-USDT-SWAP',
        planned_duration_sec=planned_duration_sec,
        trigger_mode='manual',
        trigger_note='',
        sampling_policy_id='manual_session_v1',
        integrity_policy_version='strict_v1',
        collector_version='research_collector_v1',
        source_config_hash='manual',
        feature_recipe_version='second_state_causal_tensor_v1',
        book_channel='books5',
    )
    return storage.get_research_collection_session(session_id)


def build_runner(*, storage, events, snapshots=None, fail_on_flush=False, planned_duration_sec=3):
    session = _create_session(storage, planned_duration_sec=planned_duration_sec)
    return DataCollectionRunner(
        session=session,
        storage=storage,
        next_second_bucket=lambda: 1713000000,
        accumulator=_FakeAccumulator(snapshots or []),
        assembler=_fail_assembler if fail_on_flush else (lambda row: {'session_id': session['session_id'], 'inst_id': 'BTC-USDT-SWAP', **row}),
        publish_event=events.append,
    )


def test_runner_promotes_session_to_running_after_first_flush(storage):
    events = []
    runner = build_runner(storage=storage, events=events, snapshots=[valid_snapshot(1713000000)])

    session = asyncio.run(runner.start())

    assert session['status'] == 'running'
    rows = storage.list_research_second_states(session['session_id'], limit=10)
    assert rows[0]['second_bucket'] == 1713000000
    assert [event['event'] for event in events] == [
        'session_started',
        'second_flushed',
        'session_quality_updated',
        'session_running',
    ]


def test_runner_marks_finished_when_written_seconds_reach_plan(storage):
    events = []
    runner = build_runner(
        storage=storage,
        events=events,
        snapshots=[valid_snapshot(1713000000)],
        planned_duration_sec=1,
    )

    session = asyncio.run(runner.start())

    assert session['status'] == 'finished'
    assert session['stop_reason'] == 'planned_finish'
    assert events[-1]['event'] == 'session_finished'


def test_runner_marks_failed_when_flush_raises(storage):
    events = []
    runner = build_runner(storage=storage, events=events, fail_on_flush=True)

    session = asyncio.run(runner.start())

    assert session['status'] == 'failed'
    assert session['last_error_code'] == 'flush_failed'
    assert events[-1]['event'] == 'session_failed'


def test_runner_stop_transitions_session_to_stopped(storage):
    events = []
    runner = build_runner(storage=storage, events=events, snapshots=[valid_snapshot(1713000000)])
    asyncio.run(runner.start())

    session = asyncio.run(runner.stop(stop_reason='manual_stop'))

    assert session['status'] == 'stopped'
    assert session['stop_reason'] == 'manual_stop'
    assert events[-1]['event'] == 'session_stopped'


def test_runner_uses_clock_bucket_not_session_started_at(storage):
    events = []
    session = _create_session(storage, planned_duration_sec=3)
    runner = DataCollectionRunner(
        session=session,
        storage=storage,
        next_second_bucket=lambda: 1713000123,
        accumulator=_FakeAccumulator([valid_snapshot(1713000123)]),
        assembler=lambda row: {'session_id': session['session_id'], 'inst_id': 'BTC-USDT-SWAP', **row},
        publish_event=events.append,
    )

    session = asyncio.run(runner.start())
    rows = storage.list_research_second_states(session['session_id'], limit=1)

    assert rows[0]['second_bucket'] == 1713000123


def test_runner_emits_after_flush_hook_events(storage):
    events = []
    session = _create_session(storage, planned_duration_sec=3)
    runner = DataCollectionRunner(
        session=session,
        storage=storage,
        next_second_bucket=lambda: 1713000123,
        accumulator=_FakeAccumulator([valid_snapshot(1713000123)]),
        assembler=lambda row: {'session_id': session['session_id'], 'inst_id': 'BTC-USDT-SWAP', **row},
        after_flush=lambda **kwargs: [
            {
                'event': 'sample_index_materialized',
                'session_id': kwargs['session_id'],
                'decision_ts': kwargs['second_bucket'] + 1,
            }
        ],
        publish_event=events.append,
    )

    asyncio.run(runner.start())

    assert [event['event'] for event in events] == [
        'session_started',
        'sample_index_materialized',
        'second_flushed',
        'session_quality_updated',
        'session_running',
    ]
