from __future__ import annotations

from .diagnostics_models import (
    TrendInstrumentDetails,
    TrendInstrumentHealth,
    TrendInstrumentRuntimeState,
    age_seconds,
    is_stale,
    last_event_at,
    model_to_dict,
    pipeline_stage,
)


def build_health_dict(
    inst_id: str,
    state: TrendInstrumentRuntimeState,
    *,
    now_ts: float,
    stale_seconds: float,
) -> dict:
    return model_to_dict(
        TrendInstrumentHealth(
            inst_id=inst_id,
            pipeline_stage=pipeline_stage(state),
            trade_age_seconds=age_seconds(now_ts, state.last_trade_at),
            book_age_seconds=age_seconds(now_ts, state.last_book_at),
            state_age_seconds=age_seconds(now_ts, state.last_state_at),
            last_feature_at=state.last_feature_at,
            last_inference_at=state.last_inference_at,
            last_event_at=last_event_at(state),
            is_stale=is_stale(state, now_ts, stale_seconds),
            is_error=bool(state.current_error),
            current_error=state.current_error,
        )
    )


def build_details_dict(state: TrendInstrumentRuntimeState) -> dict:
    return model_to_dict(
        TrendInstrumentDetails(
            subscription_state=state.subscription_state,
            pending_trade_count=state.pending_trade_count,
            last_feature_bucket=state.last_feature_bucket,
            last_inference_bucket=state.last_inference_bucket,
            last_error_at=state.last_error_at,
        )
    )


def build_global_health(instruments: list[dict]) -> dict:
    stale_count = sum(1 for item in instruments if item["is_stale"])
    error_count = sum(1 for item in instruments if item["is_error"])
    return {
        "whitelist_count": len(instruments),
        "active_count": len(instruments) - stale_count,
        "stale_count": stale_count,
        "error_count": error_count,
        "last_event_at": max((item["last_event_at"] or 0.0 for item in instruments), default=0.0),
    }
