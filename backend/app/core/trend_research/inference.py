from __future__ import annotations

from math import exp

from .models import FeatureBar1s, TrendInferenceSnapshot
from .sequence_dataset import build_online_sequence_window


TREND_SCORE_SCALE = 10_000.0
TREND_CONFIRMATION_THRESHOLD = 20.0
PARTIAL_DATA_CONFIDENCE_SCALE = 0.5
MODEL_NOT_READY_STATE = "model_not_ready"


def _direct_metrics_to_dict(metrics) -> dict:
    if metrics is None:
        return {}
    return {
        "top_time_mae_minutes": float(metrics.top_time_mae_minutes),
        "bottom_time_mae_minutes": float(metrics.bottom_time_mae_minutes),
        "top_price_mae_bps": float(metrics.top_price_mae_bps),
        "bottom_price_mae_bps": float(metrics.bottom_price_mae_bps),
        "joint_hit_rate": float(metrics.joint_hit_rate),
    }


def _resolve_trend_state(trend_score: float) -> str:
    if trend_score > TREND_CONFIRMATION_THRESHOLD:
        return "uptrend_confirmed"
    if trend_score < -TREND_CONFIRMATION_THRESHOLD:
        return "downtrend_confirmed"
    return "range"


def _resolve_price(bar: FeatureBar1s) -> float:
    for value in (bar.close_price, bar.mid_price, bar.mark_price, bar.index_price):
        if float(value or 0.0) > 0.0:
            return float(value)
    return 0.0


def _resolve_eta_seconds(bucket_index: int | None, bucket_seconds: int) -> int | None:
    if bucket_index is None:
        return None
    return (int(bucket_index) + 1) * int(bucket_seconds)


def _resolve_price_target(current_price: float, predicted_return: float | None) -> float | None:
    if current_price <= 0.0 or predicted_return is None:
        return None
    return current_price * exp(float(predicted_return))


def _resolve_confidence(*, top_distribution: tuple[float, ...], bottom_distribution: tuple[float, ...]) -> float:
    top_confidence = max(top_distribution) if top_distribution else 0.0
    bottom_confidence = max(bottom_distribution) if bottom_distribution else 0.0
    return max(float(top_confidence), float(bottom_confidence))


def _resolve_trend_score(top_return: float, bottom_return: float) -> float:
    raw_score = (float(top_return) + float(bottom_return)) * TREND_SCORE_SCALE
    return max(min(raw_score, 100.0), -100.0)


def _run_direct_model(window, bundle):
    from .direct_training import run_direct_model

    return run_direct_model(window, bundle)


class TrendInferenceEngine:
    """把最近分钟级因子窗口映射成未来顶底的直接预测。"""

    def __init__(self, model_bundle=None):
        self._model_bundle = model_bundle

    def set_model_bundle(self, model_bundle) -> None:
        self._model_bundle = model_bundle

    def get_model_status(self) -> dict:
        if self._model_bundle is None:
            return {
                "ready": False,
                "architecture": "",
                "trained_at": "",
                "input_minutes": 0,
                "horizon_minutes": 0,
                "bucket_seconds": 0,
                "selected_feature_count": 0,
                "metrics": {},
            }
        config = self._model_bundle.config
        return {
            "ready": True,
            "architecture": str(config.architecture),
            "trained_at": self._model_bundle.trained_at,
            "input_minutes": int(config.input_minutes),
            "horizon_minutes": int(config.horizon_minutes),
            "bucket_seconds": int(config.bucket_seconds),
            "selected_feature_count": len(config.feature_names),
            "metrics": _direct_metrics_to_dict(self._model_bundle.metrics),
        }

    def build_snapshot(
        self,
        bar: FeatureBar1s,
        *,
        recent_bars: tuple[FeatureBar1s, ...] | None = None,
    ) -> TrendInferenceSnapshot:
        if self._model_bundle is None:
            return self._build_unready_snapshot(bar)
        if recent_bars is None:
            raise ValueError("recent_bars are required for direct extrema inference")
        return self._build_model_snapshot(bar, recent_bars)

    def _build_unready_snapshot(self, bar: FeatureBar1s) -> TrendInferenceSnapshot:
        return TrendInferenceSnapshot(
            inst_id=bar.inst_id,
            second_bucket=bar.second_bucket,
            trend_score=0.0,
            trend_state=MODEL_NOT_READY_STATE,
            confidence=0.0,
            data_quality=bar.data_quality,
            current_price=_resolve_price(bar),
        )

    def _build_model_snapshot(self, bar: FeatureBar1s, recent_bars: tuple[FeatureBar1s, ...]) -> TrendInferenceSnapshot:
        config = self._model_bundle.config
        current_price = _resolve_price(bar)
        window = build_online_sequence_window(
            recent_bars,
            feature_names=config.feature_names,
            input_minutes=config.input_minutes,
        )
        prediction = _run_direct_model(window, self._model_bundle)
        trend_score = _resolve_trend_score(prediction.top_return, prediction.bottom_return)
        confidence = _resolve_confidence(
            top_distribution=prediction.top_distribution,
            bottom_distribution=prediction.bottom_distribution,
        )
        if bar.data_quality != "ok":
            confidence *= PARTIAL_DATA_CONFIDENCE_SCALE
        top_probability = max(prediction.top_distribution) if prediction.top_distribution else 0.0
        bottom_probability = max(prediction.bottom_distribution) if prediction.bottom_distribution else 0.0
        return TrendInferenceSnapshot(
            inst_id=bar.inst_id,
            second_bucket=bar.second_bucket,
            trend_score=trend_score,
            trend_state=_resolve_trend_state(trend_score),
            confidence=confidence,
            data_quality=bar.data_quality,
            current_price=current_price,
            predicted_top_eta_seconds=_resolve_eta_seconds(prediction.top_time_bucket, config.bucket_seconds),
            predicted_bottom_eta_seconds=_resolve_eta_seconds(prediction.bottom_time_bucket, config.bucket_seconds),
            predicted_top_price=_resolve_price_target(current_price, prediction.top_return),
            predicted_bottom_price=_resolve_price_target(current_price, prediction.bottom_return),
            predicted_top_return=float(prediction.top_return),
            predicted_bottom_return=float(prediction.bottom_return),
            top_time_distribution=prediction.top_distribution,
            bottom_time_distribution=prediction.bottom_distribution,
            top_probability=float(top_probability),
            bottom_probability=float(bottom_probability),
        )
