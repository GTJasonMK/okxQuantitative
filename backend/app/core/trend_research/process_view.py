from __future__ import annotations

import time
from typing import Any

from .diagnostics_models import model_to_dict


def _stage(ready: bool, waiting_label: str, ready_label: str) -> dict:
    return {
        "ready": bool(ready),
        "label": ready_label if ready else waiting_label,
    }


def _resolve_pipeline_state(stages: dict) -> str:
    if stages["inference"]["ready"]:
        return "inference_ready"
    if stages["feature"]["ready"]:
        return "feature_ready"
    if not stages["trade"]["ready"]:
        return "waiting_trade"
    if not stages["book"]["ready"]:
        return "waiting_book"
    if not stages["state"]["ready"]:
        return "waiting_state"
    return "collecting"


def _with_age(snapshot: dict, now_ts: float) -> dict:
    result = dict(snapshot)
    for key in ("last_trade_ts_local", "last_book_ts_local", "last_state_ts_local"):
        value = result.get(key)
        result[key.replace("_ts_local", "_age_seconds")] = round(max(now_ts - value, 0.0), 1) if value else None
    return result


def _build_stages(runtime: dict, latest_feature_bar: dict, latest_inference: dict) -> dict:
    return {
        "trade": _stage(runtime["has_trade_input"], "等待逐笔成交", "逐笔成交已到达"),
        "book": _stage(runtime["has_book_input"], "等待盘口", "盘口已到达"),
        "state": _stage(runtime["has_contract_state"], "等待合约状态同步", "合约状态已同步"),
        "feature": _stage(bool(latest_feature_bar), "等待生成 1 秒特征条", "最近 1 秒特征条已生成"),
        "inference": _stage(bool(latest_inference), "等待推断输出", "最新推断已生成"),
    }


def _resolve_recent_feature_bars(service, inst_id: str, limit: int, *, prefer_cache: bool) -> list[dict]:
    if prefer_cache:
        cached_rows = list(getattr(service, "_recent_bars_by_inst", {}).get(inst_id, ()))
        if not cached_rows:
            return []
        return [model_to_dict(bar) for bar in cached_rows[-limit:]]
    return [
        model_to_dict(bar)
        for bar in reversed(service.storage.list_feature_bars_1s(inst_id, limit=limit))
    ]


def build_trend_process_snapshot(service, *, bar_limit: int = 20, prefer_cache: bool = False) -> dict:
    normalized_limit = max(int(bar_limit or 20), 1)
    settings = service.get_settings()
    model_status = dict(getattr(service, "get_model_status", lambda: {})() or {})
    now_ts = time.time()
    latest_inference_by_inst = getattr(service, "_latest_inference_by_inst", {})
    whitelist = list(settings["whitelist"])
    instruments = []
    summary = {
        "whitelist_count": len(whitelist),
        "trade_ready_count": 0,
        "book_ready_count": 0,
        "state_ready_count": 0,
        "feature_ready_count": 0,
        "inference_ready_count": 0,
        "model_ready": bool(model_status.get("ready")),
        "trained_at": str(model_status.get("trained_at", "")),
        "horizon_minutes": int(model_status.get("horizon_minutes", 0) or 0),
        "selected_feature_count": int(model_status.get("selected_feature_count", 0) or 0),
    }

    for inst_id in whitelist:
        builder = service.builders.get(inst_id)
        runtime = _with_age(
            model_to_dict(builder.build_runtime_snapshot()) if builder is not None else {
                "inst_id": inst_id,
                "has_trade_input": False,
                "has_book_input": False,
                "has_contract_state": False,
                "pending_trade_count": 0,
                "last_trade_ts_local": None,
                "last_book_ts_local": None,
                "last_state_ts_local": None,
                "last_trade_price": 0.0,
                "last_trade_side": "",
            },
            now_ts,
        )
        recent_feature_bars = _resolve_recent_feature_bars(
            service,
            inst_id,
            normalized_limit,
            prefer_cache=prefer_cache,
        )
        latest_feature_bar = recent_feature_bars[-1] if recent_feature_bars else {}
        latest_inference = model_to_dict(latest_inference_by_inst.get(inst_id))
        stages = _build_stages(runtime, latest_feature_bar, latest_inference)
        summary["trade_ready_count"] += int(stages["trade"]["ready"])
        summary["book_ready_count"] += int(stages["book"]["ready"])
        summary["state_ready_count"] += int(stages["state"]["ready"])
        summary["feature_ready_count"] += int(stages["feature"]["ready"])
        summary["inference_ready_count"] += int(stages["inference"]["ready"])
        instruments.append(
            {
                "inst_id": inst_id,
                "pipeline_state": _resolve_pipeline_state(stages),
                "runtime": runtime,
                "stages": stages,
                "model": model_status,
                "latest_feature_bar": latest_feature_bar,
                "latest_inference": latest_inference,
                "recent_feature_bars": recent_feature_bars,
            }
        )

    return {
        "summary": summary,
        "instruments": instruments,
        "bar_limit": normalized_limit,
    }
