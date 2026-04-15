from __future__ import annotations

import math

from app.core.research_platform.dataset.constants import LABEL_VECTOR_FIELDS

from .diagnostics_marginals import build_marginal_coverage, build_weighted_pit

DIAGNOSTIC_BIN_COUNT = 20
PRE_RANK_NAMES = (
    'level_prerank',
    'asymmetry_prerank',
    'body_shadow_prerank',
)
PRICE_RECONSTRUCTION_NAMES = (
    'open_bps_error',
    'high_bps_error',
    'low_bps_error',
    'close_bps_error',
    'range_width_error',
    'body_direction_error',
)


def build_diagnostics_bundle(
    *,
    weight_mode: str,
    observations: list[dict[str, float]],
    samples: list[list[dict[str, float]]],
    normalized_weights: list[float],
) -> dict[str, object]:
    return {
        'weight_mode': weight_mode,
        'weight_reference_distribution': 'Q' if weight_mode == 'unweighted' else 'P_over_Q',
        'weight_normalization': {
            'formula': 'w_i^norm = w_i / sum_j w_j',
            'scope': 'diagnostics_only',
            'applies_to': [
                'marginal_coverage',
                'weighted_pit',
                'multivariate_rank_histogram',
                'prerank_rank_statistics',
                'price_reconstruction_diagnostics',
            ],
        },
        'multivariate_rank_histogram': _build_rank_histogram(
            observations=observations,
            samples=samples,
            normalized_weights=normalized_weights,
        ),
        'marginal_coverage': build_marginal_coverage(
            observations=observations,
            samples=samples,
            normalized_weights=normalized_weights,
        ),
        'weighted_pit': build_weighted_pit(
            observations=observations,
            samples=samples,
            normalized_weights=normalized_weights,
        ),
        'prerank_diagnostics': _build_prerank_diagnostics(
            observations=observations,
            samples=samples,
            normalized_weights=normalized_weights,
        ),
        'price_reconstruction_diagnostics': _build_price_reconstruction_diagnostics(
            observations=observations,
            samples=samples,
            normalized_weights=normalized_weights,
        ),
    }


def _build_rank_histogram(
    *,
    observations: list[dict[str, float]],
    samples: list[list[dict[str, float]]],
    normalized_weights: list[float],
) -> dict[str, object]:
    bin_counts = [0.0] * DIAGNOSTIC_BIN_COUNT
    for observation, sample_set, weight in zip(observations, samples, normalized_weights):
        bin_index = _rank_histogram_bin(observation=observation, sample_set=sample_set)
        bin_counts[bin_index] += weight
    return {
        'rank_scheme': 'band_depth_rank_v1',
        'bin_count': DIAGNOSTIC_BIN_COUNT,
        'bin_counts': bin_counts,
    }


def _rank_histogram_bin(
    *,
    observation: dict[str, float],
    sample_set: list[dict[str, float]],
) -> int:
    depth_observation = _modified_band_depth(point=observation, sample_set=sample_set)
    member_depths = [_modified_band_depth(point=sample, sample_set=sample_set) for sample in sample_set]
    combined = member_depths + [depth_observation]
    less_count = sum(depth < depth_observation for depth in combined)
    equal_count = sum(depth == depth_observation for depth in combined)
    first_rank = less_count + 1
    last_rank = less_count + equal_count
    average_rank = (first_rank + last_rank) / 2.0
    percentile = (average_rank - 0.5) / len(combined)
    return min(int(percentile * DIAGNOSTIC_BIN_COUNT), DIAGNOSTIC_BIN_COUNT - 1)


def _modified_band_depth(
    *,
    point: dict[str, float],
    sample_set: list[dict[str, float]],
) -> float:
    if len(sample_set) < 2:
        return 1.0
    pair_scores = []
    for left_index in range(len(sample_set) - 1):
        for right_index in range(left_index + 1, len(sample_set)):
            pair_scores.append(
                _pair_band_containment(
                    point=point,
                    left=sample_set[left_index],
                    right=sample_set[right_index],
                )
            )
    return sum(pair_scores) / len(pair_scores)


def _pair_band_containment(
    *,
    point: dict[str, float],
    left: dict[str, float],
    right: dict[str, float],
) -> float:
    dimensions = LABEL_VECTOR_FIELDS
    contained = [
        _within_band(
            value=float(point[dimension]),
            lhs=float(left[dimension]),
            rhs=float(right[dimension]),
        )
        for dimension in dimensions
    ]
    return sum(contained) / len(contained)


def _within_band(*, value: float, lhs: float, rhs: float) -> float:
    lower = min(lhs, rhs)
    upper = max(lhs, rhs)
    return 1.0 if lower <= value <= upper else 0.0


def _build_prerank_diagnostics(
    *,
    observations: list[dict[str, float]],
    samples: list[list[dict[str, float]]],
    normalized_weights: list[float],
) -> dict[str, object]:
    return {
        'definition_version': 'multicalibration_v1',
        'functions': list(PRE_RANK_NAMES),
        'stats': {
            name: _weighted_error_stats(
                observed_values=[_compute_prerank_value(name=name, row=row) for row in observations],
                predicted_values=[_compute_prerank_value(name=name, row=_mean_sample(sample_set)) for sample_set in samples],
                normalized_weights=normalized_weights,
            )
            for name in PRE_RANK_NAMES
        },
    }


def _build_price_reconstruction_diagnostics(
    *,
    observations: list[dict[str, float]],
    samples: list[list[dict[str, float]]],
    normalized_weights: list[float],
) -> dict[str, object]:
    return {
        'targets': list(PRICE_RECONSTRUCTION_NAMES),
        'metrics': {
            name: _weighted_error_stats(
                observed_values=[_compute_price_target(name=name, row=row) for row in observations],
                predicted_values=[_compute_price_target(name=name, row=_mean_sample(sample_set)) for sample_set in samples],
                normalized_weights=normalized_weights,
            )
            for name in PRICE_RECONSTRUCTION_NAMES
        },
    }


def _weighted_error_stats(
    *,
    observed_values: list[float],
    predicted_values: list[float],
    normalized_weights: list[float],
) -> dict[str, float]:
    errors = [predicted - observed for observed, predicted in zip(observed_values, predicted_values)]
    return {
        'weighted_mean_abs_error': sum(weight * abs(error) for weight, error in zip(normalized_weights, errors)),
        'weighted_bias': sum(weight * error for weight, error in zip(normalized_weights, errors)),
    }


def _compute_prerank_value(*, name: str, row: dict[str, float]) -> float:
    if name == 'level_prerank':
        return abs(float(row['r_open'])) + abs(float(row['r_close'])) + float(row['u']) + float(row['d'])
    if name == 'asymmetry_prerank':
        return float(row['u']) - float(row['d'])
    return abs(float(row['r_close']) - float(row['r_open'])) - (float(row['u']) + float(row['d']))


def _compute_price_target(*, name: str, row: dict[str, float]) -> float:
    if name == 'open_bps_error':
        return float(row['r_open']) * 1e4
    if name == 'high_bps_error':
        return _high(row) * 1e4
    if name == 'low_bps_error':
        return _low(row) * 1e4
    if name == 'close_bps_error':
        return float(row['r_close']) * 1e4
    if name == 'range_width_error':
        return (_high(row) - _low(row)) * 1e4
    return float(_body_direction(row))


def _mean_sample(sample_set: list[dict[str, float]]) -> dict[str, float]:
    keys = LABEL_VECTOR_FIELDS
    return {
        key: sum(float(sample[key]) for sample in sample_set) / len(sample_set)
        for key in keys
    }


def _high(row: dict[str, float]) -> float:
    return max(float(row['r_open']), float(row['r_close'])) + float(row['u'])


def _low(row: dict[str, float]) -> float:
    return min(float(row['r_open']), float(row['r_close'])) - float(row['d'])


def _body_direction(row: dict[str, float]) -> int:
    body = float(row['r_close']) - float(row['r_open'])
    if math.isclose(body, 0.0):
        return 0
    return 1 if body > 0 else -1
