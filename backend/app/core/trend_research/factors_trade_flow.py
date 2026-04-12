from __future__ import annotations

from collections.abc import Sequence

from .rolling_stats import rolling_mean_series, rolling_quantile_series, safe_divide


TRADE_INTENSITY_WINDOW = 60
TRADE_INTENSITY_NOTIONAL_WEIGHT = 0.5
TRADE_INTENSITY_COUNT_WEIGHT = 0.5
LARGE_TRADE_WINDOW = 60
LARGE_TRADE_QUANTILE = 0.75
BURST_NOTIONAL_WEIGHT = 0.5
BURST_COUNT_WEIGHT = 0.5


def compute_signed_volume_imbalance_series(bars: Sequence) -> list[float]:
    values: list[float] = []
    for bar in bars:
        total_notional = _total_notional(bar)
        imbalance = float(bar.buy_notional) - float(bar.sell_notional)
        values.append(safe_divide(imbalance, total_notional))
    return values


def compute_trade_intensity_series(bars: Sequence) -> list[float]:
    totals = [_total_notional(bar) for bar in bars]
    counts = [_total_count(bar) for bar in bars]
    total_baseline = rolling_mean_series(
        totals,
        window=TRADE_INTENSITY_WINDOW,
        include_current=False,
    )
    count_baseline = rolling_mean_series(
        counts,
        window=TRADE_INTENSITY_WINDOW,
        include_current=False,
    )
    values: list[float] = []
    for index, total in enumerate(totals):
        count = counts[index]
        if total <= 0.0 and count <= 0.0:
            values.append(0.0)
            continue
        total_ratio = safe_divide(total, total_baseline[index], default=0.0)
        count_ratio = safe_divide(count, count_baseline[index], default=0.0)
        values.append(
            total_ratio * TRADE_INTENSITY_NOTIONAL_WEIGHT
            + count_ratio * TRADE_INTENSITY_COUNT_WEIGHT
        )
    return values


def compute_large_trade_share_series(bars: Sequence) -> list[float]:
    thresholds = rolling_quantile_series(
        [float(bar.max_trade_notional) for bar in bars],
        window=LARGE_TRADE_WINDOW,
        quantile=LARGE_TRADE_QUANTILE,
        include_current=False,
    )
    values: list[float] = []
    for index, bar in enumerate(bars):
        total_notional = _total_notional(bar)
        max_trade_notional = float(bar.max_trade_notional)
        if max_trade_notional < thresholds[index]:
            values.append(0.0)
            continue
        values.append(safe_divide(max_trade_notional, total_notional))
    return values


def compute_buy_burst_strength_series(bars: Sequence) -> list[float]:
    return [
        _burst_strength(
            bar,
            burst_notional=float(bar.buy_burst_notional),
            burst_count=int(bar.buy_burst_count),
        )
        for bar in bars
    ]


def compute_sell_burst_strength_series(bars: Sequence) -> list[float]:
    return [
        _burst_strength(
            bar,
            burst_notional=float(bar.sell_burst_notional),
            burst_count=int(bar.sell_burst_count),
        )
        for bar in bars
    ]


def _burst_strength(bar, *, burst_notional: float, burst_count: int) -> float:
    total_notional = _total_notional(bar)
    total_count = _total_count(bar)
    notional_share = safe_divide(burst_notional, total_notional)
    count_share = safe_divide(burst_count, total_count)
    return notional_share * BURST_NOTIONAL_WEIGHT + count_share * BURST_COUNT_WEIGHT


def _total_notional(bar) -> float:
    return float(bar.buy_notional) + float(bar.sell_notional)


def _total_count(bar) -> float:
    return float(bar.buy_count) + float(bar.sell_count)
