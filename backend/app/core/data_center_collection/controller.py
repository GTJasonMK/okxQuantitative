import time

from app.core.data_center_collection.errors import CollectionSessionBootstrapError
from app.core.research_platform_delete_errors import CollectionSessionDeleteBlockedError
from app.core.storage_research_platform import SESSION_STATUS_FAILED
from app.core.storage_research_platform import SESSION_STATUS_RUNNING
from app.core.storage_research_platform import SESSION_STATUS_STARTING
from app.core.storage_research_platform import SESSION_STATUS_STOPPING


ACTIVE_COLLECTION_SESSION_STATUSES = {
    SESSION_STATUS_STARTING,
    SESSION_STATUS_RUNNING,
    SESSION_STATUS_STOPPING,
}
RUNTIME_MISSING_ERROR_CODE = 'runtime_missing'
RUNTIME_MISSING_STOP_REASON = 'runtime_missing'
RUNTIME_MISSING_MESSAGE = 'collection runtime not found; session likely belongs to an earlier backend process'


class CollectionSessionController:
    def __init__(self, *, storage, runtime_registry, runtime_factory):
        self._storage = storage
        self._runtime_registry = runtime_registry
        self._runtime_factory = runtime_factory

    async def start_session(self, payload: dict[str, object], *, emit_event) -> dict[str, object]:
        session_id = self._storage.create_research_collection_session(**payload)
        session = self._storage.get_research_collection_session(session_id)
        runtime = self._runtime_factory(session, emit_event)
        self._runtime_registry.register(session_id, runtime)
        try:
            await runtime.start()
        except Exception as exc:
            self._runtime_registry.unregister(session_id)
            self._mark_session_failed(
                session_id,
                error_code='bootstrap_failed',
                error_message=str(exc),
                emit_event=emit_event,
            )
            raise CollectionSessionBootstrapError(
                session_id=session_id,
                detail=str(exc),
            ) from exc
        return self._storage.get_research_collection_session(session_id)

    async def stop_session(
        self,
        session_id: str,
        *,
        stop_reason: str,
        emit_event,
    ) -> dict[str, object]:
        runtime = self._runtime_registry.get(session_id)
        if runtime is None:
            return self._mark_session_failed(
                session_id,
                error_code=RUNTIME_MISSING_ERROR_CODE,
                error_message=RUNTIME_MISSING_MESSAGE,
                stop_reason=RUNTIME_MISSING_STOP_REASON,
                emit_event=emit_event,
            )
        self._storage.update_research_collection_session(
            session_id,
            status='stopping',
            stop_reason=stop_reason,
        )
        emit_event({
            'event': 'session_stopping',
            'session_id': session_id,
            'stop_reason': stop_reason,
        })
        try:
            await runtime.stop(stop_reason=stop_reason)
        finally:
            self._runtime_registry.unregister(session_id)
        return self._storage.get_research_collection_session(session_id)

    async def delete_session(self, session_id: str, *, emit_event) -> dict[str, object] | None:
        session = self._storage.get_research_collection_session(session_id)
        if session is None:
            return None
        if self._runtime_registry.get(session_id) is not None:
            raise CollectionSessionDeleteBlockedError.active_session(session_id)
        if str(session.get('status') or '') in ACTIVE_COLLECTION_SESSION_STATUSES:
            raise CollectionSessionDeleteBlockedError.active_session(session_id)
        blocking_dataset_ids = self._storage.list_research_dataset_ids_for_session(session_id)
        if blocking_dataset_ids:
            raise CollectionSessionDeleteBlockedError.referenced_by_datasets(
                session_id,
                blocking_dataset_ids,
            )
        deleted = self._storage.delete_research_collection_session_cascade(session_id)
        emit_event({'event': 'session_deleted', **deleted})
        return deleted

    def _mark_session_failed(
        self,
        session_id: str,
        *,
        error_code: str,
        error_message: str,
        stop_reason: str = '',
        emit_event,
    ) -> dict[str, object]:
        failed_at = float(time.time())
        session = self._storage.update_research_collection_session(
            session_id,
            status=SESSION_STATUS_FAILED,
            stop_reason=stop_reason,
            last_error_code=error_code,
            last_error_message=error_message,
            failed_at=failed_at,
            ended_at=failed_at,
        )
        emit_event({
            'event': 'session_failed',
            'session_id': session_id,
            'status': SESSION_STATUS_FAILED,
            'error_code': error_code,
            'error_message': error_message,
            'failed_at': session['failed_at'],
        })
        return session
