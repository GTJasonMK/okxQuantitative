from __future__ import annotations

from app.core.research_platform.dataset.shift_state import (
    REGIME_FIELDS_V1,
    REGIME_OUTPUT_FIELDS_V1,
    REGIME_WEIGHTED_MEAN_FIELDS,
)

from .sample_scores import energy_score
from .sample_scores import variogram_score


def build_regime_summary(
    *,
    regimes: list[dict[str, object]],
    observations: list[dict[str, float]],
    samples: list[list[dict[str, float]]],
    raw_weights: list[float],
    joint_nll_values: list[float],
) -> dict[str, object]:
    return {
        'schema': _build_schema(),
        'rows': _aggregate_regime_rows(
            regimes=regimes,
            observations=observations,
            samples=samples,
            raw_weights=raw_weights,
            joint_nll_values=joint_nll_values,
        ),
    }


def _build_schema() -> dict[str, object]:
    return {
        'definition_version': 'boundary_regimes_v1',
        'required_fields': list(REGIME_FIELDS_V1),
        'output_fields': list(REGIME_OUTPUT_FIELDS_V1),
    }


def _aggregate_regime_rows(
    *,
    regimes: list[dict[str, object]],
    observations: list[dict[str, float]],
    samples: list[list[dict[str, float]]],
    raw_weights: list[float],
    joint_nll_values: list[float],
) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    rows = zip(regimes, observations, samples, raw_weights, joint_nll_values)
    for regime, observation, sample_set, weight, joint_nll in rows:
        bucket = grouped.setdefault(_build_regime_key(regime), _build_empty_bucket(regime))
        _accumulate_bucket(
            bucket=bucket,
            observation=observation,
            sample_set=sample_set,
            weight=float(weight),
            joint_nll=float(joint_nll),
        )
    return [_finalize_bucket(bucket) for bucket in grouped.values()]


def _build_regime_key(regime: dict[str, object]) -> str:
    return '|'.join(str(regime[field]) for field in REGIME_FIELDS_V1)


def _build_empty_bucket(regime: dict[str, object]) -> dict[str, object]:
    return {
        'regime_key': _build_regime_key(regime),
        'sample_count': 0,
        'raw_weight_sum': 0.0,
        '_joint_nll_sum': 0.0,
        '_energy_score_sum': 0.0,
        '_variogram_score_sum': 0.0,
        '_calibration_error_sum': 0.0,
        '_sharpness_sum': 0.0,
    }


def _accumulate_bucket(
    *,
    bucket: dict[str, object],
    observation: dict[str, float],
    sample_set: list[dict[str, float]],
    weight: float,
    joint_nll: float,
) -> None:
    mean_close = sum(float(sample['r_close']) for sample in sample_set) / len(sample_set)
    mean_sharpness = sum(
        float(sample['u']) + float(sample['d'])
        for sample in sample_set
    ) / len(sample_set)
    bucket['sample_count'] += 1
    bucket['raw_weight_sum'] += weight
    bucket['_joint_nll_sum'] += weight * joint_nll
    bucket['_energy_score_sum'] += weight * energy_score(observation=observation, sample_set=sample_set)
    bucket['_variogram_score_sum'] += weight * variogram_score(observation=observation, sample_set=sample_set)
    bucket['_calibration_error_sum'] += weight * abs(mean_close - float(observation['r_close']))
    bucket['_sharpness_sum'] += weight * mean_sharpness


def _finalize_bucket(bucket: dict[str, object]) -> dict[str, object]:
    weight_sum = float(bucket['raw_weight_sum'])
    return {
        'regime_key': bucket['regime_key'],
        'sample_count': int(bucket['sample_count']),
        'raw_weight_sum': weight_sum,
        'joint_nll_mean': _safe_weighted_mean(bucket['_joint_nll_sum'], weight_sum),
        'energy_score_mean': _safe_weighted_mean(bucket['_energy_score_sum'], weight_sum),
        'variogram_score_mean': _safe_weighted_mean(bucket['_variogram_score_sum'], weight_sum),
        'calibration_error': _safe_weighted_mean(bucket['_calibration_error_sum'], weight_sum),
        'sharpness_mean': _safe_weighted_mean(bucket['_sharpness_sum'], weight_sum),
    }


def _safe_weighted_mean(weighted_sum: float, weight_sum: float) -> float:
    if weight_sum <= 0.0:
        return 0.0
    return weighted_sum / weight_sum
