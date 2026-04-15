from __future__ import annotations

import math

import numpy as np

from .shift_state import SHIFT_STATE_FIELDS_V1
from .shift_state import parse_shift_state_blob


MMD_METHOD = 'linear_rbf_mmd_permutation_v1'
MMD_P_VALUE_THRESHOLD = 0.05
MMD_PERMUTATION_COUNT = 64
MMD_MIN_SAMPLE_COUNT = 2
MMD_RANDOM_SEED = 7
MMD_BANDWIDTH_FLOOR = 1e-6
ROBUST_SCALE_FLOOR = 1e-6


def run_mmd_check(
    *,
    labeled_shift_rows: list[dict[str, object]],
    census_shift_rows: list[dict[str, object]],
) -> dict[str, object]:
    source_matrix = _build_source_matrix(labeled_shift_rows)
    target_matrix = _build_target_matrix(census_shift_rows)
    if min(len(source_matrix), len(target_matrix)) < MMD_MIN_SAMPLE_COUNT:
        return _build_failed_mmd_result(reason='insufficient_samples')
    standardized_source, standardized_target, bandwidth = _prepare_standardized_inputs(
        source_matrix=source_matrix,
        target_matrix=target_matrix,
    )
    observed = _linear_rbf_mmd_statistic(
        source_matrix=standardized_source,
        target_matrix=standardized_target,
        bandwidth=bandwidth,
    )
    permutation_stats = _build_permutation_distribution(
        source_matrix=standardized_source,
        target_matrix=standardized_target,
        bandwidth=bandwidth,
    )
    p_value = (1.0 + float(np.sum(permutation_stats >= observed))) / (MMD_PERMUTATION_COUNT + 1.0)
    return {
        'name': 'mmd_test',
        'method': MMD_METHOD,
        'status': 'acceptable' if p_value >= MMD_P_VALUE_THRESHOLD else 'failed',
        'score': p_value,
        'threshold': MMD_P_VALUE_THRESHOLD,
        'score_direction': 'greater_is_better',
        'statistic_name': 'linear_time_mmd2',
        'statistic': observed,
        'p_value': p_value,
        'bandwidth': bandwidth,
        'permutation_count': MMD_PERMUTATION_COUNT,
        'feature_names': list(SHIFT_STATE_FIELDS_V1),
    }


def _build_source_matrix(rows: list[dict[str, object]]) -> np.ndarray:
    return np.asarray([
        [float(row['shift_state'][feature_name]) for feature_name in SHIFT_STATE_FIELDS_V1]
        for row in rows
    ], dtype=np.float64)


def _build_target_matrix(rows: list[dict[str, object]]) -> np.ndarray:
    return np.asarray([
        [float(parse_shift_state_blob(row)[feature_name]) for feature_name in SHIFT_STATE_FIELDS_V1]
        for row in rows
    ], dtype=np.float64)


def _prepare_standardized_inputs(
    *,
    source_matrix: np.ndarray,
    target_matrix: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float]:
    combined = np.vstack([source_matrix, target_matrix])
    median = np.median(combined, axis=0)
    mad = np.median(np.abs(combined - median), axis=0)
    scale = np.where(mad > ROBUST_SCALE_FLOOR, mad, 1.0)
    standardized = (combined - median) / scale
    bandwidth = _estimate_bandwidth(standardized)
    return standardized[: len(source_matrix)], standardized[len(source_matrix) :], bandwidth


def _estimate_bandwidth(matrix: np.ndarray) -> float:
    if len(matrix) < 2:
        return 1.0
    adjacent = matrix[1:] - matrix[:-1]
    squared_distances = np.sum(adjacent * adjacent, axis=1)
    positive = squared_distances[squared_distances > MMD_BANDWIDTH_FLOOR]
    if len(positive) == 0:
        return 1.0
    return max(float(math.sqrt(float(np.median(positive)))), 1.0)


def _linear_rbf_mmd_statistic(
    *,
    source_matrix: np.ndarray,
    target_matrix: np.ndarray,
    bandwidth: float,
) -> float:
    pair_count = min(len(source_matrix), len(target_matrix)) // 2
    if pair_count == 0:
        return 0.0
    source_even = source_matrix[: pair_count * 2 : 2]
    source_odd = source_matrix[1 : pair_count * 2 : 2]
    target_even = target_matrix[: pair_count * 2 : 2]
    target_odd = target_matrix[1 : pair_count * 2 : 2]
    return float(np.mean(
        _rbf_kernel(source_even, source_odd, bandwidth)
        + _rbf_kernel(target_even, target_odd, bandwidth)
        - _rbf_kernel(source_even, target_odd, bandwidth)
        - _rbf_kernel(source_odd, target_even, bandwidth)
    ))


def _rbf_kernel(lhs: np.ndarray, rhs: np.ndarray, bandwidth: float) -> np.ndarray:
    diff = lhs - rhs
    squared_norm = np.sum(diff * diff, axis=1)
    gamma = 1.0 / max(2.0 * (bandwidth ** 2), MMD_BANDWIDTH_FLOOR)
    return np.exp(-gamma * squared_norm)


def _build_permutation_distribution(
    *,
    source_matrix: np.ndarray,
    target_matrix: np.ndarray,
    bandwidth: float,
) -> np.ndarray:
    combined = np.vstack([source_matrix, target_matrix])
    source_count = len(source_matrix)
    rng = np.random.default_rng(MMD_RANDOM_SEED)
    statistics = []
    for _ in range(MMD_PERMUTATION_COUNT):
        shuffled = combined[rng.permutation(len(combined))]
        statistics.append(
            _linear_rbf_mmd_statistic(
                source_matrix=shuffled[:source_count],
                target_matrix=shuffled[source_count:],
                bandwidth=bandwidth,
            )
        )
    return np.asarray(statistics, dtype=np.float64)


def _build_failed_mmd_result(*, reason: str) -> dict[str, object]:
    return {
        'name': 'mmd_test',
        'method': MMD_METHOD,
        'status': 'failed',
        'score': 0.0,
        'threshold': MMD_P_VALUE_THRESHOLD,
        'score_direction': 'greater_is_better',
        'statistic_name': 'linear_time_mmd2',
        'statistic': None,
        'p_value': 0.0,
        'bandwidth': None,
        'permutation_count': MMD_PERMUTATION_COUNT,
        'feature_names': list(SHIFT_STATE_FIELDS_V1),
        'reason': reason,
    }
