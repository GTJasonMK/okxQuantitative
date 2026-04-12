from __future__ import annotations

from math import isfinite
from statistics import fmean
from typing import Sequence

from .factor_catalog import get_factor_definitions
from .factor_definition import FactorDefinition
from .factor_research import rank_candidate_factors
from .labeling import build_swing_labels
from .models import CandidateFactorSeries, FactorScore


DEFAULT_FACTOR_LOOKBACK = 3600
DEFAULT_FACTOR_LIMIT = 20
MIN_BARS_FOR_RESEARCH = 3


def _zscore(values: list[float]) -> list[float]:
    if not values:
        return []

    mean_value = fmean(values)
    variance = fmean([(value - mean_value) ** 2 for value in values])
    if variance <= 0.0:
        return [0.0 for _ in values]

    std_value = variance ** 0.5
    return [(value - mean_value) / std_value for value in values]


def _normalize_raw_factor_value(value) -> float | None:
    if value is None:
        return None
    try:
        normalized = float(value)
    except (TypeError, ValueError):
        return None
    if not isfinite(normalized):
        return None
    return normalized


def _build_raw_factor_values(definition: FactorDefinition, bars) -> tuple[float | None, ...] | None:
    if not definition.is_available(bars):
        return None
    values = definition.compute_series(bars)
    if values is None or len(values) != len(bars):
        return None
    return tuple(_normalize_raw_factor_value(value) for value in values)


def build_raw_factor_columns(
    bars,
    *,
    definitions: Sequence[FactorDefinition] | None = None,
) -> tuple[tuple[FactorDefinition, tuple[float | None, ...]], ...]:
    resolved_definitions = tuple(definitions or get_factor_definitions())
    columns = []
    for definition in resolved_definitions:
        values = _build_raw_factor_values(definition, bars)
        if values is None:
            continue
        columns.append((definition, values))
    return tuple(columns)


def build_candidate_factor_series(inst_id: str, bars) -> list[CandidateFactorSeries]:
    series: list[CandidateFactorSeries] = []
    for definition, values in build_raw_factor_columns(bars):
        if any(value is None for value in values):
            continue
        series.append(
            CandidateFactorSeries(
                inst_id=inst_id,
                factor_name=definition.name,
                values=_zscore(list(values)),
                category=definition.category,
                tier=definition.tier,
            )
        )
    return series


def build_factor_score_rows(inst_id: str, bars, scores: list[FactorScore], limit: int) -> list[FactorScore]:
    scored_names = {score.factor_name for score in scores}
    placeholders = [
        definition.build_placeholder_score(inst_id)
        for definition in get_factor_definitions()
        if definition.name not in scored_names and definition.tier > 0 and not definition.is_available(bars)
    ]
    return [*scores, *placeholders][: max(int(limit or DEFAULT_FACTOR_LIMIT), 1)]


def rebuild_factor_scores_for_inst(storage, inst_id: str, *, lookback: int, limit: int):
    normalized_lookback = max(int(lookback or DEFAULT_FACTOR_LOOKBACK), MIN_BARS_FOR_RESEARCH)
    normalized_limit = max(int(limit or DEFAULT_FACTOR_LIMIT), 1)
    bars = list(reversed(storage.list_feature_bars_1s(inst_id, limit=normalized_lookback)))
    if len(bars) < MIN_BARS_FOR_RESEARCH:
        storage.replace_swing_labels(inst_id, [])
        storage.replace_factor_scores(inst_id, [])
        return []

    labels = build_swing_labels(bars)
    storage.replace_swing_labels(inst_id, labels)
    scores = rank_candidate_factors(build_candidate_factor_series(inst_id, bars), labels)
    storage.replace_factor_scores(inst_id, scores)
    return build_factor_score_rows(inst_id, bars, scores, normalized_limit)


def _resolved_series_limit(*, lookback: int, limit: int | None) -> int:
    normalized_lookback = max(int(lookback or DEFAULT_FACTOR_LOOKBACK), MIN_BARS_FOR_RESEARCH)
    if limit is None:
        return normalized_lookback
    normalized_limit = max(int(limit or normalized_lookback), MIN_BARS_FOR_RESEARCH)
    return min(normalized_limit, normalized_lookback)


def _serialize_factor_score(score: FactorScore) -> dict:
    return {
        "factor_name": score.factor_name,
        "spearman_ic": score.spearman_ic,
        "stability_score": score.stability_score,
        "redundancy_cluster": score.redundancy_cluster,
        "category": score.category,
        "tier": score.tier,
        "available": score.available,
        "unavailable_reason": score.unavailable_reason,
    }


def _resolve_factor_score(
    definition: FactorDefinition,
    score_map: dict[str, FactorScore],
    inst_id: str,
    *,
    available: bool,
) -> FactorScore:
    score = score_map.get(definition.name)
    if score is not None:
        return score
    return FactorScore(
        inst_id=inst_id,
        factor_name=definition.name,
        spearman_ic=None,
        stability_score=None,
        redundancy_cluster=definition.category or definition.name,
        category=definition.category,
        tier=definition.tier,
        available=available,
        unavailable_reason="" if available else definition.unavailable_reason,
    )


def _build_factor_series_rows(
    definitions: Sequence[FactorDefinition],
    *,
    inst_id: str,
    raw_columns: dict[str, tuple[float | None, ...]],
    score_map: dict[str, FactorScore],
) -> tuple[list[dict], list[dict]]:
    series = []
    score_meta = []
    for definition in definitions:
        values = raw_columns.get(definition.name)
        values_available = values is not None
        score = _resolve_factor_score(
            definition,
            score_map,
            inst_id,
            available=values_available,
        )
        score_meta.append(_serialize_factor_score(score))
        series.append({
            "factor_name": definition.name,
            "category": definition.category,
            "available": values_available,
            "tier": int(score.tier),
            "unavailable_reason": "" if values_available else score.unavailable_reason,
            "values": list(values) if values_available else [],
        })
    return series, score_meta


def build_factor_series_payload(storage, inst_id: str, *, lookback: int, limit: int | None = None) -> dict:
    definitions = get_factor_definitions()
    resolved_limit = _resolved_series_limit(lookback=lookback, limit=limit)
    bars = list(reversed(storage.list_feature_bars_1s(inst_id, limit=resolved_limit)))
    second_buckets = [int(bar.second_bucket) for bar in bars]
    score_rows = rebuild_factor_scores_for_inst(storage, inst_id, lookback=lookback, limit=len(definitions))
    score_map = {row.factor_name: row for row in score_rows}
    raw_columns = {definition.name: values for definition, values in build_raw_factor_columns(bars, definitions=definitions)}
    series, score_meta = _build_factor_series_rows(
        definitions,
        inst_id=inst_id,
        raw_columns=raw_columns,
        score_map=score_map,
    )
    return {
        "inst_id": inst_id,
        "lookback": int(lookback),
        "second_buckets": second_buckets,
        "series": series,
        "score_meta": score_meta,
    }
