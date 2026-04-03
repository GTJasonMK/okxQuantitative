from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional, Tuple


class SyncJobCancelled(RuntimeError):
    """后台同步任务已被取消。"""

    pass


def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class SyncJobState:
    task_id: str
    inst_id: str
    inst_type: str
    timeframe: str
    mode: str
    days: int
    status: str = "queued"
    progress: int = 0
    message: str = "等待开始"
    created_at: str = field(default_factory=_now_iso)
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: str = ""
    fetched_count: int = 0
    saved_count: int = 0
    batches: int = 0
    api_calls: int = 0
    candle_count: int = 0
    history_complete: bool = False
    last_sync_mode: str = "window"
    last_sync_time: Optional[str] = None
    oldest_timestamp: Optional[int] = None
    newest_timestamp: Optional[int] = None
    reused_existing: bool = False
    cancel_requested: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "inst_id": self.inst_id,
            "inst_type": self.inst_type,
            "timeframe": self.timeframe,
            "mode": self.mode,
            "days": self.days,
            "status": self.status,
            "progress": self.progress,
            "message": self.message,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "error": self.error,
            "fetched_count": self.fetched_count,
            "saved_count": self.saved_count,
            "batches": self.batches,
            "api_calls": self.api_calls,
            "candle_count": self.candle_count,
            "history_complete": self.history_complete,
            "last_sync_mode": self.last_sync_mode,
            "last_sync_time": self.last_sync_time,
            "oldest_timestamp": self.oldest_timestamp,
            "newest_timestamp": self.newest_timestamp,
            "reused_existing": self.reused_existing,
            "cancel_requested": self.cancel_requested,
            "oldest_time": datetime.fromtimestamp(self.oldest_timestamp / 1000).isoformat() if self.oldest_timestamp else None,
            "newest_time": datetime.fromtimestamp(self.newest_timestamp / 1000).isoformat() if self.newest_timestamp else None,
        }


class MarketSyncTaskManager:
    """行情同步后台任务管理器。"""

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: Dict[str, SyncJobState] = {}
        self._active_keys: Dict[Tuple[str, str, str, str, int], str] = {}

    def _job_key(self, inst_id: str, inst_type: str, timeframe: str, mode: str, days: int) -> Tuple[str, str, str, str, int]:
        return (inst_id, inst_type, timeframe, mode, max(int(days), 1))

    def _update_job(self, task_id: str, **updates: Any) -> bool:
        with self._lock:
            job = self._jobs.get(task_id)
            if not job:
                return False
            requested_status = updates.get("status")
            if job.status == "cancelled" and requested_status != "cancelled":
                return False
            for key, value in updates.items():
                if hasattr(job, key):
                    setattr(job, key, value)
            return True

    def _is_cancel_requested(self, task_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(task_id)
            return bool(job and job.cancel_requested)

    def _cancel_job_locked(self, job: SyncJobState, *, reason: str) -> Dict[str, Any]:
        job.cancel_requested = True
        job.status = "cancelled"
        job.progress = 100
        job.message = reason
        job.finished_at = job.finished_at or _now_iso()
        job.error = ""
        return job.to_dict()

    def _run_job(
        self,
        task_id: str,
        key: Tuple[str, str, str, str, int],
        runner: Callable[[Callable[[Dict[str, Any]], None]], Dict[str, Any]],
    ) -> None:
        self._update_job(
            task_id,
            status="running",
            progress=1,
            message="后台任务已启动",
            started_at=_now_iso(),
        )
        if self._is_cancel_requested(task_id):
            return

        def progress_callback(payload: Dict[str, Any]) -> None:
            if self._is_cancel_requested(task_id):
                raise SyncJobCancelled("同步任务已取消")
            progress = payload.get("progress")
            if progress is not None:
                payload["progress"] = max(0, min(int(progress), 100))
            self._update_job(task_id, **payload)

        try:
            result = runner(progress_callback)
            if self._is_cancel_requested(task_id):
                return
            self._update_job(
                task_id,
                status="completed",
                progress=100,
                message=result.get("message", "同步完成"),
                finished_at=_now_iso(),
                error="",
                fetched_count=int(result.get("fetched_count", 0) or 0),
                saved_count=int(result.get("saved_count", 0) or 0),
                batches=int(result.get("batches", 0) or 0),
                api_calls=int(result.get("api_calls", 0) or 0),
                candle_count=int(result.get("candle_count", 0) or 0),
                history_complete=bool(result.get("history_complete", False)),
                last_sync_mode=result.get("last_sync_mode", result.get("mode", "window")),
                last_sync_time=result.get("last_sync_time"),
                oldest_timestamp=result.get("oldest_timestamp"),
                newest_timestamp=result.get("newest_timestamp"),
            )
        except SyncJobCancelled as e:
            self._update_job(
                task_id,
                status="cancelled",
                progress=100,
                message=str(e) or "同步任务已取消",
                finished_at=_now_iso(),
                error="",
            )
        except Exception as e:
            if self._is_cancel_requested(task_id):
                self._update_job(
                    task_id,
                    status="cancelled",
                    progress=100,
                    message="同步任务已取消",
                    finished_at=_now_iso(),
                    error="",
                )
                return
            self._update_job(
                task_id,
                status="failed",
                progress=100,
                message="同步失败",
                finished_at=_now_iso(),
                error=str(e),
            )
        finally:
            with self._lock:
                current_task_id = self._active_keys.get(key)
                if current_task_id == task_id:
                    self._active_keys.pop(key, None)

    def start_job(
        self,
        *,
        inst_id: str,
        inst_type: str,
        timeframe: str,
        mode: str,
        days: int,
        runner: Callable[[Callable[[Dict[str, Any]], None]], Dict[str, Any]],
    ) -> Dict[str, Any]:
        key = self._job_key(inst_id, inst_type, timeframe, mode, days)

        with self._lock:
            existing_task_id = self._active_keys.get(key)
            if existing_task_id and existing_task_id in self._jobs:
                existing_job = self._jobs[existing_task_id]
                snapshot = existing_job.to_dict()
                snapshot["reused_existing"] = True
                return snapshot

            task_id = uuid.uuid4().hex[:16]
            job = SyncJobState(
                task_id=task_id,
                inst_id=inst_id,
                inst_type=inst_type,
                timeframe=timeframe,
                mode=mode,
                days=days,
            )
            self._jobs[task_id] = job
            self._active_keys[key] = task_id

        thread = threading.Thread(
            target=self._run_job,
            args=(task_id, key, runner),
            name=f"market-sync-{task_id}",
            daemon=True,
        )
        thread.start()
        return job.to_dict()

    def cancel_jobs(
        self,
        *,
        inst_ids: Optional[List[str]] = None,
        task_ids: Optional[List[str]] = None,
        reason: str = "同步任务已取消",
    ) -> List[Dict[str, Any]]:
        normalized_inst_ids = {item for item in (inst_ids or []) if item}
        normalized_task_ids = {item for item in (task_ids or []) if item}
        cancelled_jobs: List[Dict[str, Any]] = []

        with self._lock:
            for key, task_id in list(self._active_keys.items()):
                job = self._jobs.get(task_id)
                if not job:
                    self._active_keys.pop(key, None)
                    continue
                if job.status not in {"queued", "running"}:
                    self._active_keys.pop(key, None)
                    continue
                if normalized_task_ids and task_id not in normalized_task_ids:
                    continue
                if normalized_inst_ids and job.inst_id not in normalized_inst_ids:
                    continue
                cancelled_jobs.append(self._cancel_job_locked(job, reason=reason))
                self._active_keys.pop(key, None)

        cancelled_jobs.sort(key=lambda item: (item["created_at"], item["task_id"]), reverse=True)
        return cancelled_jobs

    def get_job(self, task_id: str) -> Optional[Dict[str, Any]]:
        with self._lock:
            job = self._jobs.get(task_id)
            return job.to_dict() if job else None

    def list_jobs(
        self,
        *,
        only_active: bool = False,
        limit: int = 50,
        task_ids: Optional[List[str]] = None,
    ) -> List[Dict[str, Any]]:
        with self._lock:
            if task_ids:
                jobs = [self._jobs[task_id] for task_id in task_ids if task_id in self._jobs]
            else:
                jobs = list(self._jobs.values())

        if only_active:
            jobs = [job for job in jobs if job.status in {"queued", "running"}]

        jobs.sort(key=lambda item: (item.created_at, item.task_id), reverse=True)
        effective_limit = max(1, int(limit))
        if task_ids:
            effective_limit = max(effective_limit, len(task_ids))
        return [job.to_dict() for job in jobs[:effective_limit]]


_sync_task_manager = MarketSyncTaskManager()


def get_market_sync_task_manager() -> MarketSyncTaskManager:
    return _sync_task_manager
