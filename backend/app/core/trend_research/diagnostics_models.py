from __future__ import annotations

from dataclasses import asdict, dataclass, is_dataclass
from typing import Any


DEFAULT_PIPELINE_STAGE = "waiting_trade"
DEFAULT_STALE_SECONDS = 30.0
DEFAULT_SUBSCRIPTION_STATE = "subscribed"
KIND_ERROR = "error"
KIND_RECOVERY = "recovery"
LABEL_BOOK = "Book 到达"
LABEL_ERROR = "运行异常"
LABEL_FEATURE = "特征已生成"
LABEL_INFERENCE = "推断已生成"
LABEL_RECOVERY = "链路恢复"
LABEL_STATE = "状态同步"
LABEL_TRADE = "Trade 到达"
STAGE_COLLECTING = "collecting"
STAGE_FEATURE_READY = "feature_ready"
STAGE_INFERENCE_READY = "inference_ready"
STAGE_WAITING_BOOK = "waiting_book"
STAGE_WAITING_STATE = "waiting_state"


@dataclass(frozen=True)
class TrendTimelineEntry:
    sequence: int
    inst_id: str
    kind: str
    emitted_at: float
    label: str
    message: str = ""
    second_bucket: int | None = None


@dataclass(frozen=True)
class TrendInstrumentHealth:
    inst_id: str
    pipeline_stage: str = DEFAULT_PIPELINE_STAGE
    trade_age_seconds: float | None = None
    book_age_seconds: float | None = None
    state_age_seconds: float | None = None
    last_feature_at: float | None = None
    last_inference_at: float | None = None
    last_event_at: float | None = None
    is_stale: bool = True
    is_error: bool = False
    current_error: str = ""


@dataclass(frozen=True)
class TrendInstrumentDetails:
    subscription_state: str = "idle"
    pending_trade_count: int = 0
    last_feature_bucket: int | None = None
    last_inference_bucket: int | None = None
    last_error_at: float | None = None


@dataclass(frozen=True)
class TrendInstrumentRuntimeState:
    inst_id: str
    last_trade_at: float | None = None
    last_book_at: float | None = None
    last_state_at: float | None = None
    last_feature_at: float | None = None
    last_inference_at: float | None = None
    last_feature_bucket: int | None = None
    last_inference_bucket: int | None = None
    last_error_at: float | None = None
    current_error: str = ""
    subscription_state: str = DEFAULT_SUBSCRIPTION_STATE
    pending_trade_count: int = 0


def age_seconds(now_ts: float, value: float | None) -> float | None:
    if value is None:
        return None
    return round(max(now_ts - value, 0.0), 1)


def last_event_at(state: TrendInstrumentRuntimeState) -> float | None:
    values = (
        state.last_trade_at,
        state.last_book_at,
        state.last_state_at,
        state.last_feature_at,
        state.last_inference_at,
        state.last_error_at,
    )
    resolved = [value for value in values if value is not None]
    if not resolved:
        return None
    return max(resolved)


def pipeline_stage(state: TrendInstrumentRuntimeState) -> str:
    if state.last_inference_at is not None:
        return STAGE_INFERENCE_READY
    if state.last_feature_at is not None:
        return STAGE_FEATURE_READY
    if state.last_trade_at is None:
        return DEFAULT_PIPELINE_STAGE
    if state.last_book_at is None:
        return STAGE_WAITING_BOOK
    if state.last_state_at is None:
        return STAGE_WAITING_STATE
    return STAGE_COLLECTING


def is_stale(
    state: TrendInstrumentRuntimeState,
    now_ts: float,
    stale_seconds: float,
) -> bool:
    latest = last_event_at(state)
    if latest is None:
        return True
    return (now_ts - latest) >= stale_seconds


def model_to_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    return dict(getattr(value, "__dict__", {}))
