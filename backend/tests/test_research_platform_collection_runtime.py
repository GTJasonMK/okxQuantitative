from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.core.data_center_collection.controller import CollectionSessionController
from app.core.data_center_collection.runtime_registry import CollectionRuntimeRegistry
from app.core.data_storage import DataStorage
from app.core.research_platform.collection.service import ResearchCollectionService


@pytest.fixture
def storage(tmp_path: Path):
    instance = DataStorage(tmp_path / 'research_collection_runtime.db')
    yield instance
    connection = getattr(instance, '_local', None)
    if connection is not None and getattr(connection, 'connection', None) is not None:
        connection.connection.close()
        connection.connection = None


@pytest.fixture
def collection_service(storage):
    class _BootstrapRuntime:
        def __init__(self, *, storage, session, emit_event):
            self._storage = storage
            self._session = session
            self._emit_event = emit_event

        async def start(self):
            self._emit_event({
                'event': 'session_started',
                'session_id': self._session['session_id'],
            })

        async def stop(self, *, stop_reason):
            self._storage.update_research_collection_session(
                self._session['session_id'],
                status='stopped',
                stop_reason=stop_reason,
            )
            self._emit_event({
                'event': 'session_stopped',
                'session_id': self._session['session_id'],
                'stop_reason': stop_reason,
            })

    controller = CollectionSessionController(
        storage=storage,
        runtime_registry=CollectionRuntimeRegistry(),
        runtime_factory=lambda session, emit_event: _BootstrapRuntime(
            storage=storage,
            session=session,
            emit_event=emit_event,
        ),
    )
    return ResearchCollectionService(storage=storage, controller=controller)


def test_collection_service_bootstrap_runtime_emits_listener_events(storage, collection_service):
    seen = []
    collection_service.add_listener(seen.append)

    session = asyncio.run(
        collection_service.start_collection_session(
            {
                'inst_id': 'BTC-USDT-SWAP',
                'planned_duration_sec': 1800,
                'trigger_mode': 'manual',
                'trigger_note': 'operator-started',
                'sampling_policy_id': 'manual_session_v1',
                'integrity_policy_version': 'strict_v1',
                'collector_version': 'research_collector_v1',
                'source_config_hash': 'manual',
                'feature_recipe_version': 'second_state_causal_tensor_v1',
                'book_channel': 'books5',
            }
        )
    )

    assert session['status'] == 'starting'
    assert seen[0]['event'] == 'session_started'

    stopped = asyncio.run(collection_service.stop_collection_session(session['session_id']))

    assert stopped['status'] == 'stopped'
    assert seen[-1]['event'] == 'session_stopped'
