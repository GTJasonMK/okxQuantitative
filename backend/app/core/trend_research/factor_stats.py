from __future__ import annotations

import math
from statistics import fmean
from typing import Iterable

import numpy as np


MIN_SERIES_LENGTH = 3
MIN_WINDOW_SIZE = 4
ROLLING_WINDOW_DIVISOR = 3
ROLLING_WINDOW_STEP_DIVISOR = 2
ZERO_TOLERANCE = 1e-9


def build_extrema_label_signal(labels) -> list[float]:
    signal = []
    for label in labels:
        if label.swing_bottom_confirmed:
            signal.append(1.0)
            continue
        if label.swing_top_confirmed:
            signal.append(-1.0)
            continue
        signal.append(0.0)
    return signal


def compute_spearman_rank_ic(
    factor_values: Iterable[float],
    label_signal: Iterable[float],
) -> float | None:
    factor_array = _to_float_array(factor_values)
    label_array = _to_float_array(label_signal)
    if not _is_valid_series_pair(factor_array, label_array):
        return None

    ranked_factor = _average_ranks(factor_array)
    ranked_label = _average_ranks(label_array)
    return _pearson_correlation(ranked_factor, ranked_label)


def compute_stability_score(
    factor_values: Iterable[float],
    label_signal: Iterable[float],
    overall_ic: float,
) -> float:
    factor_array = _to_float_array(factor_values)
    label_array = _to_float_array(label_signal)
    rolling_ic = _collect_rolling_ic(factor_array, label_array)
    if not rolling_ic:
        return abs(overall_ic)
    if math.isclose(overall_ic, 0.0, abs_tol=ZERO_TOLERANCE):
        return 0.0

    mean_abs_ic = fmean(abs(value) for value in rolling_ic)
    consistent = sum(1 for value in rolling_ic if _same_direction(value, overall_ic))
    sign_consistency = consistent / len(rolling_ic)
    return float(min(max(mean_abs_ic * sign_consistency, 0.0), 1.0))


def _collect_rolling_ic(factor_array: np.ndarray, label_array: np.ndarray) -> list[float]:
    values = []
    for start, stop in _iter_window_bounds(len(factor_array)):
        rho = compute_spearman_rank_ic(factor_array[start:stop], label_array[start:stop])
        if rho is not None:
            values.append(rho)
    return values


def _iter_window_bounds(length: int) -> list[tuple[int, int]]:
    if length < MIN_WINDOW_SIZE:
        return []

    window_size = max(length // ROLLING_WINDOW_DIVISOR, MIN_WINDOW_SIZE)
    step = max(window_size // ROLLING_WINDOW_STEP_DIVISOR, 1)
    bounds: list[tuple[int, int]] = []
    start = 0
    while start + window_size <= length:
        bounds.append((start, start + window_size))
        start += step

    tail = (length - window_size, length)
    if not bounds or bounds[-1] != tail:
        bounds.append(tail)
    return bounds


def _same_direction(left: float, right: float) -> bool:
    if math.isclose(left, 0.0, abs_tol=ZERO_TOLERANCE):
        return False
    return math.copysign(1.0, left) == math.copysign(1.0, right)


def _to_float_array(values: Iterable[float]) -> np.ndarray:
    return np.asarray(list(values), dtype=float)


def _is_valid_series_pair(left: np.ndarray, right: np.ndarray) -> bool:
    if left.size != right.size or left.size < MIN_SERIES_LENGTH:
        return False
    return _has_variation(left) and _has_variation(right)


def _has_variation(values: np.ndarray) -> bool:
    return not np.allclose(values, values[0], atol=ZERO_TOLERANCE)


def _average_ranks(values: np.ndarray) -> np.ndarray:
    order = np.argsort(values, kind='mergesort')
    ranks = np.empty(values.size, dtype=float)
    index = 0
    while index < values.size:
        start = index
        current = values[order[index]]
        while index + 1 < values.size and math.isclose(values[order[index + 1]], current, abs_tol=ZERO_TOLERANCE):
            index += 1
        average_rank = ((start + index) / 2.0) + 1.0
        ranks[order[start:index + 1]] = average_rank
        index += 1
    return ranks


def _pearson_correlation(left: np.ndarray, right: np.ndarray) -> float | None:
    centered_left = left - np.mean(left)
    centered_right = right - np.mean(right)
    denominator = float(np.linalg.norm(centered_left) * np.linalg.norm(centered_right))
    if denominator <= ZERO_TOLERANCE:
        return None
    numerator = float(np.dot(centered_left, centered_right))
    return float(np.clip(numerator / denominator, -1.0, 1.0))
