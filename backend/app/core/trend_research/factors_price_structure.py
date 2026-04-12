from __future__ import annotations

from collections.abc import Sequence

from .factors_microstructure import compute_queue_imbalance_series
from .factors_trade_flow import compute_signed_volume_imbalance_series
from .rolling_stats import (
    efficiency_ratio_series,
    realized_range_series,
    realized_volatility_series,
    rolling_extrema,
    rolling_return_series,
    safe_divide,
)


BREAKOUT_PRICE_WEIGHT = 0.5
BREAKOUT_QUEUE_WEIGHT = 0.25
BREAKOUT_FLOW_WEIGHT = 0.25
MOMENTUM_PERIOD_30S = 30
MOMENTUM_PERIOD_60S = 60
MOMENTUM_PERIOD_300S = 300


def compute_momentum_series(bars: Sequence, *, window: int) -> list[float]:
    closes = _close_series(bars)
    return rolling_return_series(closes, window=max(int(window), 1) + 1)


def compute_distance_to_window_extrema_series(
    bars: Sequence,
    *,
    window: int | None = None,
) -> list[float]:
    closes = _close_series(bars)
    normalized_window = max(int(window or len(closes) or 1), 1)
    rolling_highs, rolling_lows = rolling_extrema(closes, window=normalized_window)
    values: list[float] = []
    for index, close in enumerate(closes):
        spread = rolling_highs[index] - rolling_lows[index]
        values.append(safe_divide(close - rolling_lows[index], spread))
    return values


def compute_realized_volatility_factor_series(bars: Sequence) -> list[float]:
    closes = _close_series(bars)
    return realized_volatility_series(closes, window=max(len(closes) - 1, 1))


def compute_realized_range_factor_series(bars: Sequence) -> list[float]:
    closes = _close_series(bars)
    highs = [float(bar.high_price) for bar in bars]
    lows = [float(bar.low_price) for bar in bars]
    return realized_range_series(highs, lows, closes, window=max(len(closes), 1))


def compute_trend_efficiency_series(bars: Sequence) -> list[float]:
    closes = _close_series(bars)
    return efficiency_ratio_series(closes, window=max(len(closes) - 1, 1))


def compute_breakout_pressure_series(bars: Sequence) -> list[float]:
    position = compute_distance_to_window_extrema_series(bars)
    queue = compute_queue_imbalance_series(bars)
    flow = compute_signed_volume_imbalance_series(bars)
    return [
        (position[index] * 2.0 - 1.0) * BREAKOUT_PRICE_WEIGHT
        + queue[index] * BREAKOUT_QUEUE_WEIGHT
        + flow[index] * BREAKOUT_FLOW_WEIGHT
        for index in range(len(bars))
    ]


def _close_series(bars: Sequence) -> list[float]:
    values: list[float] = []
    for bar in bars:
        close_price = float(bar.close_price)
        values.append(close_price if close_price > 0.0 else float(bar.mid_price))
    return values
