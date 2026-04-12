from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .factor_definition import FactorDefinition
from .models import ExtremaTarget, FeatureBar1s
from .research_runtime import build_raw_factor_columns


EMPTY_BARS_ERROR = "bars must not be empty"
LENGTH_MISMATCH_ERROR = "bars and targets must have identical length"
MISSING_FEATURE_ERROR = "missing feature value"
NO_AVAILABLE_FEATURES_ERROR = "no available features"


@dataclass(frozen=True)
class TrainingMatrix:
    inst_id: str
    feature_names: tuple[str, ...]
    second_buckets: tuple[int, ...]
    rows: tuple[tuple[float, ...], ...]
    top_labels: tuple[int, ...]
    bottom_labels: tuple[int, ...]


@dataclass(frozen=True)
class LatestFeatureVector:
    inst_id: str
    second_bucket: int
    feature_names: tuple[str, ...]
    values: tuple[float, ...]


def _resolve_columns(
    bars: list[FeatureBar1s],
    definitions: Sequence[FactorDefinition] | None,
) -> tuple[tuple[FactorDefinition, tuple[float | None, ...]], ...]:
    if not bars:
        raise ValueError(EMPTY_BARS_ERROR)
    columns = build_raw_factor_columns(bars, definitions=definitions)
    if not columns:
        raise ValueError(NO_AVAILABLE_FEATURES_ERROR)
    return columns


def _build_row(
    columns: tuple[tuple[FactorDefinition, tuple[float | None, ...]], ...],
    index: int,
) -> tuple[float, ...] | None:
    row = []
    for _, values in columns:
        value = values[index]
        if value is None:
            return None
        row.append(value)
    return tuple(row)


def build_training_matrix(
    bars: list[FeatureBar1s],
    targets: list[ExtremaTarget],
    *,
    definitions: Sequence[FactorDefinition] | None = None,
) -> TrainingMatrix:
    if len(bars) != len(targets):
        raise ValueError(LENGTH_MISMATCH_ERROR)

    columns = _resolve_columns(bars, definitions)
    feature_names = tuple(definition.name for definition, _ in columns)
    second_buckets = []
    rows = []
    top_labels = []
    bottom_labels = []
    for index, (bar, target) in enumerate(zip(bars, targets)):
        row = _build_row(columns, index)
        if row is None:
            continue
        second_buckets.append(bar.second_bucket)
        rows.append(row)
        top_labels.append(1 if target.top_event else 0)
        bottom_labels.append(1 if target.bottom_event else 0)
    return TrainingMatrix(
        inst_id=bars[0].inst_id,
        feature_names=feature_names,
        second_buckets=tuple(second_buckets),
        rows=tuple(rows),
        top_labels=tuple(top_labels),
        bottom_labels=tuple(bottom_labels),
    )


def build_latest_feature_vector(
    bars: list[FeatureBar1s],
    *,
    definitions: Sequence[FactorDefinition] | None = None,
) -> LatestFeatureVector:
    columns = _resolve_columns(bars, definitions)
    feature_names = tuple(definition.name for definition, _ in columns)
    latest_index = len(bars) - 1
    values = _build_row(columns, latest_index)
    if values is None:
        raise ValueError(f"{MISSING_FEATURE_ERROR} at second_bucket={bars[latest_index].second_bucket}")
    return LatestFeatureVector(
        inst_id=bars[latest_index].inst_id,
        second_bucket=bars[latest_index].second_bucket,
        feature_names=feature_names,
        values=values,
    )
