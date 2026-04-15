from __future__ import annotations

from math import log
from statistics import fmean

from .direct_models import DirectExtremaTarget, MinuteFeatureToken, OnlineSequenceWindow, SequenceSample
from .factor_catalog import get_factor_definitions
from .models import FeatureBar1s, resolve_bar_price
from .research_runtime import build_raw_factor_columns


SECONDS_PER_MINUTE = 60
MIN_SEQUENCE_LENGTH = 1


def _resolve_definitions(feature_names: tuple[str, ...]):
    definitions = {definition.name: definition for definition in get_factor_definitions()}
    return tuple(definitions[name] for name in feature_names if name in definitions)


_resolve_price = resolve_bar_price


def _resolve_high(bar: FeatureBar1s) -> float:
    return float(bar.high_price) if float(bar.high_price or 0.0) > 0.0 else _resolve_price(bar)


def _resolve_low(bar: FeatureBar1s) -> float:
    return float(bar.low_price) if float(bar.low_price or 0.0) > 0.0 else _resolve_price(bar)


def _group_indices_by_minute(bars: list[FeatureBar1s]) -> tuple[tuple[int, tuple[int, ...]], ...]:
    groups: list[tuple[int, tuple[int, ...]]] = []
    current_minute = None
    current_indices: list[int] = []
    for index, bar in enumerate(bars):
        minute_bucket = int(bar.second_bucket) // SECONDS_PER_MINUTE
        if current_minute is None or minute_bucket == current_minute:
            current_minute = minute_bucket
            current_indices.append(index)
            continue
        groups.append((current_minute, tuple(current_indices)))
        current_minute = minute_bucket
        current_indices = [index]
    if current_minute is not None and current_indices:
        groups.append((current_minute, tuple(current_indices)))
    return tuple(groups)


def _build_feature_map(
    bars: list[FeatureBar1s],
    feature_names: tuple[str, ...],
) -> dict[str, tuple[float | None, ...]]:
    definitions = _resolve_definitions(feature_names)
    if len(definitions) != len(feature_names):
        return {}
    columns = build_raw_factor_columns(bars, definitions=definitions)
    if len(columns) != len(feature_names):
        return {}
    return {definition.name: values for definition, values in columns}


def _aggregate_feature_row(
    indices: tuple[int, ...],
    *,
    feature_names: tuple[str, ...],
    feature_map: dict[str, tuple[float | None, ...]],
) -> tuple[float, ...] | None:
    values = []
    for feature_name in feature_names:
        series = feature_map.get(feature_name)
        if series is None:
            return None
        minute_values = [float(series[index]) for index in indices if series[index] is not None]
        if not minute_values:
            return None
        values.append(fmean(minute_values))
    return tuple(values)


def aggregate_feature_bars_to_minutes(
    bars: list[FeatureBar1s],
    *,
    feature_names: tuple[str, ...],
) -> tuple[MinuteFeatureToken, ...]:
    if not bars or not feature_names:
        return ()
    feature_map = _build_feature_map(bars, feature_names)
    if not feature_map:
        return ()
    tokens = []
    for minute_bucket, indices in _group_indices_by_minute(bars):
        feature_row = _aggregate_feature_row(indices, feature_names=feature_names, feature_map=feature_map)
        if feature_row is None:
            continue
        group_bars = [bars[index] for index in indices]
        current_price = _resolve_price(group_bars[-1])
        if current_price <= 0.0:
            continue
        tokens.append(
            MinuteFeatureToken(
                inst_id=group_bars[-1].inst_id,
                minute_bucket=minute_bucket,
                current_price=current_price,
                high_price=max(_resolve_high(bar) for bar in group_bars),
                low_price=min(_resolve_low(bar) for bar in group_bars),
                feature_values=feature_row,
            )
        )
    return tuple(tokens)


def _first_index(tokens: tuple[MinuteFeatureToken, ...], *, value: float, attr: str) -> int:
    for index, token in enumerate(tokens):
        if float(getattr(token, attr)) == value:
            return index
    raise ValueError(f"target value {value} missing from future tokens")


def _build_target(current_price: float, future_tokens: tuple[MinuteFeatureToken, ...]) -> DirectExtremaTarget | None:
    if current_price <= 0.0 or len(future_tokens) < MIN_SEQUENCE_LENGTH:
        return None
    top_price = max(token.high_price for token in future_tokens)
    bottom_price = min(token.low_price for token in future_tokens)
    if top_price <= 0.0 or bottom_price <= 0.0:
        return None
    return DirectExtremaTarget(
        top_time_bucket=_first_index(future_tokens, value=top_price, attr="high_price"),
        bottom_time_bucket=_first_index(future_tokens, value=bottom_price, attr="low_price"),
        top_price=top_price,
        bottom_price=bottom_price,
        top_return=log(top_price / current_price),
        bottom_return=log(bottom_price / current_price),
    )


def build_sequence_samples(
    bars: list[FeatureBar1s],
    *,
    feature_names: tuple[str, ...],
    input_minutes: int,
    horizon_minutes: int,
) -> list[SequenceSample]:
    minute_tokens = aggregate_feature_bars_to_minutes(bars, feature_names=feature_names)
    minimum_minutes = max(int(input_minutes or 0), 0) + max(int(horizon_minutes or 0), 0)
    if len(minute_tokens) < minimum_minutes:
        return []
    samples: list[SequenceSample] = []
    for anchor_index in range(input_minutes - 1, len(minute_tokens) - horizon_minutes):
        history_tokens = minute_tokens[anchor_index - input_minutes + 1: anchor_index + 1]
        future_tokens = minute_tokens[anchor_index + 1: anchor_index + 1 + horizon_minutes]
        if len(history_tokens) != input_minutes or len(future_tokens) != horizon_minutes:
            continue
        current_price = history_tokens[-1].current_price
        target = _build_target(current_price, future_tokens)
        if target is None:
            continue
        samples.append(
            SequenceSample(
                inst_id=history_tokens[-1].inst_id,
                anchor_minute_bucket=history_tokens[-1].minute_bucket,
                feature_names=feature_names,
                feature_rows=tuple(token.feature_values for token in history_tokens),
                current_price=current_price,
                target=target,
            )
        )
    return samples


def build_online_sequence_window(
    bars: list[FeatureBar1s] | tuple[FeatureBar1s, ...],
    *,
    feature_names: tuple[str, ...],
    input_minutes: int,
) -> OnlineSequenceWindow:
    minute_tokens = aggregate_feature_bars_to_minutes(list(bars), feature_names=feature_names)
    if len(minute_tokens) < max(int(input_minutes or 0), MIN_SEQUENCE_LENGTH):
        raise ValueError("insufficient minute tokens for direct extrema inference")
    history_tokens = minute_tokens[-input_minutes:]
    return OnlineSequenceWindow(
        inst_id=history_tokens[-1].inst_id,
        anchor_minute_bucket=history_tokens[-1].minute_bucket,
        feature_names=feature_names,
        feature_rows=tuple(token.feature_values for token in history_tokens),
        current_price=history_tokens[-1].current_price,
    )
