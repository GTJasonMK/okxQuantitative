from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Sequence

from .factor_definition import FactorDefinition
from .models import FactorScore, FeatureSelectionResult, SelectedFeatureStats


MIN_FEATURE_COVERAGE = 0.7
MIN_FEATURE_VARIATION = 1e-9
MAX_FEATURE_CORRELATION = 0.9


@dataclass(frozen=True)
class _CandidateFeature:
    definition: FactorDefinition
    values: tuple[float | None, ...]
    mean: float
    std: float
    coverage: float
    spearman_ic: float
    stability_score: float


def _population_std(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    mean_value = fmean(values)
    variance = fmean([(value - mean_value) ** 2 for value in values])
    return variance ** 0.5


def _coverage(values: tuple[float | None, ...]) -> float:
    if not values:
        return 0.0
    return sum(1 for value in values if value is not None) / len(values)


def _candidate_sort_key(candidate: _CandidateFeature) -> tuple[float, float, str]:
    return (-candidate.stability_score, -abs(candidate.spearman_ic), candidate.definition.name)


def _overlap_pairs(left: tuple[float | None, ...], right: tuple[float | None, ...]) -> list[tuple[float, float]]:
    return [(l_value, r_value) for l_value, r_value in zip(left, right) if l_value is not None and r_value is not None]


def _absolute_correlation(left: tuple[float | None, ...], right: tuple[float | None, ...]) -> float:
    overlap = _overlap_pairs(left, right)
    if len(overlap) < 2:
        return 0.0

    left_values = [pair[0] for pair in overlap]
    right_values = [pair[1] for pair in overlap]
    left_mean = fmean(left_values)
    right_mean = fmean(right_values)
    left_std = _population_std(left_values)
    right_std = _population_std(right_values)
    if left_std <= 0.0 or right_std <= 0.0:
        return 0.0
    covariance = fmean(
        [(l_value - left_mean) * (r_value - right_mean) for l_value, r_value in overlap]
    )
    return abs(covariance / (left_std * right_std))


def _build_candidates(
    columns: tuple[tuple[FactorDefinition, tuple[float | None, ...]], ...],
    scores: Sequence[FactorScore],
    min_coverage: float,
    min_variation: float,
) -> list[_CandidateFeature]:
    score_map = {score.factor_name: score for score in scores if score.available}
    candidates = []
    for definition, values in columns:
        score = score_map.get(definition.name)
        valid_values = [value for value in values if value is not None]
        coverage = _coverage(values)
        std = _population_std(valid_values)
        if score is None or coverage < min_coverage or std <= min_variation:
            continue
        candidates.append(
            _CandidateFeature(
                definition=definition,
                values=values,
                mean=fmean(valid_values),
                std=std,
                coverage=coverage,
                spearman_ic=float(score.spearman_ic or 0.0),
                stability_score=float(score.stability_score or 0.0),
            )
        )
    return sorted(candidates, key=_candidate_sort_key)


def _prune_correlated(
    candidates: list[_CandidateFeature],
    max_correlation: float,
) -> tuple[_CandidateFeature, ...]:
    selected = []
    for candidate in candidates:
        correlation_conflict = any(
            candidate.definition.category == existing.definition.category
            and _absolute_correlation(candidate.values, existing.values) > max_correlation
            for existing in selected
        )
        if not correlation_conflict:
            selected.append(candidate)
    return tuple(selected)


def select_training_features(
    columns: Sequence[tuple[FactorDefinition, tuple[float | None, ...]]],
    scores: Sequence[FactorScore],
    *,
    min_coverage: float = MIN_FEATURE_COVERAGE,
    max_correlation: float = MAX_FEATURE_CORRELATION,
    min_variation: float = MIN_FEATURE_VARIATION,
) -> FeatureSelectionResult:
    candidates = _build_candidates(tuple(columns), scores, min_coverage, min_variation)
    selected = _prune_correlated(candidates, max_correlation)
    return FeatureSelectionResult(
        features=tuple(
            SelectedFeatureStats(
                name=candidate.definition.name,
                category=candidate.definition.category,
                mean=candidate.mean,
                std=candidate.std,
                coverage=candidate.coverage,
                spearman_ic=candidate.spearman_ic,
                stability_score=candidate.stability_score,
            )
            for candidate in selected
        )
    )
