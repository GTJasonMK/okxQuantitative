from __future__ import annotations

from app.core.research_platform.training.evaluation import evaluate_forecast_batch


def test_weighted_joint_scores_and_regime_summary():
    summary = evaluate_forecast_batch(
        observations=[{'r_open': 0.0, 'r_close': 0.01, 'u': 0.02, 'd': 0.01}],
        samples=[[{'r_open': 0.0, 'r_close': 0.009, 'u': 0.018, 'd': 0.011}]],
        joint_nll_values=[0.02],
        sample_weights=[1.0],
        comparison_delta_sequence=[-0.05],
        regimes=[
            {
                'hour_of_day': 8,
                'day_of_week': 6,
                'realized_vol_bin': 1,
                'spread_bin': 0,
                'liquidity_bin': 2,
                'funding_regime': 'neutral',
            }
        ],
    )

    assert 'joint_nll' in summary['forecast_metrics']
    assert 'energy_score' in summary['forecast_metrics']
    assert 'weighted_diagnostics' in summary
    assert 'multivariate_rank_histogram' in summary['weighted_diagnostics']
    assert 'prerank_diagnostics' in summary['weighted_diagnostics']
    assert 'price_reconstruction_diagnostics' in summary['weighted_diagnostics']
    assert 'n_eff_summary' in summary
    assert 'regime_metrics' in summary
    assert summary['weighted_diagnostics']['weight_normalization']['formula'] == 'w_i^norm = w_i / sum_j w_j'
    assert summary['weighted_diagnostics']['multivariate_rank_histogram']['rank_scheme'] == 'band_depth_rank_v1'
    assert abs(sum(summary['weighted_diagnostics']['multivariate_rank_histogram']['bin_counts']) - 1.0) < 1e-9
    assert summary['unweighted_diagnostics']['weight_reference_distribution'] == 'Q'
    assert 'marginal_coverage' in summary['weighted_diagnostics']
    assert 'weighted_pit' in summary['weighted_diagnostics']
    assert 'r_close' in summary['weighted_diagnostics']['marginal_coverage']['stats']
    assert 'coverage_rate' in summary['weighted_diagnostics']['marginal_coverage']['stats']['r_close']
    assert 'r_close' in summary['weighted_diagnostics']['weighted_pit']['stats']
    assert 'weighted_mean' in summary['weighted_diagnostics']['weighted_pit']['stats']['r_close']
    assert 'level_prerank' in summary['weighted_diagnostics']['prerank_diagnostics']['stats']
    assert 'weighted_mean_abs_error' in summary['weighted_diagnostics']['prerank_diagnostics']['stats']['level_prerank']
    assert 'open_bps_error' in summary['weighted_diagnostics']['price_reconstruction_diagnostics']['metrics']
    assert 'weighted_mean_abs_error' in summary['weighted_diagnostics']['price_reconstruction_diagnostics']['metrics']['open_bps_error']
    assert summary['regime_metrics']['schema']['required_fields'] == [
        'hour_of_day',
        'day_of_week',
        'realized_vol_bin',
        'spread_bin',
        'liquidity_bin',
        'funding_regime',
    ]
    assert summary['regime_metrics']['rows'][0]['joint_nll_mean'] >= 0.0
    assert summary['regime_metrics']['rows'][0]['energy_score_mean'] >= 0.0
    assert summary['regime_metrics']['rows'][0]['variogram_score_mean'] >= 0.0
    assert 'calibration_error' in summary['regime_metrics']['rows'][0]
    assert 'sharpness_mean' in summary['regime_metrics']['rows'][0]
    assert summary['n_eff_summary']['truncation_rule'] == 'initial_positive_sequence_v1'
    assert summary['n_eff_summary']['sequences']['label_r_close_sequence']['field_name'] == 'r_close'
    assert 'estimate' in summary['n_eff_summary']['sequences']['primary_validation_score_sequence']
    assert 'estimate' in summary['n_eff_summary']['sequences']['label_r_close_sequence']
    assert 'estimate' in summary['n_eff_summary']['sequences']['model_comparison_delta_sequence']
    assert summary['n_eff_summary']['sequences']['model_comparison_delta_sequence']['value_summary']['mean'] == -0.05


def test_forecast_metrics_use_raw_importance_weights_without_self_normalization():
    summary = evaluate_forecast_batch(
        observations=[
            {'r_open': 0.0, 'r_close': 0.01, 'u': 0.02, 'd': 0.01},
            {'r_open': 0.0, 'r_close': 0.01, 'u': 0.02, 'd': 0.01},
        ],
        samples=[
            [{'r_open': 0.0, 'r_close': 0.009, 'u': 0.018, 'd': 0.011}],
            [{'r_open': 0.0, 'r_close': 0.012, 'u': 0.022, 'd': 0.012}],
        ],
        joint_nll_values=[1.0, 5.0],
        sample_weights=[3.0, 1.0],
        comparison_delta_sequence=[-0.1, 0.2],
        regimes=[
            {
                'hour_of_day': 8,
                'day_of_week': 6,
                'realized_vol_bin': 1,
                'spread_bin': 0,
                'liquidity_bin': 2,
                'funding_regime': 'neutral',
            },
            {
                'hour_of_day': 9,
                'day_of_week': 6,
                'realized_vol_bin': 1,
                'spread_bin': 0,
                'liquidity_bin': 2,
                'funding_regime': 'neutral',
            },
        ],
    )

    assert summary['forecast_metrics']['joint_nll'] == 4.0
    assert summary['weighted_diagnostics']['weight_normalization']['formula'] == 'w_i^norm = w_i / sum_j w_j'
