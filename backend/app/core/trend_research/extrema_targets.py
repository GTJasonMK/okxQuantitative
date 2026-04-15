from __future__ import annotations

from math import log, sqrt
from statistics import fmean

from .models import ExtremaTarget, FeatureBar1s, resolve_bar_price

_resolve_price = resolve_bar_price


SECONDS_PER_MINUTE = 60
DEFAULT_HORIZON_MINUTES = 60
DEFAULT_VOLATILITY_WINDOW_SECONDS = 300
MIN_REVERSAL_FLOOR = 0.002
REVERSAL_SIGMA_MULTIPLIER = 2.0


def _relative_gain(start_price: float, end_price: float) -> float:
    if start_price <= 0.0 or end_price <= 0.0:
        return 0.0
    return max((end_price - start_price) / start_price, 0.0)


def _relative_drop(start_price: float, end_price: float) -> float:
    if start_price <= 0.0 or end_price <= 0.0:
        return 0.0
    return max((start_price - end_price) / start_price, 0.0)


def _future_offsets(second_buckets: list[int], index: int, horizon_seconds: int) -> list[int]:
    start_bucket = second_buckets[index]
    return [
        offset
        for offset in range(index + 1, len(second_buckets))
        if second_buckets[offset] - start_bucket <= horizon_seconds
    ]


def _realized_volatility(prices: list[float], second_buckets: list[int], index: int, window_seconds: int) -> float:
    window_start = second_buckets[index] - max(int(window_seconds or 0), 0)
    window_prices = [prices[offset] for offset in range(index + 1) if second_buckets[offset] >= window_start]
    returns = [
        log(window_prices[offset] / window_prices[offset - 1])
        for offset in range(1, len(window_prices))
        if window_prices[offset] > 0.0 and window_prices[offset - 1] > 0.0
    ]
    if len(returns) < 2:
        return 0.0

    mean_return = fmean(returns)
    variance = fmean([(value - mean_return) ** 2 for value in returns])
    return sqrt(max(variance, 0.0))


def _max_post_peak_reversal(future_prices: list[float], peak_index: int) -> float:
    post_peak_prices = future_prices[peak_index + 1 :]
    if not post_peak_prices:
        return 0.0
    peak_price = future_prices[peak_index]
    return max(_relative_drop(peak_price, price) for price in post_peak_prices)


def _max_post_trough_reversal(future_prices: list[float], trough_index: int) -> float:
    post_trough_prices = future_prices[trough_index + 1 :]
    if not post_trough_prices:
        return 0.0
    trough_price = future_prices[trough_index]
    return max(_relative_gain(trough_price, price) for price in post_trough_prices)


def _select_peak_candidate(future_prices: list[float], reversal_threshold: float) -> tuple[int, float] | None:
    candidates = [
        (index, price)
        for index, price in enumerate(future_prices)
        if _max_post_peak_reversal(future_prices, index) >= reversal_threshold
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda item: item[1])


def _select_trough_candidate(future_prices: list[float], reversal_threshold: float) -> tuple[int, float] | None:
    candidates = [
        (index, price)
        for index, price in enumerate(future_prices)
        if _max_post_trough_reversal(future_prices, index) >= reversal_threshold
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda item: item[1])


def _build_target(
    bars: list[FeatureBar1s],
    prices: list[float],
    second_buckets: list[int],
    index: int,
    horizon_minutes: int,
    volatility_window_seconds: int,
) -> ExtremaTarget:
    horizon_seconds = max(int(horizon_minutes or 0), 0) * SECONDS_PER_MINUTE
    offsets = _future_offsets(second_buckets, index, horizon_seconds)
    realized_volatility = _realized_volatility(prices, second_buckets, index, volatility_window_seconds)
    reversal_threshold = max(MIN_REVERSAL_FLOOR, realized_volatility * REVERSAL_SIGMA_MULTIPLIER)
    if not offsets:
        return ExtremaTarget(
            inst_id=bars[index].inst_id,
            second_bucket=bars[index].second_bucket,
            horizon_minutes=horizon_minutes,
            realized_volatility=realized_volatility,
            reversal_threshold=reversal_threshold,
            top_event=False,
            bottom_event=False,
            time_to_top_seconds=None,
            time_to_bottom_seconds=None,
            top_forward_return=0.0,
            bottom_forward_return=0.0,
            top_reversal_return=0.0,
            bottom_reversal_return=0.0,
        )

    current_price = prices[index]
    future_prices = [prices[offset] for offset in offsets]
    peak_candidate = _select_peak_candidate(future_prices, reversal_threshold)
    trough_candidate = _select_trough_candidate(future_prices, reversal_threshold)
    peak_index = peak_candidate[0] if peak_candidate else None
    trough_index = trough_candidate[0] if trough_candidate else None
    top_forward_return = _relative_gain(current_price, future_prices[peak_index]) if peak_candidate else 0.0
    bottom_forward_return = _relative_drop(current_price, future_prices[trough_index]) if trough_candidate else 0.0
    top_reversal_return = _max_post_peak_reversal(future_prices, peak_index) if peak_candidate else 0.0
    bottom_reversal_return = _max_post_trough_reversal(future_prices, trough_index) if trough_candidate else 0.0
    top_event = bool(peak_candidate) and top_forward_return > 0.0
    bottom_event = bool(trough_candidate) and bottom_forward_return > 0.0
    return ExtremaTarget(
        inst_id=bars[index].inst_id,
        second_bucket=bars[index].second_bucket,
        horizon_minutes=horizon_minutes,
        realized_volatility=realized_volatility,
        reversal_threshold=reversal_threshold,
        top_event=top_event,
        bottom_event=bottom_event,
        time_to_top_seconds=second_buckets[offsets[peak_index]] - second_buckets[index] if top_event else None,
        time_to_bottom_seconds=second_buckets[offsets[trough_index]] - second_buckets[index] if bottom_event else None,
        top_forward_return=top_forward_return,
        bottom_forward_return=bottom_forward_return,
        top_reversal_return=top_reversal_return,
        bottom_reversal_return=bottom_reversal_return,
    )


def build_extrema_targets(
    bars: list[FeatureBar1s],
    *,
    horizon_minutes: int = DEFAULT_HORIZON_MINUTES,
    volatility_window_seconds: int = DEFAULT_VOLATILITY_WINDOW_SECONDS,
) -> list[ExtremaTarget]:
    if not bars:
        return []

    prices = [_resolve_price(bar) for bar in bars]
    second_buckets = [bar.second_bucket for bar in bars]
    return [
        _build_target(bars, prices, second_buckets, index, horizon_minutes, volatility_window_seconds)
        for index in range(len(bars))
    ]
