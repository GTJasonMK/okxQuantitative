from __future__ import annotations

from typing import Any

from .diagnostics_models import model_to_dict
from .process_view import build_trend_process_snapshot
from .training_run_models import build_training_summary


def resolve_trend_status(*, enabled: bool, whitelist, rows, runtime_error: str = "") -> str:
    if not enabled:
        return "disabled"
    if not whitelist:
        return "unconfigured"
    if runtime_error:
        return "error"
    if not rows:
        return "collecting"
    return "ready"


def build_trend_realtime_payload(service, *, bar_limit: int = 20, rows_limit: int = 50) -> dict:
    settings = service.get_settings()
    runtime_error = str(getattr(service, "get_runtime_error", lambda: "")() or "")
    model_status = dict(getattr(service, "get_model_status", lambda: {})() or {})
    cached_rows = list(getattr(service, "_inference_rows", ()) or ())
    rows = [model_to_dict(row) for row in cached_rows[:max(int(rows_limit or 50), 1)]]
    training_run = dict(getattr(service, "get_training_run", lambda: {})() or {})
    return {
        "enabled": bool(settings["enabled"]),
        "status": resolve_trend_status(
            enabled=bool(settings["enabled"]),
            whitelist=settings["whitelist"],
            rows=rows,
            runtime_error=runtime_error,
        ),
        "whitelist": list(settings["whitelist"]),
        "runtime_error": runtime_error,
        "model_status": model_status,
        "rows": rows,
        "training_run": training_run,
        "training_summary": build_training_summary(training_run or None),
        **build_trend_process_snapshot(service, bar_limit=bar_limit, prefer_cache=True),
    }
