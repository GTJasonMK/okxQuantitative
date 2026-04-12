from __future__ import annotations

from collections.abc import Sequence

from .factors_price_structure import compute_realized_volatility_factor_series
from .rolling_stats import rolling_return_series, safe_divide


RETURN_BPS_MULTIPLIER = 10000.0


def compute_amihud_illiquidity_series(bars: Sequence) -> list[float]:
    closes = _close_series(bars)
    returns = rolling_return_series(closes, window=2)
    return [
        safe_divide(abs(returns[index]), _dollar_volume(bar))
        for index, bar in enumerate(bars)
    ]


def compute_impact_per_notional_series(bars: Sequence) -> list[float]:
    closes = _close_series(bars)
    values = [0.0]
    for index in range(1, len(bars)):
        previous_close = closes[index - 1]
        signed_return_bps = safe_divide(
            closes[index] - previous_close,
            previous_close,
        ) * RETURN_BPS_MULTIPLIER
        values.append(
            safe_divide(
                signed_return_bps,
                _dollar_volume(bars[index]),
            )
        )
    return values


def compute_depth_to_vol_ratio_series(bars: Sequence) -> list[float]:
    volatility = compute_realized_volatility_factor_series(bars)
    return [
        safe_divide(_visible_depth_notional(bar), volatility[index])
        for index, bar in enumerate(bars)
    ]


def _close_series(bars: Sequence) -> list[float]:
    return [
        float(bar.close_price) if float(bar.close_price) > 0.0 else float(bar.mid_price)
        for bar in bars
    ]


def _dollar_volume(bar) -> float:
    return float(bar.buy_notional) + float(bar.sell_notional)


def _visible_depth_notional(bar) -> float:
    bid_depth = float(bar.bid_price) * float(bar.bid_size)
    ask_depth = float(bar.ask_price) * float(bar.ask_size)
    return bid_depth + ask_depth
