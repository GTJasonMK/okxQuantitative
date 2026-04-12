from __future__ import annotations

from collections.abc import Sequence


FUNDING_BPS_MULTIPLIER = 10000.0
QUADRANT_NEW_LONG = 1.0
QUADRANT_SHORT_COVER = 0.5
QUADRANT_NEW_SHORT = -1.0
QUADRANT_LONG_LIQUIDATION = -0.5


def compute_basis_momentum_series(bars: Sequence) -> list[float]:
    values = [float(bar.basis_bps) for bar in bars]
    return _delta_series(values)


def compute_price_oi_quadrant_series(bars: Sequence) -> list[float]:
    closes = [float(bar.close_price) if float(bar.close_price) > 0.0 else float(bar.mid_price) for bar in bars]
    values = [0.0]
    for index in range(1, len(bars)):
        price_change = closes[index] - closes[index - 1]
        oi_delta = float(bars[index].oi_delta)
        values.append(_resolve_price_oi_quadrant(price_change, oi_delta))
    return values


def compute_funding_basis_divergence_series(bars: Sequence) -> list[float]:
    return [
        float(bar.basis_bps) - float(bar.funding_rate) * FUNDING_BPS_MULTIPLIER
        for bar in bars
    ]


def compute_premium_shock_series(bars: Sequence) -> list[float]:
    basis_delta = _delta_series([float(bar.basis_bps) for bar in bars])
    premium_delta = _delta_series([float(bar.premium) for bar in bars])
    return [
        abs(basis_delta[index]) + abs(float(bars[index].funding_delta) * FUNDING_BPS_MULTIPLIER) + abs(premium_delta[index])
        for index in range(len(bars))
    ]


def _delta_series(values: Sequence[float]) -> list[float]:
    if not values:
        return []
    result = [0.0]
    for index in range(1, len(values)):
        result.append(float(values[index]) - float(values[index - 1]))
    return result


def _resolve_price_oi_quadrant(price_change: float, oi_delta: float) -> float:
    if price_change > 0.0 and oi_delta > 0.0:
        return QUADRANT_NEW_LONG
    if price_change > 0.0 and oi_delta < 0.0:
        return QUADRANT_SHORT_COVER
    if price_change < 0.0 and oi_delta > 0.0:
        return QUADRANT_NEW_SHORT
    if price_change < 0.0 and oi_delta < 0.0:
        return QUADRANT_LONG_LIQUIDATION
    return 0.0
