from __future__ import annotations

import math

import numpy as np

from app.core.research_platform.dataset.constants import LABEL_VECTOR_FIELDS

from .feature_tensors import build_feature_dataset


RIDGE_ALPHA = 1.0
FORECAST_SAMPLE_COUNT = 32
TARGET_FIELDS = LABEL_VECTOR_FIELDS
TARGET_DIMENSION = len(TARGET_FIELDS)
COVARIANCE_EPSILON = 1e-6
DIAGONAL_SHRINKAGE = 0.1


def build_origin_forecast_bundle(
    *,
    storage,
    fit_rows: list[dict[str, object]],
    scored_rows: list[dict[str, object]],
    training_seed: int,
    origin_ts: int,
) -> dict[str, object]:
    if not fit_rows:
        raise ValueError(f'origin {origin_ts} requires at least one fit row')
    fit_dataset = build_feature_dataset(storage=storage, rows=fit_rows)
    scored_dataset = build_feature_dataset(storage=storage, rows=scored_rows)
    model = fit_joint_linear_gaussian(
        feature_matrix=fit_dataset['matrix'],
        targets=_target_matrix(fit_rows),
    )
    rng = np.random.default_rng(int(training_seed) + int(origin_ts))
    predictions = [
        _predict_distribution(model=model, feature_vector=feature_vector, rng=rng)
        for feature_vector in scored_dataset['matrix']
    ]
    return {
        'predicted_rows': [
            _attach_forecast_fields(row=row, mean_vector=prediction['mean'])
            for row, prediction in zip(scored_rows, predictions)
        ],
        'sample_sets': [_sample_matrix_to_rows(prediction['samples']) for prediction in predictions],
        'joint_nll_values': [
            gaussian_joint_nll(
                observation=_target_vector(row),
                mean_vector=prediction['mean'],
                covariance=model['covariance'],
            )
            for row, prediction in zip(scored_rows, predictions)
        ],
        'generation_summary': {
            'feature_source': 'research_second_states',
            'input_window_shape': list(scored_dataset['tensors'][0]['window_shape']),
            'summary_feature_count': int(scored_dataset['summary_feature_count']),
            'sample_count': FORECAST_SAMPLE_COUNT,
            'train_sample_count': len(fit_rows),
        },
    }


def fit_joint_linear_gaussian(*, feature_matrix: np.ndarray, targets: np.ndarray) -> dict[str, np.ndarray]:
    feature_mean = feature_matrix.mean(axis=0)
    feature_scale = np.where(feature_matrix.std(axis=0) > 1e-9, feature_matrix.std(axis=0), 1.0)
    standardized = (feature_matrix - feature_mean) / feature_scale
    design = np.column_stack([np.ones(standardized.shape[0]), standardized])
    penalty = np.eye(design.shape[1], dtype=float)
    penalty[0, 0] = 0.0
    coefficients = np.linalg.solve(
        (design.T @ design) + (RIDGE_ALPHA * penalty),
        design.T @ targets,
    )
    residuals = targets - (design @ coefficients)
    return {
        'feature_mean': feature_mean,
        'feature_scale': feature_scale,
        'coefficients': coefficients,
        'covariance': _estimate_covariance(residuals=residuals, targets=targets),
    }


def gaussian_joint_nll(
    *,
    observation: np.ndarray,
    mean_vector: np.ndarray,
    covariance: np.ndarray,
) -> float:
    diff = observation - mean_vector
    sign, log_det = np.linalg.slogdet(covariance)
    if sign <= 0:
        covariance = covariance + (np.eye(TARGET_DIMENSION, dtype=float) * COVARIANCE_EPSILON)
        _, log_det = np.linalg.slogdet(covariance)
    precision = np.linalg.pinv(covariance)
    quadratic = float(diff.T @ precision @ diff)
    return 0.5 * ((TARGET_DIMENSION * math.log(2.0 * math.pi)) + log_det + quadratic)


def _predict_distribution(
    *,
    model: dict[str, np.ndarray],
    feature_vector: np.ndarray,
    rng: np.random.Generator,
) -> dict[str, np.ndarray]:
    standardized = (feature_vector - model['feature_mean']) / model['feature_scale']
    design = np.concatenate([np.ones(1, dtype=float), standardized])
    mean_vector = np.maximum(design @ model['coefficients'], _support_floor())
    samples = rng.multivariate_normal(
        mean=mean_vector,
        cov=model['covariance'],
        size=FORECAST_SAMPLE_COUNT,
    )
    samples[:, 2:] = np.clip(samples[:, 2:], a_min=0.0, a_max=None)
    return {'mean': mean_vector, 'samples': samples}


def _estimate_covariance(*, residuals: np.ndarray, targets: np.ndarray) -> np.ndarray:
    source = residuals if residuals.shape[0] > 1 else targets
    covariance = np.atleast_2d(np.cov(source, rowvar=False, bias=source.shape[0] <= 1))
    if covariance.shape != (TARGET_DIMENSION, TARGET_DIMENSION):
        covariance = np.eye(TARGET_DIMENSION, dtype=float) * COVARIANCE_EPSILON
    diagonal = np.diag(np.maximum(np.diag(covariance), COVARIANCE_EPSILON))
    stabilized = ((1.0 - DIAGONAL_SHRINKAGE) * covariance) + (DIAGONAL_SHRINKAGE * diagonal)
    return stabilized + (np.eye(TARGET_DIMENSION, dtype=float) * COVARIANCE_EPSILON)


def _support_floor() -> np.ndarray:
    return np.asarray([-np.inf, -np.inf, 0.0, 0.0], dtype=float)


def _sample_matrix_to_rows(sample_matrix: np.ndarray) -> list[dict[str, float]]:
    return [_vector_to_row(sample_vector) for sample_vector in sample_matrix]


def _attach_forecast_fields(*, row: dict[str, object], mean_vector: np.ndarray) -> dict[str, object]:
    return {
        **row,
        **{f'forecast_{field_name}': float(value) for field_name, value in zip(TARGET_FIELDS, mean_vector)},
    }


def _vector_to_row(vector: np.ndarray) -> dict[str, float]:
    return {
        field_name: float(value)
        for field_name, value in zip(TARGET_FIELDS, vector)
    }


def _target_vector(row: dict[str, object]) -> np.ndarray:
    return np.asarray([float(row[field_name]) for field_name in TARGET_FIELDS], dtype=float)


def _target_matrix(rows: list[dict[str, object]]) -> np.ndarray:
    return np.asarray([_target_vector(row) for row in rows], dtype=float)
