from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional

from ..utils.datetimes import parse_iso_datetime
from ..utils.numbers import safe_float_convert as _safe_float
from ..utils.timeframes import TIMEFRAME_TO_MS
from ..utils.watched_symbols_store import normalize_watched_symbol


_TIMEFRAME_ALIASES: Dict[str, str] = {
    "1m": "1m",
    "3m": "3m",
    "5m": "5m",
    "15m": "15m",
    "30m": "30m",
    "1h": "1H",
    "2h": "2H",
    "4h": "4H",
    "6h": "6H",
    "12h": "12H",
    "1d": "1D",
    "1w": "1W",
    "1M": "1M",
}


def _safe_json_value(value: Any) -> Any:
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if math.isnan(value) or math.isinf(value):
            return None
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _safe_json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_safe_json_value(item) for item in value]
    if hasattr(value, "to_dict") and callable(value.to_dict):
        return _safe_json_value(value.to_dict())
    return value


def _latest_valid(series: Any) -> Any:
    if isinstance(series, Mapping):
        return {str(key): _latest_valid(value) for key, value in series.items()}
    if not isinstance(series, list):
        return _safe_json_value(series)
    for item in reversed(series):
        value = _safe_json_value(item)
        if value is not None:
            return value
    return None


def _normalize_timeframe(value: str) -> str:
    raw = str(value or "").strip()
    if raw in TIMEFRAME_TO_MS:
        return raw
    normalized = _TIMEFRAME_ALIASES.get(raw.lower())
    if normalized and normalized in TIMEFRAME_TO_MS:
        return normalized
    if raw.endswith("M") and raw in TIMEFRAME_TO_MS:
        return raw
    raise ValueError(f"不支持的 timeframe: {value}")


def _normalize_inst_type(inst_id: str, inst_type: Optional[str]) -> str:
    raw = str(inst_type or "").upper().strip()
    if raw in {"SPOT", "SWAP", "FUTURES", "OPTION"}:
        return raw
    return "SWAP" if str(inst_id or "").upper().endswith("-SWAP") else "SPOT"


def _serialize_candle(candle: Any) -> Dict[str, Any]:
    return {
        "timestamp": int(getattr(candle, "timestamp", 0) or 0),
        "datetime": getattr(candle, "datetime").isoformat(),
        "open": _safe_json_value(float(getattr(candle, "open", 0) or 0)),
        "high": _safe_json_value(float(getattr(candle, "high", 0) or 0)),
        "low": _safe_json_value(float(getattr(candle, "low", 0) or 0)),
        "close": _safe_json_value(float(getattr(candle, "close", 0) or 0)),
        "volume": _safe_json_value(float(getattr(candle, "volume", 0) or 0)),
        "volume_ccy": _safe_json_value(float(getattr(candle, "volume_ccy", 0) or 0)),
    }


def _serialize_indicator_payload(
    name: str,
    series: Any,
    params: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    safe_series = _safe_json_value(series)
    return {
        "name": name,
        "params": params or {},
        "series": safe_series,
        "latest": _latest_valid(safe_series),
    }


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _utc_now_iso() -> str:
    return _utc_now().isoformat()


def _format_order_number(value: Any, *, precision: int = 8) -> str:
    number = _safe_float(value, 0.0)
    if number <= 0:
        return ""
    return f"{number:.{precision}f}".rstrip("0").rstrip(".")


def _timeframe_sort_key(timeframe: str) -> int:
    return int(TIMEFRAME_TO_MS.get(timeframe, 10**18))


def _dedupe_timeframes(values: Iterable[str]) -> List[str]:
    results: List[str] = []
    seen: set[str] = set()
    for item in values:
        normalized = _normalize_timeframe(item)
        if normalized in seen:
            continue
        seen.add(normalized)
        results.append(normalized)
    results.sort(key=_timeframe_sort_key)
    return results


def _age_ms_from_iso(value: Optional[str]) -> Optional[int]:
    if not value:
        return None
    try:
        dt = parse_iso_datetime(value)
    except Exception:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return max(0, int((_utc_now() - dt.astimezone(timezone.utc)).total_seconds() * 1000))


def _average(values: Iterable[float]) -> float:
    numbers = [float(item) for item in values]
    return sum(numbers) / len(numbers) if numbers else 0.0


def _resolve_analysis_inst_id(symbol: str, inst_type: str) -> str:
    normalized_symbol = normalize_watched_symbol(symbol)
    if not normalized_symbol:
        return ""
    normalized_inst_type = _normalize_inst_type(normalized_symbol, inst_type)
    if normalized_inst_type == "SWAP" and not normalized_symbol.endswith("-SWAP"):
        return f"{normalized_symbol}-SWAP"
    if normalized_inst_type != "SWAP" and normalized_symbol.endswith("-SWAP"):
        return normalized_symbol[:-5]
    return normalized_symbol


def _resolve_query_inst_id(inst_id: str, inst_type: Optional[str]) -> tuple[str, str]:
    normalized_inst_type = _normalize_inst_type(inst_id, inst_type)
    return _resolve_analysis_inst_id(inst_id, normalized_inst_type), normalized_inst_type


def _pearson_correlation(left: List[float], right: List[float]) -> float:
    if len(left) != len(right) or len(left) < 2:
        return 0.0

    left_mean = sum(left) / len(left)
    right_mean = sum(right) / len(right)
    numerator = sum((lx - left_mean) * (rx - right_mean) for lx, rx in zip(left, right))
    left_variance = sum((value - left_mean) ** 2 for value in left)
    right_variance = sum((value - right_mean) ** 2 for value in right)
    denominator = math.sqrt(left_variance * right_variance)
    if denominator <= 0:
        return 0.0
    return numerator / denominator


def _trend_label(score: float) -> str:
    if score >= 2:
        return "bullish"
    if score <= -2:
        return "bearish"
    return "neutral"


def _health_status_from_score(score: float) -> str:
    if score >= 80:
        return "healthy"
    if score >= 45:
        return "degraded"
    if score > 0:
        return "stale"
    return "missing"


def _serialize_health_row(row: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    if not isinstance(row, dict):
        return {
            "symbol": "",
            "status": "missing",
            "health_score": 0.0,
            "missing_timeframes": [],
            "markets": {},
            "has_local_data": False,
        }
    return {
        "symbol": row.get("symbol") or "",
        "status": row.get("status") or "missing",
        "health_score": _safe_json_value(row.get("health_score")),
        "coverage_ratio": _safe_json_value(row.get("coverage_ratio")),
        "missing_timeframes": _safe_json_value(row.get("missing_timeframes") or []),
        "watched": bool(row.get("watched", False)),
        "orphan": bool(row.get("orphan", False)),
        "has_local_data": bool(row.get("has_local_data", False)),
        "markets": _safe_json_value(row.get("markets") or {}),
    }


def _serialize_optional_health_row(row: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not isinstance(row, dict):
        return None
    return _serialize_health_row(row)


def _summarize_position_snapshot(position: Dict[str, Any]) -> Dict[str, Any]:
    holdings = position.get("holdings") or []
    return {
        "available": bool(position.get("available", False)),
        "holding_count": int((position.get("summary") or {}).get("holding_count", len(holdings)) or 0),
        "assets": (position.get("summary") or {}).get("assets") or [],
    }


def _build_horizontal_annotation(
    price: Any,
    *,
    role: str,
    timeframe: str,
    strength: float,
) -> Dict[str, Any]:
    return {
        "type": "horizontal",
        "price": _safe_json_value(price),
        "meta": {
            "source": "assistant",
            "role": role,
            "timeframe": timeframe,
            "strength": _safe_json_value(round(strength, 4)),
        },
    }


def _build_trendline_annotation(
    *,
    start_ts: Any,
    end_ts: Any,
    start_price: Any,
    end_price: Any,
    scenario: str,
) -> Dict[str, Any]:
    return {
        "type": "trendline",
        "startTs": _safe_json_value(start_ts),
        "endTs": _safe_json_value(end_ts),
        "startPrice": _safe_json_value(start_price),
        "endPrice": _safe_json_value(end_price),
        "meta": {
            "source": "assistant",
            "scenario": scenario,
        },
    }

