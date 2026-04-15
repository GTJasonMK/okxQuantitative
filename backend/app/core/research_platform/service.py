from __future__ import annotations

from threading import Lock
from typing import Callable

from .protocols import RESEARCH_PROTOCOL_LOCKS


class ResearchPlatformService:
    def __init__(self, *, collection_service, census_service, dataset_service, training_service, storage):
        self._collection = collection_service
        self._census = census_service
        self._dataset = dataset_service
        self._training = training_service
        self._storage = storage
        self._listeners_lock = Lock()
        self._listeners: list[Callable[[dict[str, object]], None]] = []
        if hasattr(self._collection, 'add_listener'):
            self._collection.add_listener(self._forward_collection_event)

    def add_listener(self, listener: Callable[[dict[str, object]], None]) -> None:
        with self._listeners_lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[dict[str, object]], None]) -> None:
        with self._listeners_lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def _emit(self, payload: dict[str, object]) -> None:
        with self._listeners_lock:
            listeners = list(self._listeners)
        for listener in listeners:
            listener(payload)

    def _forward_collection_event(self, payload: dict[str, object]) -> None:
        self._emit(payload)
        event_name = str(payload.get('event', ''))
        if event_name.startswith('session_') and event_name != 'session_deleted':
            self._emit({**payload, 'event': 'session_updated'})

    def get_protocol_locks(self) -> dict[str, str]:
        return dict(RESEARCH_PROTOCOL_LOCKS)

    async def start(self) -> None:
        await self._census.start()

    async def stop(self) -> None:
        await self._census.stop()

    async def start_collection_session(self, payload: dict[str, object]) -> dict[str, object]:
        return await self._collection.start_collection_session(payload)

    async def stop_collection_session(self, session_id: str) -> dict[str, object] | None:
        return await self._collection.stop_collection_session(session_id)

    async def delete_collection_session(self, session_id: str) -> dict[str, object] | None:
        return await self._collection.delete_collection_session(session_id)

    def list_collection_sessions(self, *, limit: int = 50) -> list[dict[str, object]]:
        return self._storage.list_research_collection_sessions(limit=limit)

    def get_collection_session_detail(self, session_id: str) -> dict[str, object] | None:
        session = self._storage.get_research_collection_session(session_id)
        if session is None:
            return None
        return {
            **session,
            'progress': self._storage.get_research_session_progress_summary(session_id),
            'coverage': self._storage.get_research_session_coverage_summary(session_id),
            'charts': self._storage.get_research_session_chart_series(session_id),
        }

    def get_census_status(self) -> dict[str, object]:
        return {
            'enabled': self._census.enabled,
            'last_decision_ts': self._census.last_decision_ts,
            'census_policy_version': RESEARCH_PROTOCOL_LOCKS['census_policy_version_v1'],
            'shift_state_definition_version': RESEARCH_PROTOCOL_LOCKS['shift_state_definition_version_v1'],
            'universe_count': int(getattr(self._census, 'universe_count', 0) or 0),
        }

    def create_dataset_manifest(self, payload: dict[str, object]) -> dict[str, object]:
        dataset = self._dataset.create_dataset_manifest(payload)
        self._emit({'event': 'dataset_manifest_created', 'dataset_id': dataset['dataset_id']})
        return dataset

    def delete_dataset_manifest(self, dataset_id: str) -> dict[str, object] | None:
        dataset = self._dataset.delete_dataset_manifest(dataset_id)
        if dataset is not None:
            self._emit({'event': 'dataset_manifest_deleted', 'dataset_id': dataset['dataset_id']})
        return dataset

    def list_dataset_manifests(self, *, limit: int = 50) -> list[dict[str, object]]:
        return self._dataset.list_dataset_manifests(limit=limit)

    def get_dataset_manifest(self, dataset_id: str) -> dict[str, object] | None:
        return self._dataset.get_dataset_manifest(dataset_id)

    def get_dataset_protocol_validation_status(self, dataset_id: str) -> str:
        return self._dataset.get_dataset_protocol_validation_status(dataset_id)

    def get_dataset_split_summary(self, dataset_id: str) -> dict[str, object]:
        return self._dataset.get_dataset_split_summary(dataset_id)

    def get_dataset_weight_summary(self, dataset_id: str) -> dict[str, object]:
        return self._dataset.get_dataset_weight_summary(dataset_id)

    def get_dataset_regime_schema(self, dataset_id: str) -> dict[str, object]:
        return self._dataset.get_dataset_regime_schema(dataset_id)

    def get_dataset_effective_size_summary(self, dataset_id: str) -> dict[str, object]:
        return self._dataset.get_dataset_effective_size_summary(dataset_id)

    def get_dataset_shift_diagnostic_preview(self, dataset_id: str) -> dict[str, object]:
        return self._dataset.get_dataset_shift_diagnostic_preview(dataset_id)

    def get_dataset_fit_artifact_preview(self, dataset_id: str) -> dict[str, object]:
        return self._dataset.get_dataset_fit_artifact_preview(dataset_id)

    def get_dataset_shift_diagnostics_bundle(self, dataset_id: str) -> dict[str, object]:
        return self._dataset.get_dataset_shift_diagnostics_bundle(dataset_id)

    def start_training_run(self, payload: dict[str, object]) -> dict[str, object]:
        run = self._training.start_training_run(payload)
        self._emit(
            {
                'event': 'training_run_updated',
                'run_id': run['run_id'],
                'status': run['status'],
                'progress_stage': run['progress_stage'],
                'forecast_metrics_ref': run['forecast_metrics_ref'],
                'decision_metrics_ref': run['decision_metrics_ref'],
                'artifact_bundle_ref': run['diagnostics_ref'],
            }
        )
        return run

    def list_training_runs(
        self,
        *,
        dataset_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        return self._training.list_training_runs(dataset_id=dataset_id, limit=limit)

    def get_training_run_detail(self, run_id: str) -> dict[str, object] | None:
        return self._training.get_training_run_detail(run_id)
