from __future__ import annotations

from app.core.research_platform.dataset.constants import LABEL_VECTOR_FIELDS


MARGINAL_FIELDS = LABEL_VECTOR_FIELDS


def build_marginal_coverage(
    *,
    observations: list[dict[str, float]],
    samples: list[list[dict[str, float]]],
    normalized_weights: list[float],
) -> dict[str, object]:
    return {
        'stats': {
            field: {
                'coverage_rate': sum(
                    weight * _marginal_coverage_hit(
                        observed=float(observation[field]),
                        sample_values=[float(sample[field]) for sample in sample_set],
                    )
                    for observation, sample_set, weight in zip(
                        observations,
                        samples,
                        normalized_weights,
                    )
                )
            }
            for field in MARGINAL_FIELDS
        }
    }


def build_weighted_pit(
    *,
    observations: list[dict[str, float]],
    samples: list[list[dict[str, float]]],
    normalized_weights: list[float],
) -> dict[str, object]:
    return {
        'stats': {
            field: _weighted_pit_stats(
                observed_values=[float(observation[field]) for observation in observations],
                sample_values=[[float(sample[field]) for sample in sample_set] for sample_set in samples],
                normalized_weights=normalized_weights,
            )
            for field in MARGINAL_FIELDS
        }
    }


def _weighted_pit_stats(
    *,
    observed_values: list[float],
    sample_values: list[list[float]],
    normalized_weights: list[float],
) -> dict[str, float]:
    pits = [
        _pit_value(observed=observed, sample_values=samples)
        for observed, samples in zip(observed_values, sample_values)
    ]
    weighted_mean = sum(weight * pit for weight, pit in zip(normalized_weights, pits))
    weighted_var = sum(weight * ((pit - weighted_mean) ** 2) for weight, pit in zip(normalized_weights, pits))
    return {
        'weighted_mean': weighted_mean,
        'weighted_variance': weighted_var,
    }


def _marginal_coverage_hit(
    *,
    observed: float,
    sample_values: list[float],
) -> float:
    lower = min(sample_values)
    upper = max(sample_values)
    return 1.0 if lower <= observed <= upper else 0.0


def _pit_value(
    *,
    observed: float,
    sample_values: list[float],
) -> float:
    less_count = sum(value < observed for value in sample_values)
    equal_count = sum(value == observed for value in sample_values)
    return (less_count + (0.5 * equal_count)) / len(sample_values)
