from __future__ import annotations

from collections.abc import Sequence

from .rolling_stats import safe_divide


BPS_MULTIPLIER = 10000.0


def compute_queue_imbalance_series(bars: Sequence) -> list[float]:
    return [
        safe_divide(
            float(bar.bid_size) - float(bar.ask_size),
            float(bar.bid_size) + float(bar.ask_size),
        )
        for bar in bars
    ]


def compute_microprice_premium_bps_series(bars: Sequence) -> list[float]:
    values: list[float] = []
    for bar in bars:
        premium = safe_divide(float(bar.microprice) - float(bar.mid_price), float(bar.mid_price))
        values.append(premium * BPS_MULTIPLIER)
    return values


def compute_spread_level_bps_series(bars: Sequence) -> list[float]:
    return [
        safe_divide(float(bar.ask_price) - float(bar.bid_price), float(bar.mid_price)) * BPS_MULTIPLIER
        for bar in bars
    ]


def compute_ofi_top_book_series(bars: Sequence) -> list[float]:
    values = [0.0]
    for index in range(1, len(bars)):
        previous = bars[index - 1]
        current = bars[index]
        values.append(_ofi_step(previous, current))
    return values[:len(bars)]


def _ofi_step(previous, current) -> float:
    bid_term = 0.0
    ask_term = 0.0
    if current.bid_price >= previous.bid_price:
        bid_term += float(current.bid_size)
    if current.bid_price <= previous.bid_price:
        bid_term -= float(previous.bid_size)
    if current.ask_price <= previous.ask_price:
        ask_term -= float(current.ask_size)
    if current.ask_price >= previous.ask_price:
        ask_term += float(previous.ask_size)
    return bid_term + ask_term
