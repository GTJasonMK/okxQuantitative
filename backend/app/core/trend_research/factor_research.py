from __future__ import annotations

from typing import List

from .models import CandidateFactorSeries, FactorScore, SwingLabel
from .factor_stats import (
    build_extrema_label_signal,
    compute_spearman_rank_ic,
    compute_stability_score,
)


def rank_candidate_factors(
    factors: List[CandidateFactorSeries],
    labels: List[SwingLabel],
) -> List[FactorScore]:
    if not factors or not labels:
        return []

    label_signal = build_extrema_label_signal(labels)
    if not label_signal:
        return []

    ranked: List[FactorScore] = []
    for factor in factors:
        spearman_ic = compute_spearman_rank_ic(factor.values, label_signal)
        if spearman_ic is None:
            continue
        stability_score = compute_stability_score(factor.values, label_signal, spearman_ic)
        ranked.append(
            FactorScore(
                inst_id=factor.inst_id,
                factor_name=factor.factor_name,
                spearman_ic=spearman_ic,
                stability_score=stability_score,
                redundancy_cluster=factor.category or factor.factor_name,
                category=factor.category,
                tier=factor.tier,
                available=True,
                unavailable_reason="",
            )
        )

    return sorted(ranked, key=_factor_score_sort_key)


def _factor_score_sort_key(item: FactorScore) -> tuple[float, float, float, str]:
    stability = float(item.stability_score or 0.0)
    spearman = abs(float(item.spearman_ic or 0.0))
    availability = 1.0 if item.available else 0.0
    return (-availability, -stability, -spearman, item.factor_name)
