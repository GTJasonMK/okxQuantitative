from __future__ import annotations

import math
from collections.abc import Sequence


EPSILON = 1e-9


def safe_divide(numerator: float, denominator: float, *, default: float = 0.0) -> float:
    if abs(denominator) <= EPSILON:
        return default
    return numerator / denominator


def rolling_return_series(values: Sequence[float], *, window: int) -> list[float]:
    normalized_window = max(int(window), 1)
    result: list[float] = []
    for index, value in enumerate(values):
        start = max(index - normalized_window + 1, 0)
        base_value = float(values[start])
        result.append(safe_divide(float(value), base_value, default=1.0) - 1.0)
    return result


def rolling_extrema(values: Sequence[float], *, window: int) -> tuple[list[float], list[float]]:
    normalized_window = max(int(window), 1)
    rolling_highs: list[float] = []
    rolling_lows: list[float] = []
    for index in range(len(values)):
        start = max(index - normalized_window + 1, 0)
        window_values = [float(item) for item in values[start:index + 1]]
        rolling_highs.append(max(window_values))
        rolling_lows.append(min(window_values))
    return rolling_highs, rolling_lows


def rolling_mean_series(
    values: Sequence[float],
    *,
    window: int,
    include_current: bool = True,
) -> list[float]:
    return [
        sum(window_values) / len(window_values)
        for window_values in _window_series(values, window=window, include_current=include_current)
    ]


def rolling_quantile_series(
    values: Sequence[float],
    *,
    window: int,
    quantile: float,
    include_current: bool = True,
) -> list[float]:
    clipped_quantile = min(max(float(quantile), 0.0), 1.0)
    result: list[float] = []
    for window_values in _window_series(values, window=window, include_current=include_current):
        ordered = sorted(window_values)
        if len(ordered) == 1:
            result.append(ordered[0])
            continue
        position = clipped_quantile * (len(ordered) - 1)
        lower_index = int(math.floor(position))
        upper_index = int(math.ceil(position))
        fraction = position - lower_index
        lower_value = ordered[lower_index]
        upper_value = ordered[upper_index]
        result.append(lower_value + (upper_value - lower_value) * fraction)
    return result


def realized_volatility_series(closes: Sequence[float], *, window: int) -> list[float]:
    returns = _log_return_series(closes)
    normalized_window = max(int(window), 1)
    result: list[float] = []
    for index in range(len(returns)):
        start = max(index - normalized_window + 1, 0)
        squared_sum = sum(value * value for value in returns[start:index + 1])
        result.append(math.sqrt(squared_sum))
    return result


def realized_range_series(
    highs: Sequence[float],
    lows: Sequence[float],
    closes: Sequence[float],
    *,
    window: int,
) -> list[float]:
    rolling_highs, rolling_lows = rolling_extrema(highs, window=window)
    _, rolling_close_lows = rolling_extrema(lows, window=window)
    result: list[float] = []
    for index, close in enumerate(closes):
        price_range = float(rolling_highs[index]) - float(rolling_close_lows[index])
        result.append(safe_divide(price_range, float(close), default=0.0))
    return result


def efficiency_ratio_series(values: Sequence[float], *, window: int) -> list[float]:
    normalized_window = max(int(window), 1)
    result: list[float] = []
    for index, value in enumerate(values):
        start = max(index - normalized_window, 0)
        path_values = [float(item) for item in values[start:index + 1]]
        if len(path_values) < 2:
            result.append(0.0)
            continue
        net_move = abs(float(value) - path_values[0])
        path_length = sum(
            abs(path_values[offset] - path_values[offset - 1])
            for offset in range(1, len(path_values))
        )
        result.append(safe_divide(net_move, path_length, default=0.0))
    return result


def _log_return_series(values: Sequence[float]) -> list[float]:
    result = [0.0]
    for index in range(1, len(values)):
        current = float(values[index])
        previous = float(values[index - 1])
        if current <= EPSILON or previous <= EPSILON:
            result.append(0.0)
            continue
        result.append(math.log(current / previous))
    return result


def _window_series(
    values: Sequence[float],
    *,
    window: int,
    include_current: bool,
) -> list[list[float]]:
    normalized_window = max(int(window), 1)
    result: list[list[float]] = []
    for index in range(len(values)):
        end = index + 1 if include_current else index
        start = max(end - normalized_window, 0)
        window_values = [float(item) for item in values[start:end]]
        if not window_values:
            window_values = [float(values[index])]
        result.append(window_values)
    return result
