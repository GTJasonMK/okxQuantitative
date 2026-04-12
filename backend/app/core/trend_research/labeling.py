from __future__ import annotations

from typing import List

from .models import FeatureBar1s, SwingLabel


def _resolve_label_price(bar: FeatureBar1s) -> float:
    if float(bar.mid_price or 0.0) > 0.0:
        return float(bar.mid_price)
    if float(bar.mark_price or 0.0) > 0.0:
        return float(bar.mark_price)
    return float(bar.index_price or 0.0)


def build_swing_labels(
    bars: List[FeatureBar1s],
    *,
    sigma_floor: float = 0.002,
    threshold_multiplier: float = 1.5,
) -> List[SwingLabel]:
    if not bars:
        return []

    labels: List[SwingLabel] = []
    prices = [_resolve_label_price(bar) for bar in bars]
    threshold = max(float(sigma_floor or 0.0), 0.0) * max(float(threshold_multiplier or 0.0), 0.0)

    for index, bar in enumerate(bars):
        prev_price = prices[index - 1] if index > 0 else prices[index]
        next_price = prices[index + 1] if index + 1 < len(prices) else prices[index]
        price = prices[index]

        top_strength = price - max(prev_price, next_price)
        bottom_strength = min(prev_price, next_price) - price
        swing_top = index > 0 and index + 1 < len(prices) and top_strength > threshold
        swing_bottom = index > 0 and index + 1 < len(prices) and bottom_strength > threshold

        trend_state = "range"
        if next_price > prev_price:
            trend_state = "uptrend"
        elif next_price < prev_price:
            trend_state = "downtrend"

        labels.append(
            SwingLabel(
                inst_id=bar.inst_id,
                second_bucket=bar.second_bucket,
                trend_state=trend_state,
                swing_top_confirmed=swing_top,
                swing_bottom_confirmed=swing_bottom,
                time_to_top=0 if swing_top else 10,
                time_to_bottom=0 if swing_bottom else 10,
            )
        )

    return labels
