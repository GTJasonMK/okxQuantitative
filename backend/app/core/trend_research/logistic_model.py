from __future__ import annotations

import numpy as np

from .models import BinaryClassificationMetrics, LogisticModelHead


DEFAULT_LEARNING_RATE = 0.1
DEFAULT_ITERATIONS = 400
DEFAULT_L2_REGULARIZATION = 0.01
LOGIT_CLIP = 40.0
LOG_LOSS_EPSILON = 1e-9


def _as_feature_matrix(features) -> np.ndarray:
    matrix = np.asarray(features, dtype=float)
    if matrix.ndim != 2:
        raise ValueError("features must be a 2D matrix")
    return matrix


def _as_label_vector(labels) -> np.ndarray:
    vector = np.asarray(labels, dtype=float)
    if vector.ndim != 1:
        raise ValueError("labels must be a 1D vector")
    return vector


def _sigmoid(logits: np.ndarray) -> np.ndarray:
    clipped = np.clip(logits, -LOGIT_CLIP, LOGIT_CLIP)
    return 1.0 / (1.0 + np.exp(-clipped))


def _sample_weights(labels: np.ndarray, positive_class_weight: float, negative_class_weight: float) -> np.ndarray:
    return np.where(labels > 0.5, positive_class_weight, negative_class_weight)


def predict_probabilities(features, head: LogisticModelHead) -> np.ndarray:
    matrix = _as_feature_matrix(features)
    weights = np.asarray(head.weights, dtype=float)
    return _sigmoid(matrix @ weights + float(head.intercept))


def train_logistic_head(
    features,
    labels,
    *,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    iterations: int = DEFAULT_ITERATIONS,
    l2_regularization: float = DEFAULT_L2_REGULARIZATION,
    positive_class_weight: float = 1.0,
    negative_class_weight: float = 1.0,
) -> LogisticModelHead:
    matrix = _as_feature_matrix(features)
    target = _as_label_vector(labels)
    if matrix.shape[0] != target.shape[0]:
        raise ValueError("feature and label counts must match")
    weights = np.zeros(matrix.shape[1], dtype=float)
    intercept = 0.0
    sample_weights = _sample_weights(target, positive_class_weight, negative_class_weight)
    for _ in range(max(int(iterations), 1)):
        probabilities = _sigmoid(matrix @ weights + intercept)
        error = (probabilities - target) * sample_weights
        gradient_weights = (matrix.T @ error) / matrix.shape[0] + l2_regularization * weights
        gradient_intercept = float(np.mean(error))
        weights -= learning_rate * gradient_weights
        intercept -= learning_rate * gradient_intercept
    return LogisticModelHead(
        weights=tuple(float(value) for value in weights.tolist()),
        intercept=float(intercept),
        positive_class_weight=float(positive_class_weight),
        negative_class_weight=float(negative_class_weight),
    )


def train_dual_logistic_heads(features, top_labels, bottom_labels) -> tuple[LogisticModelHead, LogisticModelHead]:
    top_positive_weight = _balanced_positive_weight(_as_label_vector(top_labels))
    bottom_positive_weight = _balanced_positive_weight(_as_label_vector(bottom_labels))
    return (
        train_logistic_head(features, top_labels, positive_class_weight=top_positive_weight),
        train_logistic_head(features, bottom_labels, positive_class_weight=bottom_positive_weight),
    )


def evaluate_binary_classifier(features, labels, head: LogisticModelHead) -> BinaryClassificationMetrics:
    target = _as_label_vector(labels)
    probabilities = predict_probabilities(features, head)
    predicted = (probabilities >= 0.5).astype(float)
    clipped = np.clip(probabilities, LOG_LOSS_EPSILON, 1.0 - LOG_LOSS_EPSILON)
    log_loss = -np.mean(target * np.log(clipped) + (1.0 - target) * np.log(1.0 - clipped))
    accuracy = float(np.mean(predicted == target))
    return BinaryClassificationMetrics(
        accuracy=accuracy,
        log_loss=float(log_loss),
        positive_rate=float(np.mean(target)),
    )


def _balanced_positive_weight(labels: np.ndarray) -> float:
    positive_count = float(np.sum(labels > 0.5))
    negative_count = float(np.sum(labels <= 0.5))
    if positive_count <= 0.0 or negative_count <= 0.0:
        raise ValueError("class collapse in training labels")
    return negative_count / positive_count
