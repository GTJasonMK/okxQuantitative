from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from .logistic_model import evaluate_binary_classifier, train_logistic_head
from .models import TimeOrderedSplit, TrendModelBundle
from .sample_matrix import TrainingMatrix


DEFAULT_TRAIN_RATIO = 0.7
DEFAULT_VALIDATION_RATIO = 0.15


def build_time_splits(
    second_buckets: tuple[int, ...],
    *,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
    validation_ratio: float = DEFAULT_VALIDATION_RATIO,
) -> TimeOrderedSplit:
    total_count = len(second_buckets)
    if total_count < 3:
        raise ValueError("at least 3 rows are required for train/validation/test splits")
    train_count = max(int(total_count * train_ratio), 1)
    validation_count = max(int(total_count * validation_ratio), 1)
    if train_count + validation_count >= total_count:
        train_count = max(total_count - 2, 1)
        validation_count = 1
    validation_start = train_count
    test_start = train_count + validation_count
    return TimeOrderedSplit(
        train_indices=tuple(range(train_count)),
        validation_indices=tuple(range(validation_start, test_start)),
        test_indices=tuple(range(test_start, total_count)),
    )


def _resolve_feature_indices(matrix: TrainingMatrix, selected_feature_names: tuple[str, ...]) -> tuple[int, ...]:
    index_by_name = {name: index for index, name in enumerate(matrix.feature_names)}
    try:
        return tuple(index_by_name[name] for name in selected_feature_names)
    except KeyError as exc:
        raise ValueError(f"missing selected feature in matrix: {exc.args[0]}") from exc


def _slice_rows(matrix: TrainingMatrix, row_indices: tuple[int, ...], feature_indices: tuple[int, ...]) -> np.ndarray:
    return np.asarray(
        [[matrix.rows[row_index][feature_index] for feature_index in feature_indices] for row_index in row_indices],
        dtype=float,
    )


def _slice_labels(labels: tuple[int, ...], row_indices: tuple[int, ...]) -> np.ndarray:
    return np.asarray([labels[row_index] for row_index in row_indices], dtype=float)


def _fit_standardizer(train_rows: np.ndarray) -> tuple[tuple[float, ...], tuple[float, ...]]:
    means = np.mean(train_rows, axis=0)
    stds = np.std(train_rows, axis=0)
    if np.any(stds <= 0.0):
        raise ValueError("zero variance in training split")
    return tuple(float(value) for value in means.tolist()), tuple(float(value) for value in stds.tolist())


def _standardize(rows: np.ndarray, means: tuple[float, ...], stds: tuple[float, ...]) -> np.ndarray:
    return (rows - np.asarray(means, dtype=float)) / np.asarray(stds, dtype=float)


def _balanced_positive_weight(labels: np.ndarray) -> float:
    positive_count = float(np.sum(labels > 0.5))
    negative_count = float(np.sum(labels <= 0.5))
    if positive_count <= 0.0 or negative_count <= 0.0:
        raise ValueError("class collapse in training labels")
    return negative_count / positive_count


def train_trend_model(
    matrix: TrainingMatrix,
    selection,
    *,
    horizon_minutes: int,
    reversal_threshold_floor: float,
) -> TrendModelBundle:
    selected_feature_names = tuple(selection.feature_names)
    if not selected_feature_names:
        raise ValueError("no selected features available for model training")
    splits = build_time_splits(matrix.second_buckets)
    feature_indices = _resolve_feature_indices(matrix, selected_feature_names)
    train_rows = _slice_rows(matrix, splits.train_indices, feature_indices)
    validation_rows = _slice_rows(matrix, splits.validation_indices, feature_indices)
    test_rows = _slice_rows(matrix, splits.test_indices, feature_indices)
    train_means, train_stds = _fit_standardizer(train_rows)
    standardized_train = _standardize(train_rows, train_means, train_stds)
    standardized_validation = _standardize(validation_rows, train_means, train_stds)
    standardized_test = _standardize(test_rows, train_means, train_stds)
    top_train = _slice_labels(matrix.top_labels, splits.train_indices)
    bottom_train = _slice_labels(matrix.bottom_labels, splits.train_indices)
    top_head = train_logistic_head(standardized_train, top_train, positive_class_weight=_balanced_positive_weight(top_train))
    bottom_head = train_logistic_head(standardized_train, bottom_train, positive_class_weight=_balanced_positive_weight(bottom_train))
    return TrendModelBundle(
        trained_at=datetime.now(timezone.utc).isoformat(),
        horizon_minutes=int(horizon_minutes),
        reversal_threshold_floor=float(reversal_threshold_floor),
        feature_names=selected_feature_names,
        train_means=train_means,
        train_stds=train_stds,
        top_head=top_head,
        bottom_head=bottom_head,
        top_validation=evaluate_binary_classifier(standardized_validation, _slice_labels(matrix.top_labels, splits.validation_indices), top_head),
        bottom_validation=evaluate_binary_classifier(standardized_validation, _slice_labels(matrix.bottom_labels, splits.validation_indices), bottom_head),
        top_test=evaluate_binary_classifier(standardized_test, _slice_labels(matrix.top_labels, splits.test_indices), top_head),
        bottom_test=evaluate_binary_classifier(standardized_test, _slice_labels(matrix.bottom_labels, splits.test_indices), bottom_head),
    )
