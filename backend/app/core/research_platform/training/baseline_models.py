from __future__ import annotations

from statistics import median

import numpy as np

from app.core.research_platform.dataset.constants import LABEL_VECTOR_FIELDS

from .joint_forecasts import FORECAST_SAMPLE_COUNT
from .joint_forecasts import gaussian_joint_nll


TARGET_FIELDS = LABEL_VECTOR_FIELDS
EMPIRICAL_JOINT_MODEL = 'empirical_joint_distribution_v1'
INDEPENDENT_MARGINAL_MODEL = 'independent_marginal_distribution_v1'
POINT_BASELINE_MODEL = 'zero_body_median_shadow_v1'
MIN_VARIANCE = 1e-6
DIAGONAL_SHRINKAGE = 0.1


def build_empirical_joint_baseline(
    *,
    train_rows: list[dict[str, object]],
    test_rows: list[dict[str, object]],
) -> dict[str, object]:
    targets = _collect_targets(train_rows)
    forecast_mean = _mean_row(targets)
    covariance = _covariance_matrix(targets)
    sample_sets = [
        _cycle_joint_samples(targets, offset=test_index)
        for test_index, _ in enumerate(test_rows)
    ]
    return _build_prediction_bundle(
        test_rows=test_rows,
        forecast_mean=forecast_mean,
        sample_sets=sample_sets,
        covariance=covariance,
    )


def build_independent_marginal_baseline(
    *,
    train_rows: list[dict[str, object]],
    test_rows: list[dict[str, object]],
) -> dict[str, object]:
    marginals = _collect_marginals(train_rows)
    forecast_mean = {
        field_name: float(sum(values) / len(values))
        for field_name, values in marginals.items()
    }
    covariance = _diagonal_covariance(marginals)
    sample_sets = [
        _independent_sample_set(marginals, offset=test_index)
        for test_index, _ in enumerate(test_rows)
    ]
    return _build_prediction_bundle(
        test_rows=test_rows,
        forecast_mean=forecast_mean,
        sample_sets=sample_sets,
        covariance=covariance,
    )


def build_point_baseline(
    *,
    train_rows: list[dict[str, object]],
    test_rows: list[dict[str, object]],
) -> dict[str, object]:
    marginals = _collect_marginals(train_rows)
    forecast_mean = {
        'r_open': 0.0,
        'r_close': 0.0,
        'u': float(median(marginals['u'])),
        'd': float(median(marginals['d'])),
    }
    covariance = _diagonal_covariance(marginals)
    sample_sets = [
        [dict(forecast_mean) for _ in range(FORECAST_SAMPLE_COUNT)]
        for _ in test_rows
    ]
    return _build_prediction_bundle(
        test_rows=test_rows,
        forecast_mean=forecast_mean,
        sample_sets=sample_sets,
        covariance=covariance,
    )


def _build_prediction_bundle(
    *,
    test_rows: list[dict[str, object]],
    forecast_mean: dict[str, float],
    sample_sets: list[list[dict[str, float]]],
    covariance: np.ndarray,
) -> dict[str, object]:
    forecast_rows = [
        _attach_forecast_fields(row=test_row, forecast_mean=forecast_mean)
        for test_row in test_rows
    ]
    joint_nll_values = [
        gaussian_joint_nll(
            observation=_row_to_vector(test_row),
            mean_vector=_dict_to_vector(forecast_mean),
            covariance=covariance,
        )
        for test_row in test_rows
    ]
    return {
        'forecast_rows': forecast_rows,
        'sample_sets': sample_sets,
        'joint_nll_values': joint_nll_values,
        'prediction_summary': {
            'sample_count': FORECAST_SAMPLE_COUNT,
            'forecast_mean': dict(forecast_mean),
        },
    }


def _collect_targets(rows: list[dict[str, object]]) -> list[dict[str, float]]:
    if not rows:
        raise ValueError('baseline construction requires non-empty train_rows')
    return [
        {field_name: float(row[field_name]) for field_name in TARGET_FIELDS}
        for row in rows
    ]


def _collect_marginals(rows: list[dict[str, object]]) -> dict[str, list[float]]:
    targets = _collect_targets(rows)
    return {
        field_name: [float(row[field_name]) for row in targets]
        for field_name in TARGET_FIELDS
    }


def _mean_row(targets: list[dict[str, float]]) -> dict[str, float]:
    return {
        field_name: float(sum(row[field_name] for row in targets) / len(targets))
        for field_name in TARGET_FIELDS
    }


def _covariance_matrix(targets: list[dict[str, float]]) -> np.ndarray:
    values = np.asarray([_dict_to_vector(row) for row in targets], dtype=float)
    covariance = np.atleast_2d(np.cov(values, rowvar=False, bias=values.shape[0] <= 1))
    return _stabilize_covariance(covariance)


def _diagonal_covariance(marginals: dict[str, list[float]]) -> np.ndarray:
    variances = [
        _variance(values)
        for values in marginals.values()
    ]
    return np.diag(np.asarray(variances, dtype=float))


def _stabilize_covariance(covariance: np.ndarray) -> np.ndarray:
    if covariance.shape != (len(TARGET_FIELDS), len(TARGET_FIELDS)):
        covariance = np.eye(len(TARGET_FIELDS), dtype=float) * MIN_VARIANCE
    diagonal = np.diag(np.maximum(np.diag(covariance), MIN_VARIANCE))
    stabilized = ((1.0 - DIAGONAL_SHRINKAGE) * covariance) + (DIAGONAL_SHRINKAGE * diagonal)
    return stabilized + (np.eye(len(TARGET_FIELDS), dtype=float) * MIN_VARIANCE)


def _cycle_joint_samples(
    targets: list[dict[str, float]],
    *,
    offset: int,
) -> list[dict[str, float]]:
    count = len(targets)
    return [
        dict(targets[(offset + sample_index) % count])
        for sample_index in range(FORECAST_SAMPLE_COUNT)
    ]


def _independent_sample_set(
    marginals: dict[str, list[float]],
    *,
    offset: int,
) -> list[dict[str, float]]:
    return [
        {
            field_name: float(values[(offset + ((field_index + 1) * sample_index)) % len(values)])
            for field_index, (field_name, values) in enumerate(marginals.items())
        }
        for sample_index in range(FORECAST_SAMPLE_COUNT)
    ]


def _attach_forecast_fields(
    *,
    row: dict[str, object],
    forecast_mean: dict[str, float],
) -> dict[str, object]:
    return {
        **row,
        **{f'forecast_{field_name}': float(value) for field_name, value in forecast_mean.items()},
    }


def _row_to_vector(row: dict[str, object]) -> np.ndarray:
    return np.asarray([float(row[field_name]) for field_name in TARGET_FIELDS], dtype=float)


def _dict_to_vector(row: dict[str, float]) -> np.ndarray:
    return np.asarray([float(row[field_name]) for field_name in TARGET_FIELDS], dtype=float)


def _variance(values: list[float]) -> float:
    if len(values) <= 1:
        return MIN_VARIANCE
    mean_value = sum(values) / len(values)
    variance = sum((value - mean_value) ** 2 for value in values) / len(values)
    return max(float(variance), MIN_VARIANCE)
