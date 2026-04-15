from __future__ import annotations

import pytest

from app.core.research_platform.training.comparison import (
    build_comparison_result,
    build_locked_candidate_comparison_result,
)


def test_build_comparison_result_materializes_delta_sequence_and_bootstrap():
    result = build_comparison_result(
        challenger_scores=[0.2, 0.15, 0.18],
        baseline_scores=[0.3, 0.2, 0.21],
        candidate_set_ref='artifact://candidate-set/locked-v1.json',
        retained_model_set=['unconditional_distribution_baseline', 'joint_density_model_v1'],
    )

    assert result['multiple_comparison_version'] == 'locked_candidate_set_v1'
    assert result['candidate_set_ref'] == 'artifact://candidate-set/locked-v1.json'
    assert result['retained_model_set'] == ['unconditional_distribution_baseline', 'joint_density_model_v1']
    assert result['delta_by_origin'] == [-0.09999999999999998, -0.05000000000000002, -0.03]
    assert result['paired_block_bootstrap_result']['definition_version'] == 'stationary_block_bootstrap_min9_v1'
    assert result['paired_block_bootstrap_result']['avg_block_length'] == 9
    assert 'ci_95' in result['paired_block_bootstrap_result']


def test_build_comparison_result_rejects_mismatched_sequence_lengths():
    with pytest.raises(ValueError, match='score sequences must have the same length'):
        build_comparison_result(
            challenger_scores=[0.2, 0.15],
            baseline_scores=[0.3],
            candidate_set_ref='artifact://candidate-set/locked-v1.json',
            retained_model_set=['baseline', 'challenger'],
        )


def test_build_locked_candidate_comparison_result_uses_reference_baseline():
    result = build_locked_candidate_comparison_result(
        challenger_origins=[
            {'origin_ts': 1000, 'forecast_metrics': {'joint_nll': 0.20}, 'forecast_score_sequence': [0.19, 0.20, 0.21]},
            {'origin_ts': 1900, 'forecast_metrics': {'joint_nll': 0.15}, 'forecast_score_sequence': [0.14, 0.15]},
        ],
        challenger_id='joint_density_model_v1',
        baseline_bundle={
            'baselines': [
                {
                    'baseline_id': 'unconditional_distribution_baseline',
                    'baseline_model': 'empirical_joint_distribution_v1',
                    'origins': [
                        {'origin_ts': 1000, 'forecast_metrics': {'joint_nll': 0.25}, 'forecast_score_sequence': [0.24, 0.25, 0.26]},
                        {'origin_ts': 1900, 'forecast_metrics': {'joint_nll': 0.19}, 'forecast_score_sequence': [0.18, 0.20]},
                    ],
                },
                {
                    'baseline_id': 'independent_marginal_baseline',
                    'baseline_model': 'independent_marginal_distribution_v1',
                    'origins': [
                        {'origin_ts': 1000, 'forecast_metrics': {'joint_nll': 0.21}, 'forecast_score_sequence': [0.20, 0.21, 0.22]},
                        {'origin_ts': 1900, 'forecast_metrics': {'joint_nll': 0.16}, 'forecast_score_sequence': [0.15, 0.17]},
                    ],
                },
                {
                    'baseline_id': 'point_baseline',
                    'baseline_model': 'zero_body_median_shadow_v1',
                    'origins': [
                        {'origin_ts': 1000, 'forecast_metrics': {'joint_nll': 0.40}, 'forecast_score_sequence': [0.39, 0.40, 0.41]},
                        {'origin_ts': 1900, 'forecast_metrics': {'joint_nll': 0.35}, 'forecast_score_sequence': [0.34, 0.36]},
                    ],
                },
            ]
        },
        candidate_set_ref='artifact://candidate-set/locked-v1.json',
    )

    assert result['baseline_id'] == 'unconditional_distribution_baseline'
    assert result['best_candidate_id'] == 'joint_density_model_v1'
    assert result['reference_candidate_id'] == 'joint_density_model_v1'
    assert result['candidate_ranking'][0]['candidate_id'] == 'joint_density_model_v1'
    assert result['candidate_ranking'][-1]['candidate_id'] == 'point_baseline'
    assert len(result['pairwise_results']) == 3
    assert result['pairwise_results'][0]['candidate_id'] == 'unconditional_distribution_baseline'
    assert result['pairwise_results'][0]['reference_candidate_id'] == 'joint_density_model_v1'
    assert result['pairwise_results'][0]['delta_by_origin'] == [0.04999999999999999, 0.04000000000000001]
    assert result['paired_block_bootstrap_result']['sample_count'] == 5
    assert result['pairwise_results'][0]['paired_block_bootstrap_result']['sample_count'] == 5
    assert 'joint_density_model_v1' in result['retained_model_set']
    assert result['data_snooping_control']['candidate_set_locked_before_outer_test'] is True
    assert result['data_snooping_control']['retention_rule'] == 'best_relative_stationary_block_ci_v1'
