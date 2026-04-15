from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.core.data_center_collection.controller import CollectionSessionController
from app.core.data_center_collection.runtime_registry import CollectionRuntimeRegistry
from app.core.data_storage import DataStorage
from app.core.storage_research_platform import SESSION_STATUS_FAILED
from app.core.storage_research_platform import SESSION_STATUS_FINISHED
from app.core.storage_research_platform import SESSION_STATUS_RUNNING
from app.core.storage_research_platform import SESSION_STATUS_STARTING
from app.core.storage_research_platform import SESSION_STATUS_STOPPED


@pytest.fixture
def storage(tmp_path: Path):
    instance = DataStorage(tmp_path / 'collection_controller.db')
    yield instance
    connection = getattr(instance, '_local', None)
    if connection is not None and getattr(connection, 'connection', None) is not None:
        connection.connection.close()
        connection.connection = None


class _DummyRuntime:
    def __init__(self, *, storage, emit_event, session_id):
        self._storage = storage
        self._emit_event = emit_event
        self._session_id = session_id

    async def start(self):
        self._emit_event({'event': 'session_started', 'session_id': self._session_id})
        self._storage.update_research_collection_session(
            self._session_id,
            status=SESSION_STATUS_RUNNING,
        )

    async def stop(self, *, stop_reason):
        self._storage.update_research_collection_session(
            self._session_id,
            status=SESSION_STATUS_STOPPED,
            stop_reason=stop_reason,
        )
        self._emit_event({
            'event': 'session_stopped',
            'session_id': self._session_id,
            'stop_reason': stop_reason,
        })


class _FailingRuntime:
    def __init__(self, *, error_message):
        self._error_message = error_message

    async def start(self):
        raise RuntimeError(self._error_message)

    async def stop(self, *, stop_reason):
        raise AssertionError('stop should not be called when start fails')


def _payload():
    return {
        'inst_id': 'BTC-USDT-SWAP',
        'planned_duration_sec': 1800,
        'trigger_mode': 'manual',
        'trigger_note': '',
        'sampling_policy_id': 'manual_session_v1',
        'integrity_policy_version': 'strict_v1',
        'collector_version': 'research_collector_v1',
        'source_config_hash': 'manual',
        'feature_recipe_version': 'second_state_causal_tensor_v1',
        'book_channel': 'books5',
    }


def test_controller_returns_latest_session_after_runtime_start(storage):
    seen = []
    controller = CollectionSessionController(
        storage=storage,
        runtime_registry=CollectionRuntimeRegistry(),
        runtime_factory=lambda session, emit_event: _DummyRuntime(
            storage=storage,
            emit_event=emit_event,
            session_id=session['session_id'],
        ),
    )

    session = asyncio.run(controller.start_session(_payload(), emit_event=seen.append))

    assert session['status'] == SESSION_STATUS_RUNNING
    assert seen[0]['event'] == 'session_started'


def test_controller_marks_session_stopping_then_returns_stopped_session(storage):
    seen = []
    controller = CollectionSessionController(
        storage=storage,
        runtime_registry=CollectionRuntimeRegistry(),
        runtime_factory=lambda session, emit_event: _DummyRuntime(
            storage=storage,
            emit_event=emit_event,
            session_id=session['session_id'],
        ),
    )
    session = asyncio.run(controller.start_session(_payload(), emit_event=seen.append))

    stopped = asyncio.run(
        controller.stop_session(
            session['session_id'],
            stop_reason='manual_stop',
            emit_event=seen.append,
        )
    )

    assert stopped['status'] == SESSION_STATUS_STOPPED
    assert stopped['stop_reason'] == 'manual_stop'
    assert seen[-1]['event'] == 'session_stopped'


def test_controller_marks_session_failed_when_runtime_start_raises(storage):
    seen = []
    registry = CollectionRuntimeRegistry()
    controller = CollectionSessionController(
        storage=storage,
        runtime_registry=registry,
        runtime_factory=lambda session, emit_event: _FailingRuntime(
            error_message='market feed unavailable',
        ),
    )

    with pytest.raises(RuntimeError, match='market feed unavailable'):
        asyncio.run(controller.start_session(_payload(), emit_event=seen.append))

    sessions = storage.list_research_collection_sessions(limit=10)
    assert len(sessions) == 1
    failed = sessions[0]
    assert failed['status'] == SESSION_STATUS_FAILED
    assert failed['last_error_code'] == 'bootstrap_failed'
    assert failed['last_error_message'] == 'market feed unavailable'
    assert failed['failed_at'] is not None
    assert failed['ended_at'] is not None
    assert registry.active_session_id() is None
    assert seen[-1]['event'] == 'session_failed'
    assert seen[-1]['error_code'] == 'bootstrap_failed'


def test_controller_marks_orphaned_active_session_failed_when_runtime_missing_on_stop(storage):
    seen = []
    controller = CollectionSessionController(
        storage=storage,
        runtime_registry=CollectionRuntimeRegistry(),
        runtime_factory=lambda session, emit_event: _DummyRuntime(
            storage=storage,
            emit_event=emit_event,
            session_id=session['session_id'],
        ),
    )
    session_id = storage.create_research_collection_session(**_payload())
    storage.update_research_collection_session(session_id, status=SESSION_STATUS_STARTING)

    stopped = asyncio.run(
        controller.stop_session(
            session_id,
            stop_reason='manual_stop',
            emit_event=seen.append,
        )
    )

    assert stopped['status'] == SESSION_STATUS_FAILED
    assert stopped['stop_reason'] == 'runtime_missing'
    assert stopped['last_error_code'] == 'runtime_missing'
    assert 'collection runtime not found' in stopped['last_error_message']
    assert stopped['failed_at'] is not None
    assert stopped['ended_at'] is not None
    assert seen[-1]['event'] == 'session_failed'
    assert seen[-1]['error_code'] == 'runtime_missing'


def test_controller_rejects_deleting_active_session(storage):
    controller = CollectionSessionController(
        storage=storage,
        runtime_registry=CollectionRuntimeRegistry(),
        runtime_factory=lambda session, emit_event: _DummyRuntime(
            storage=storage,
            emit_event=emit_event,
            session_id=session['session_id'],
        ),
    )
    session_id = storage.create_research_collection_session(**_payload())
    storage.update_research_collection_session(session_id, status=SESSION_STATUS_RUNNING)

    with pytest.raises(RuntimeError, match='active collection sessions cannot be deleted'):
        asyncio.run(controller.delete_session(session_id, emit_event=lambda payload: None))


def test_controller_rejects_deleting_session_referenced_by_dataset(storage, monkeypatch):
    controller = CollectionSessionController(
        storage=storage,
        runtime_registry=CollectionRuntimeRegistry(),
        runtime_factory=lambda session, emit_event: _DummyRuntime(
            storage=storage,
            emit_event=emit_event,
            session_id=session['session_id'],
        ),
    )
    session_id = storage.create_research_collection_session(**_payload())
    storage.update_research_collection_session(session_id, status=SESSION_STATUS_FINISHED)
    monkeypatch.setattr(
        storage,
        'list_research_dataset_ids_for_session',
        lambda _session_id: ['dataset-1'],
    )

    with pytest.raises(RuntimeError, match='delete referenced datasets first'):
        asyncio.run(controller.delete_session(session_id, emit_event=lambda payload: None))


def test_controller_deletes_session_and_cascades_bound_rows(storage):
    seen = []
    controller = CollectionSessionController(
        storage=storage,
        runtime_registry=CollectionRuntimeRegistry(),
        runtime_factory=lambda session, emit_event: _DummyRuntime(
            storage=storage,
            emit_event=emit_event,
            session_id=session['session_id'],
        ),
    )
    session_id = storage.create_research_collection_session(**_payload())
    storage.update_research_collection_session(session_id, status=SESSION_STATUS_STOPPED)
    _save_second_state(storage, session_id)
    _save_sample_index(storage, session_id)
    _save_boundary_target(storage, session_id)

    deleted = asyncio.run(controller.delete_session(session_id, emit_event=seen.append))

    assert deleted['session_id'] == session_id
    assert deleted['deleted_second_state_count'] == 1
    assert deleted['deleted_sample_index_count'] == 1
    assert deleted['deleted_boundary_target_count'] == 1
    assert deleted['deleted_session_count'] == 1
    assert storage.get_research_collection_session(session_id) is None
    assert storage.list_research_second_states(session_id, limit=10) == []
    assert storage.list_research_sample_index_15m_for_sessions([session_id]) == []
    assert storage.list_research_boundary_targets_15m_for_sessions([session_id]) == []
    assert seen[-1]['event'] == 'session_deleted'
    assert seen[-1]['session_id'] == session_id


def _save_second_state(storage, session_id):
    storage.save_research_second_state(
        session_id=session_id,
        inst_id='BTC-USDT-SWAP',
        second_bucket=1713000899,
        ts_exchange=1713000899.0,
        ts_local=1713000899.1,
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


def _save_sample_index(storage, session_id):
    storage.save_research_sample_index_15m(
        sample_id=f'{session_id}:1713000900',
        session_id=session_id,
        inst_id='BTC-USDT-SWAP',
        decision_ts=1713000900,
        input_start_ts=1712993700,
        input_end_ts=1713000900,
        label_start_ts=1713000900,
        label_end_ts=1713001800,
        input_second_count=7200,
        label_second_count=900,
        input_complete_7200=1,
        label_complete_900=1,
        sample_valid=1,
        ready_for_inference=1,
        ready_for_training=1,
        invalid_reason='',
        prev_sample_overlap_seconds=6300,
        stride_seconds=900,
    )


def _save_boundary_target(storage, session_id):
    storage.save_research_boundary_target_15m(
        target_id=f'{session_id}:1713000900',
        session_id=session_id,
        inst_id='BTC-USDT-SWAP',
        decision_ts=1713000900,
        anchor_second_bucket=1713000899,
        anchor_close_price=65000.2,
        label_start_ts=1713000900,
        label_end_ts=1713001800,
        open_price=65000.1,
        high_price=65001.0,
        low_price=64999.8,
        close_price=65000.6,
        r_open=0.00001,
        r_close=0.00002,
        u=0.00003,
        d=0.00002,
        label_complete=1,
        invalid_reason='',
        label_definition_version='next_bar_15m_ohlc_reparam_from_session_seconds_v1',
    )
