from __future__ import annotations

from copy import deepcopy

from app.core.research_platform.training import artifacts as training_artifacts
from app.core.research_platform.training.artifacts import build_split_artifact


def test_build_training_artifacts_rewrites_n_eff_comparison_delta_from_reference_baseline(monkeypatch):
    origin_n_eff_a = _build_n_eff_summary()
    origin_n_eff_b = _build_n_eff_summary()
    rolling_origin = {
        'origins': [
            {
                'origin_ts': 1000,
                'forecast_score_sequence': [0.20, 0.15],
                'forecast_metrics': {'joint_nll': 0.175},
                'decision_metrics': {'mean_utility': 0.01},
                'weighted_diagnostics': {},
                'unweighted_diagnostics': {},
                'regime_metrics': {},
                'n_eff_summary': origin_n_eff_a,
            },
            {
                'origin_ts': 1900,
                'forecast_score_sequence': [0.18, 0.12],
                'forecast_metrics': {'joint_nll': 0.15},
                'decision_metrics': {'mean_utility': 0.02},
                'weighted_diagnostics': {},
                'unweighted_diagnostics': {},
                'regime_metrics': {},
                'n_eff_summary': origin_n_eff_b,
            },
        ],
        'forecast_metrics': {'joint_nll': {'mean': 0.16}},
        'decision_metrics': {'mean_utility': {'mean': 0.015}},
        'weighted_diagnostics': {'by_origin': []},
        'unweighted_diagnostics': {'by_origin': []},
        'regime_metrics': {'by_origin': []},
        'n_eff_summary': {
            'origin_count': 2,
            'by_origin': [
                {'origin_ts': 1000, 'n_eff_summary': origin_n_eff_a},
                {'origin_ts': 1900, 'n_eff_summary': origin_n_eff_b},
            ],
        },
    }
    baseline_result = {
        'baselines': [
            {
                'baseline_id': 'unconditional_distribution_baseline',
                'origins': [
                    {'origin_ts': 1000, 'forecast_score_sequence': [0.25, 0.19]},
                    {'origin_ts': 1900, 'forecast_score_sequence': [0.22, 0.17]},
                ],
            }
        ]
    }

    monkeypatch.setattr(training_artifacts, 'load_qualified_rows', lambda *args, **kwargs: ([], []))
    monkeypatch.setattr(training_artifacts, 'build_split_artifact', lambda **kwargs: {'origins': []})
    monkeypatch.setattr(training_artifacts, 'build_rolling_origin_evaluation', lambda **kwargs: deepcopy(rolling_origin))
    monkeypatch.setattr(training_artifacts, 'build_baseline_bundle', lambda **kwargs: deepcopy(baseline_result))
    monkeypatch.setattr(training_artifacts, 'build_locked_candidate_comparison_result', lambda **kwargs: {'best_candidate_id': 'joint_density_model_v1'})
    monkeypatch.setattr(training_artifacts, 'build_training_artifact_summary', lambda **kwargs: dict(kwargs))
    monkeypatch.setattr(
        training_artifacts,
        'finalize_training_run_parameter_refs',
        lambda **kwargs: {
            'policy_parameter_ref': 'artifact://policy',
            'utility_parameter_ref': 'artifact://utility',
            'weight_fit_ref': 'artifact://weight',
        },
    )
    monkeypatch.setattr(training_artifacts, 'build_policy_parameter_bundle', lambda **kwargs: {})
    monkeypatch.setattr(training_artifacts, 'build_utility_parameter_bundle', lambda **kwargs: {})
    monkeypatch.setattr(training_artifacts, 'build_execution_assumption_bundle', lambda **kwargs: {})
    monkeypatch.setattr(training_artifacts, 'build_candidate_set_bundle', lambda **kwargs: {})
    monkeypatch.setattr(training_artifacts, 'build_weight_fit_bundles', lambda **kwargs: {})
    monkeypatch.setattr(training_artifacts, '_build_bootstrap_result', lambda *_args, **_kwargs: {})

    artifacts, _ = training_artifacts.build_training_artifacts(
        storage=object(),
        manifest={'weighting_version': 'strata_ratio_weighting'},
        run={
            'run_id': 'run-1',
            'model_family': 'joint_density_model_v1',
            'candidate_set_ref': 'candidate://locked/default-v1',
            'execution_assumption_version': 'boundary_rebalance_hold_to_close_v1',
        },
    )

    first_delta = artifacts['n_eff_summary']['by_origin'][0]['n_eff_summary']['sequences']['model_comparison_delta_sequence']
    second_delta = artifacts['n_eff_summary']['by_origin'][1]['n_eff_summary']['sequences']['model_comparison_delta_sequence']

    assert first_delta['value_summary']['mean'] == -0.045
    assert second_delta['value_summary']['mean'] == -0.045


def test_build_split_artifact_materializes_refit_protocol_metadata():
    artifact = build_split_artifact(
        manifest={
            'split_definition_version': 'blocked_temporal_hv_v1',
            'embargo_sec': 8100,
            'refit_policy_version': 'expanding_refit_recompute_all_statistics_v1',
        },
        qualified_rows=[
            {'decision_ts': 1713000900 + (index * 900)}
            for index in range(24)
        ],
    )

    assert artifact['definition_version'] == 'blocked_temporal_hv_v1'
    assert artifact['refit_policy_version'] == 'expanding_refit_recompute_all_statistics_v1'
    assert artifact['refit_policy']['window_type'] == 'expanding'
    assert artifact['refit_policy']['recompute_statistics_per_origin'] is True
    assert artifact['refit_policy']['model_frozen_within_test_block'] is True
    assert artifact['origins'][0]['pre_origin_fit_end_ts'] == artifact['origins'][0]['origin_ts'] - 900


def _build_n_eff_summary() -> dict[str, object]:
    return {
        'truncation_rule': 'initial_positive_sequence_v1',
        'sequences': {
            'model_comparison_delta_sequence': {
                'field_name': 'challenger_score_minus_locked_baseline_score',
                'sequence_ref': 'artifact://n-eff/model-comparison-delta-sequence.json',
                'sequence_role': 'pairwise_model_difference',
                'estimate': 2.0,
                'value_summary': {
                    'count': 2,
                    'mean': 0.0,
                    'min': 0.0,
                    'max': 0.0,
                },
            },
        },
    }
