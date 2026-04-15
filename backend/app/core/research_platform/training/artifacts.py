from __future__ import annotations

from decimal import Decimal

from app.core.research_platform.dataset.qualified_rows import load_qualified_rows

from .baselines import (
    build_baseline_bundle,
    select_reference_baseline,
)
from .bootstrap import stationary_block_bootstrap_mean
from .comparison import build_locked_candidate_comparison_result
from .decision_policy import (
    build_policy_parameter_bundle,
    build_utility_parameter_bundle,
)
from .evaluation import (
    DECISION_METRIC_PREFERENCES,
    FORECAST_METRIC_FIELDS,
    aggregate_metric_bundle,
    aggregate_metric_bundle_by_field,
    build_sequence_summary,
    build_training_artifact_summary,
    collect_origin_artifacts,
    finalize_training_run_parameter_refs,
)
from .origin_pipeline import build_origin_bundle
from .origin_weighting import (
    build_weight_fit_bundles,
)
from .protocol_artifacts import (
    build_candidate_set_bundle,
    build_execution_assumption_bundle,
)
from .refit_policy import build_refit_policy_bundle
from .splits import (
    OUTER_ORIGIN_SELECTION_POLICY,
    build_blocked_temporal_hv_v1,
    count_outer_origin_candidates,
)



def build_training_artifacts(
    *,
    storage,
    manifest: dict[str, object],
    run: dict[str, object],
) -> tuple[dict[str, object], dict[str, str]]:
    qualified_rows, census_rows = load_qualified_rows(storage, manifest)
    split_artifact = build_split_artifact(manifest=manifest, qualified_rows=qualified_rows)
    rolling_origin = build_rolling_origin_evaluation(
        storage=storage,
        manifest=manifest,
        run=run,
        split_artifact=split_artifact,
        qualified_rows=qualified_rows,
        census_rows=census_rows,
    )
    refs = finalize_training_run_parameter_refs(
        run_id=str(run['run_id']),
        weighting_version=str(manifest['weighting_version']),
    )
    baseline_result = build_baseline_bundle(
        manifest=manifest,
        split_artifact=split_artifact,
        qualified_rows=qualified_rows,
        census_rows=census_rows,
        challenger_origins=rolling_origin['origins'],
    )
    rolling_origin = apply_reference_baseline_delta_sequences(
        rolling_origin=rolling_origin,
        baseline_result=baseline_result,
    )
    comparison_result = build_locked_candidate_comparison_result(
        challenger_origins=rolling_origin['origins'],
        challenger_id=str(run['model_family']),
        baseline_bundle=baseline_result,
        candidate_set_ref=str(run['candidate_set_ref']),
    )
    artifacts = build_training_artifact_summary(
        forecast_metrics=rolling_origin['forecast_metrics'],
        decision_metrics=rolling_origin['decision_metrics'],
        weighted_diagnostics=rolling_origin['weighted_diagnostics'],
        unweighted_diagnostics=rolling_origin['unweighted_diagnostics'],
        regime_metrics=rolling_origin['regime_metrics'],
        n_eff_summary=rolling_origin['n_eff_summary'],
        bootstrap_result=_build_bootstrap_result(rolling_origin),
        baseline_result=baseline_result,
        comparison_result=comparison_result,
    )
    artifacts['split_artifact'] = split_artifact
    artifacts['rolling_origin_evaluation'] = rolling_origin
    artifacts['policy_parameter_bundle'] = build_policy_parameter_bundle(
        origins=rolling_origin['origins'],
        policy_parameter_ref=refs['policy_parameter_ref'],
    )
    artifacts['utility_parameter_bundle'] = build_utility_parameter_bundle(
        origins=rolling_origin['origins'],
        utility_parameter_ref=refs['utility_parameter_ref'],
    )
    artifacts['execution_assumption_bundle'] = build_execution_assumption_bundle(
        execution_assumption_version=str(run['execution_assumption_version']),
    )
    artifacts['candidate_set_bundle'] = build_candidate_set_bundle(
        run=run,
        baseline_bundle=baseline_result,
    )
    artifacts.update(
        build_weight_fit_bundles(
            origins=rolling_origin['origins'],
            weight_fit_ref=refs['weight_fit_ref'],
            domain_classifier_fit_ref=str(refs.get('domain_classifier_fit_ref', '')),
        )
    )
    return artifacts, refs


def build_split_artifact(
    *,
    manifest: dict[str, object],
    qualified_rows: list[dict[str, object]],
) -> dict[str, object]:
    decision_ts = [int(row['decision_ts']) for row in qualified_rows]
    outer_origin_count = count_outer_origin_candidates(
        decision_ts=decision_ts,
        embargo_sec=int(manifest['embargo_sec']),
    )
    origins = build_blocked_temporal_hv_v1(
        decision_ts=decision_ts,
        embargo_sec=int(manifest['embargo_sec']),
        outer_origin_count=outer_origin_count,
    )
    return {
        'definition_version': str(manifest['split_definition_version']),
        'refit_policy_version': str(manifest['refit_policy_version']),
        'refit_policy': build_refit_policy_bundle(
            refit_policy_version=str(manifest['refit_policy_version']),
        ),
        'outer_origin_selection_policy': OUTER_ORIGIN_SELECTION_POLICY,
        'qualified_sample_count': len(decision_ts),
        'origins': origins,
    }


def build_rolling_origin_evaluation(
    *,
    storage,
    manifest: dict[str, object],
    run: dict[str, object],
    split_artifact: dict[str, object],
    qualified_rows: list[dict[str, object]],
    census_rows: list[dict[str, object]],
) -> dict[str, object]:
    origins = [
        build_origin_bundle(
            storage=storage,
            manifest=manifest,
            run=run,
            split_row=split_row,
            qualified_rows=qualified_rows,
            census_rows=census_rows,
        )
        for split_row in split_artifact['origins']
    ]
    return {
        'evaluation_protocol_version': str(manifest['evaluation_protocol_version']),
        'origin_count': len(origins),
        'origins': origins,
        'forecast_metrics': aggregate_metric_bundle(origins, bundle_key='forecast_metrics', metric_fields=FORECAST_METRIC_FIELDS, lower_is_better=True),
        'decision_metrics': aggregate_metric_bundle_by_field(
            origins,
            bundle_key='decision_metrics',
            field_preferences=DECISION_METRIC_PREFERENCES,
        ),
        'weighted_diagnostics': collect_origin_artifacts(origins, artifact_key='weighted_diagnostics'),
        'unweighted_diagnostics': collect_origin_artifacts(origins, artifact_key='unweighted_diagnostics'),
        'regime_metrics': collect_origin_artifacts(origins, artifact_key='regime_metrics'),
        'n_eff_summary': collect_origin_artifacts(origins, artifact_key='n_eff_summary'),
    }


def _build_bootstrap_result(rolling_origin: dict[str, object]) -> dict[str, object]:
    forecast_values = _flatten_origin_sequence(
        rolling_origin['origins'],
        sequence_key='forecast_score_sequence',
    )
    decision_values = _flatten_bundle_sequence(
        rolling_origin['origins'],
        bundle_key='decision_metrics',
        sequence_key='utility_sequence',
    )
    return {
        'joint_nll': stationary_block_bootstrap_mean(values=forecast_values, avg_block_length=9, bootstrap_repeats=200),
        'mean_utility': stationary_block_bootstrap_mean(values=decision_values, avg_block_length=9, bootstrap_repeats=200),
    }


def apply_reference_baseline_delta_sequences(
    *,
    rolling_origin: dict[str, object],
    baseline_result: dict[str, object],
) -> dict[str, object]:
    reference_baseline = select_reference_baseline(baseline_result)
    baseline_origins = {
        int(origin['origin_ts']): origin
        for origin in reference_baseline.get('origins', [])
    }
    updated_origins = []
    for origin in rolling_origin['origins']:
        updated_origins.append(
            _rewrite_origin_n_eff_summary(
                origin=origin,
                baseline_origin=baseline_origins.get(int(origin['origin_ts'])),
            )
        )
    return {
        **rolling_origin,
        'origins': updated_origins,
        'n_eff_summary': collect_origin_artifacts(updated_origins, artifact_key='n_eff_summary'),
    }


def _rewrite_origin_n_eff_summary(
    *,
    origin: dict[str, object],
    baseline_origin: dict[str, object] | None,
) -> dict[str, object]:
    if baseline_origin is None:
        raise ValueError(f"missing reference baseline origin for {origin['origin_ts']}")
    challenger_scores = [float(value) for value in origin.get('forecast_score_sequence', [])]
    baseline_scores = [float(value) for value in baseline_origin.get('forecast_score_sequence', [])]
    if len(challenger_scores) != len(baseline_scores) or not challenger_scores:
        raise ValueError(f"invalid comparison delta sequence for origin {origin['origin_ts']}")
    delta_sequence = _build_decimal_score_delta_sequence(
        challenger_scores=challenger_scores,
        baseline_scores=baseline_scores,
    )
    existing_n_eff = dict(origin.get('n_eff_summary', {}))
    sequences = dict(existing_n_eff.get('sequences', {}))
    sequences['model_comparison_delta_sequence'] = build_sequence_summary(
        field_name='challenger_score_minus_locked_baseline_score',
        sequence_ref='artifact://n-eff/model-comparison-delta-sequence.json',
        sequence_role='pairwise_model_difference',
        sequence=delta_sequence,
    )
    return {
        **origin,
        'n_eff_summary': {
            **existing_n_eff,
            'truncation_rule': existing_n_eff.get('truncation_rule', 'initial_positive_sequence_v1'),
            'sequences': sequences,
        },
    }


def _build_decimal_score_delta_sequence(
    *,
    challenger_scores: list[float],
    baseline_scores: list[float],
) -> list[float]:
    return [
        float(Decimal(str(challenger_score)) - Decimal(str(baseline_score)))
        for challenger_score, baseline_score in zip(challenger_scores, baseline_scores)
    ]


def _flatten_origin_sequence(origins: list[dict[str, object]], *, sequence_key: str) -> list[float]:
    return [
        float(value)
        for origin in origins
        for value in origin.get(sequence_key, [])
    ]


def _flatten_bundle_sequence(
    origins: list[dict[str, object]],
    *,
    bundle_key: str,
    sequence_key: str,
) -> list[float]:
    return [
        float(value)
        for origin in origins
        for value in origin.get(bundle_key, {}).get(sequence_key, [])
    ]
