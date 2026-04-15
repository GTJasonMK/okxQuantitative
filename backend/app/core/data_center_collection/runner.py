from __future__ import annotations

import time

from app.core.storage_research_platform import SESSION_STATUS_FAILED
from app.core.storage_research_platform import SESSION_STATUS_FINISHED
from app.core.storage_research_platform import SESSION_STATUS_RUNNING
from app.core.storage_research_platform import SESSION_STATUS_STOPPED


class DataCollectionRunner:
    def __init__(self, *, session, storage, next_second_bucket, accumulator, assembler, publish_event, after_flush=None):
        self._session = session
        self._storage = storage
        self._next_second_bucket = next_second_bucket
        self._accumulator = accumulator
        self._assembler = assembler
        self._publish_event = publish_event
        self._after_flush = after_flush
        self._written_seconds = 0
        self._valid_second_count = 0
        self._missing_second_count = 0
        self._planned_duration_sec = int(session['planned_duration_sec'])
        self._started = False

    def _emit(self, payload: dict[str, object]) -> None:
        self._publish_event({'session_id': self._session['session_id'], **payload})

    async def start(self) -> dict[str, object]:
        self._started = True
        self._emit({'event': 'session_started'})
        return await self.flush_once()

    async def flush_once(self, second_bucket: int | None = None) -> dict[str, object]:
        try:
            second_bucket = int(second_bucket if second_bucket is not None else self._next_second_bucket())
            row = self._assembler(self._accumulator.flush(second_bucket))
            row.setdefault('session_id', self._session['session_id'])
            row.setdefault('inst_id', self._session['inst_id'])
            self._storage.save_research_second_state(**row)
            self._emit_after_flush(second_bucket=second_bucket, row=row)
            self._written_seconds += 1
            self._valid_second_count += int(row.get('is_valid_second', 0))
            self._missing_second_count += int(not row.get('is_valid_second', 0))
            self._emit({'event': 'second_flushed', 'second_bucket': second_bucket})
            session = self._storage.update_research_collection_session(
                self._session['session_id'],
                status=SESSION_STATUS_RUNNING,
                valid_second_count=self._valid_second_count,
                missing_second_count=self._missing_second_count,
                coverage_ratio=self._written_seconds / self._planned_duration_sec,
            )
            self._emit({
                'event': 'session_quality_updated',
                'written_seconds': self._written_seconds,
                'valid_second_count': self._valid_second_count,
                'missing_second_count': self._missing_second_count,
            })
            self._emit({'event': 'session_running'})
            if self._written_seconds >= self._planned_duration_sec:
                session = self._storage.update_research_collection_session(
                    self._session['session_id'],
                    status=SESSION_STATUS_FINISHED,
                    stop_reason='planned_finish',
                    ended_at=float(time.time()),
                )
                self._emit({'event': 'session_finished', 'stop_reason': 'planned_finish'})
            return session
        except Exception as exc:
            session = self._storage.update_research_collection_session(
                self._session['session_id'],
                status=SESSION_STATUS_FAILED,
                last_error_code='flush_failed',
                last_error_message=str(exc),
                failed_at=float(time.time()),
                ended_at=float(time.time()),
            )
            self._emit({
                'event': 'session_failed',
                'status': SESSION_STATUS_FAILED,
                'error_code': 'flush_failed',
                'error_message': str(exc),
                'failed_at': session['failed_at'],
            })
            return session

    async def stop(self, *, stop_reason: str) -> dict[str, object]:
        session = self._storage.update_research_collection_session(
            self._session['session_id'],
            status=SESSION_STATUS_STOPPED,
            stop_reason=stop_reason,
            ended_at=float(time.time()),
        )
        self._emit({'event': 'session_stopped', 'stop_reason': stop_reason})
        return session

    def _emit_after_flush(self, *, second_bucket: int, row: dict[str, object]) -> None:
        if self._after_flush is None:
            return
        events = self._after_flush(
            session_id=str(self._session['session_id']),
            inst_id=str(self._session['inst_id']),
            second_bucket=int(second_bucket),
            row=row,
        )
        for payload in events or []:
            self._emit(payload)
