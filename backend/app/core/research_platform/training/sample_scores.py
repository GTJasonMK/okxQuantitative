from __future__ import annotations

import math

from app.core.research_platform.dataset.constants import LABEL_VECTOR_FIELDS

VARIOGRAM_P = 0.5
ROW_VECTOR_FIELDS = LABEL_VECTOR_FIELDS


def energy_score(*, observation: dict[str, float], sample_set: list[dict[str, float]]) -> float:
    observation_vector = row_to_vector(observation)
    sample_vectors = [row_to_vector(sample) for sample in sample_set]
    cross_term = sum(euclidean_distance(vector, observation_vector) for vector in sample_vectors) / len(sample_vectors)
    return cross_term - (0.5 * mean_pairwise_distance(sample_vectors))


def variogram_score(*, observation: dict[str, float], sample_set: list[dict[str, float]]) -> float:
    observation_vector = row_to_vector(observation)
    sample_vectors = [row_to_vector(sample) for sample in sample_set]
    score = 0.0
    for left_index in range(len(observation_vector) - 1):
        for right_index in range(left_index + 1, len(observation_vector)):
            observed_gap = _gap_power(
                observation_vector[left_index],
                observation_vector[right_index],
            )
            sample_gap = sum(
                _gap_power(vector[left_index], vector[right_index])
                for vector in sample_vectors
            ) / len(sample_vectors)
            score += (observed_gap - sample_gap) ** 2
    return float(score)


def row_to_vector(row: dict[str, float]) -> list[float]:
    return [float(row[key]) for key in ROW_VECTOR_FIELDS]


def euclidean_distance(lhs: list[float], rhs: list[float]) -> float:
    return math.sqrt(sum((left - right) ** 2 for left, right in zip(lhs, rhs)))


def mean_pairwise_distance(sample_vectors: list[list[float]]) -> float:
    if len(sample_vectors) <= 1:
        return 0.0
    total = 0.0
    count = 0
    for left_index in range(len(sample_vectors) - 1):
        for right_index in range(left_index + 1, len(sample_vectors)):
            total += euclidean_distance(sample_vectors[left_index], sample_vectors[right_index])
            count += 1
    return total / count


def _gap_power(lhs: float, rhs: float) -> float:
    return abs(lhs - rhs) ** VARIOGRAM_P
