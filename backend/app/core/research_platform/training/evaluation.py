from __future__ import annotations

from decimal import Decimal

from app.core.research_platform.dataset.effective_size import estimate_effective_sample_size

from .diagnostics_bundle import build_diagnostics_bundle
from .regime_summary import build_regime_summary
from .sample_scores import energy_score as compute_energy_score
from .sample_scores import variogram_score as compute_variogram_score


FORECAST_METRIC_FIELDS = ('joint_nll', 'energy_score', 'variogram_score')
DECISION_METRIC_PREFERENCES = {
    'mean_utility': False,
    'net_return': False,
    'max_drawdown': True,
    'turnover_mean': True,
    'hit_rate': False,
    'exposure_rate': False,
    'downside_tail_risk': True,
}

def evaluate_forecast_batch(
    *,
    observations: list[dict[str, float]],
    samples: list[list[dict[str, float]]],
    joint_nll_values: list[float],
    sample_weights: list[float],
    comparison_delta_sequence: list[float] | None = None,
    regimes: list[dict[str, object]],
) -> dict[str, object]:
    weighted = normalize_importance_weights(raw_weights=sample_weights)
    unweighted = normalize_importance_weights(raw_weights=[1.0] * len(sample_weights))
    forecast_metrics = compute_joint_scores(
        observations=observations,
        samples=samples,
        joint_nll_values=joint_nll_values,
        raw_weights=sample_weights,
    )
    return {
        'forecast_metrics': forecast_metrics,
        'weighted_diagnostics': build_diagnostics_bundle(
            weight_mode='weighted',
            observations=observations,
            samples=samples,
            normalized_weights=weighted,
        ),
        'unweighted_diagnostics': build_diagnostics_bundle(
            weight_mode='unweighted',
            observations=observations,
            samples=samples,
            normalized_weights=unweighted,
        ),
        'regime_metrics': build_regime_summary(
            regimes=regimes,
            observations=observations,
            samples=samples,
            raw_weights=sample_weights,
            joint_nll_values=joint_nll_values,
        ),
        'n_eff_summary': build_n_eff_summary(
            observations=observations,
            primary_score_sequence=[
                float(weight) * float(value)
                for weight, value in zip(sample_weights, joint_nll_values)
            ],
            comparison_delta_sequence=comparison_delta_sequence or [0.0] * len(joint_nll_values),
        ),
    }


def normalize_importance_weights(*, raw_weights: list[float]) -> list[float]:
    total = float(sum(raw_weights))
    if total <= 0.0:
        raise ValueError('importance weights must sum to a positive value')
    return [float(weight / total) for weight in raw_weights]


def compute_joint_scores(
    *,
    observations: list[dict[str, float]],
    samples: list[list[dict[str, float]]],
    joint_nll_values: list[float],
    raw_weights: list[float],
) -> dict[str, float]:
    scale = float(len(raw_weights))
    joint_nll = sum(weight * value for weight, value in zip(raw_weights, joint_nll_values)) / scale
    energy_score = (
        sum(
            weight * compute_energy_score(observation=observation, sample_set=sample_set)
            for observation, sample_set, weight in zip(observations, samples, raw_weights)
        )
        / scale
    )
    variogram_score = (
        sum(
            weight * compute_variogram_score(observation=observation, sample_set=sample_set)
            for observation, sample_set, weight in zip(observations, samples, raw_weights)
        )
        / scale
    )
    return {
        'joint_nll': joint_nll,
        'energy_score': energy_score,
        'variogram_score': variogram_score,
    }


def build_n_eff_summary(
    *,
    observations: list[dict[str, float]],
    primary_score_sequence: list[float],
    comparison_delta_sequence: list[float],
) -> dict[str, object]:
    if len(comparison_delta_sequence) != len(primary_score_sequence):
        raise ValueError('comparison_delta_sequence must align with primary_score_sequence')
    return {
        'truncation_rule': 'initial_positive_sequence_v1',
        'sequences': {
            'primary_validation_score_sequence': build_sequence_summary(
                field_name='joint_nll',
                sequence_ref='artifact://n-eff/primary-validation-score-sequence.json',
                sequence_role='model_selection_objective',
                sequence=primary_score_sequence,
            ),
            'label_r_close_sequence': build_sequence_summary(
                field_name='r_close',
                sequence_ref='artifact://n-eff/label-r-close-sequence.json',
                sequence_role='data_dependence_proxy',
                sequence=[float(row['r_close']) for row in observations],
            ),
            'model_comparison_delta_sequence': build_sequence_summary(
                field_name='challenger_score_minus_locked_baseline_score',
                sequence_ref='artifact://n-eff/model-comparison-delta-sequence.json',
                sequence_role='pairwise_model_difference',
                sequence=comparison_delta_sequence,
            ),
        },
    }


def build_training_artifact_summary(
    *,
    forecast_metrics: dict[str, object],
    decision_metrics: dict[str, object],
    weighted_diagnostics: dict[str, object],
    unweighted_diagnostics: dict[str, object],
    regime_metrics: dict[str, object],
    n_eff_summary: dict[str, object],
    bootstrap_result: dict[str, object],
    baseline_result: dict[str, object],
    comparison_result: dict[str, object],
) -> dict[str, object]:
    return {
        'forecast_metrics': forecast_metrics,
        'decision_metrics': decision_metrics,
        'weighted_diagnostics': weighted_diagnostics,
        'unweighted_diagnostics': unweighted_diagnostics,
        'regime_metrics': regime_metrics,
        'n_eff_summary': n_eff_summary,
        'bootstrap_result': bootstrap_result,
        'baseline_result': baseline_result,
        'comparison_result': comparison_result,
    }


def aggregate_metric_bundle(
    origins: list[dict[str, object]],
    *,
    bundle_key: str,
    metric_fields: tuple[str, ...],
    lower_is_better: bool,
) -> dict[str, object]:
    return {
        field_name: _summarize_metric_values(
            [(int(origin['origin_ts']), float(origin[bundle_key][field_name])) for origin in origins],
            lower_is_better=lower_is_better,
        )
        for field_name in metric_fields
    }


def aggregate_metric_bundle_by_field(
    origins: list[dict[str, object]],
    *,
    bundle_key: str,
    field_preferences: dict[str, bool],
) -> dict[str, object]:
    return {
        field_name: _summarize_metric_values(
            [(int(origin['origin_ts']), float(origin[bundle_key][field_name])) for origin in origins],
            lower_is_better=lower_is_better,
        )
        for field_name, lower_is_better in field_preferences.items()
    }


def collect_origin_artifacts(
    origins: list[dict[str, object]],
    *,
    artifact_key: str,
) -> dict[str, object]:
    return {
        'origin_count': len(origins),
        'by_origin': [
            {
                'origin_ts': int(origin['origin_ts']),
                artifact_key: origin[artifact_key],
            }
            for origin in origins
        ],
    }


def extract_metric_values(
    origins: list[dict[str, object]],
    *,
    bundle_key: str,
    field_name: str,
) -> list[float]:
    return [float(origin[bundle_key][field_name]) for origin in origins]


def finalize_training_run_parameter_refs(
    *,
    run_id: str,
    weighting_version: str,
) -> dict[str, str]:
    refs = {
        'policy_parameter_ref': f'artifact://training-run/{run_id}/policy-params-by-origin.json',
        'utility_parameter_ref': f'artifact://training-run/{run_id}/utility-params-by-origin.json',
        'weight_fit_ref': f'artifact://training-run/{run_id}/weight-fit-by-origin.json',
    }
    if weighting_version == 'classifier_density_ratio_weighting':
        refs['domain_classifier_fit_ref'] = f'artifact://training-run/{run_id}/domain-classifier-fit-by-origin.json'
    return refs


def build_sequence_summary(
    *,
    field_name: str,
    sequence_ref: str,
    sequence_role: str,
    sequence: list[float],
) -> dict[str, object]:
    return {
        'field_name': field_name,
        'sequence_ref': sequence_ref,
        'sequence_role': sequence_role,
        'estimate': estimate_effective_sample_size(
            sequence=sequence,
            truncation_rule='initial_positive_sequence_v1',
        ),
        'value_summary': {
            'count': len(sequence),
            'mean': build_decimal_mean(sequence),
            'min': min(sequence),
            'max': max(sequence),
        },
    }


def build_decimal_mean(sequence: list[float]) -> float:
    decimal_sequence = [Decimal(str(value)) for value in sequence]
    return float(sum(decimal_sequence) / len(decimal_sequence))


def _summarize_metric_values(
    pairs: list[tuple[int, float]],
    *,
    lower_is_better: bool,
) -> dict[str, float]:
    values = [value for _, value in pairs]
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    comparator = min if lower_is_better else max
    worst_origin_ts, worst_value = comparator(pairs, key=lambda item: item[1])
    mean = sum(values) / len(values)
    variance = sum((value - mean) ** 2 for value in values) / len(values)
    return {
        'mean': mean,
        'median': ordered[midpoint],
        'dispersion': variance ** 0.5,
        'worst_origin_ts': float(worst_origin_ts),
        'worst_value': worst_value,
    }
