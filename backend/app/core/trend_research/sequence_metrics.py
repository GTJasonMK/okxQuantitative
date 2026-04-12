from __future__ import annotations

from math import exp
from statistics import fmean

from .direct_models import DirectExtremaMetrics


TIME_HIT_WINDOW_MINUTES = 5.0
PRICE_HIT_WINDOW_BPS = 50.0
BPS_SCALE = 10_000.0


def _mean_abs(values: list[float]) -> float:
    return fmean(values) if values else 0.0


def _price_error_bps(predicted_return: float, target_return: float) -> float:
    return abs(exp(predicted_return) - exp(target_return)) * BPS_SCALE


def build_direct_extrema_metrics(
    *,
    predicted_top_buckets: list[int],
    target_top_buckets: list[int],
    predicted_bottom_buckets: list[int],
    target_bottom_buckets: list[int],
    predicted_top_returns: list[float],
    target_top_returns: list[float],
    predicted_bottom_returns: list[float],
    target_bottom_returns: list[float],
) -> DirectExtremaMetrics:
    top_time_errors = [abs(float(predicted) - float(target)) for predicted, target in zip(predicted_top_buckets, target_top_buckets)]
    bottom_time_errors = [abs(float(predicted) - float(target)) for predicted, target in zip(predicted_bottom_buckets, target_bottom_buckets)]
    top_price_errors = [_price_error_bps(float(predicted), float(target)) for predicted, target in zip(predicted_top_returns, target_top_returns)]
    bottom_price_errors = [_price_error_bps(float(predicted), float(target)) for predicted, target in zip(predicted_bottom_returns, target_bottom_returns)]
    joint_hits = []
    for index in range(min(len(top_time_errors), len(bottom_time_errors), len(top_price_errors), len(bottom_price_errors))):
        joint_hits.append(
            top_time_errors[index] <= TIME_HIT_WINDOW_MINUTES
            and bottom_time_errors[index] <= TIME_HIT_WINDOW_MINUTES
            and top_price_errors[index] <= PRICE_HIT_WINDOW_BPS
            and bottom_price_errors[index] <= PRICE_HIT_WINDOW_BPS
        )
    return DirectExtremaMetrics(
        top_time_mae_minutes=_mean_abs(top_time_errors),
        bottom_time_mae_minutes=_mean_abs(bottom_time_errors),
        top_price_mae_bps=_mean_abs(top_price_errors),
        bottom_price_mae_bps=_mean_abs(bottom_price_errors),
        joint_hit_rate=fmean([1.0 if hit else 0.0 for hit in joint_hits]) if joint_hits else 0.0,
    )
