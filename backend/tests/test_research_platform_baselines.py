from __future__ import annotations

from app.core.research_platform.training import baselines
from app.core.research_platform.training.baselines import build_baseline_bundle


def test_build_baseline_bundle_materializes_real_distribution_baselines(monkeypatch):
    monkeypatch.setattr(
        baselines,
        'build_weighting_bundle',
        lambda **kwargs: ({'weighting_version': 'uniform'}, [1.0]),
    )

    result = build_baseline_bundle(
        manifest={
            'weighting_version': 'strata_ratio_weighting',
            'weight_estimator_version': 'exact_strata_ratio_v1',
            'weight_definition': 'raw_ratio_no_clip_no_self_normalization',
        },
        split_artifact={
            'origins': [
                {
                    'origin_ts': 5000,
                    'test_start_ts': 5000,
                    'test_end_ts': 5000,
                    'census_window_end_ts': 4500,
                }
            ],
        },
        qualified_rows=[
            _build_row(1000, r_open=0.10, r_close=0.20, u=0.30, d=0.40),
            _build_row(2000, r_open=-0.10, r_close=0.00, u=0.50, d=0.60),
            _build_row(5000, r_open=0.02, r_close=0.12, u=0.45, d=0.55),
        ],
        census_rows=[],
        challenger_origins=[
            {
                'origin_ts': 5000,
                'policy_parameters': {'tau_entry': 0.0, 'tau_switch': 0.0},
                'utility_parameters': {'slippage_const_bps': 1.0, 'lambda_ae': 0.5, 'previous_action': 0},
                'decision_metrics': {
                    'mean_utility': 0.015,
                    'net_return': 0.020,
                    'max_drawdown': -0.005,
                    'turnover_mean': 1.0,
                    'hit_rate': 0.60,
                    'exposure_rate': 0.70,
                    'downside_tail_risk': -0.004,
                },
            }
        ]
    )

    assert len(result['baselines']) == 3
    unconditional = result['baselines'][0]
    independent = result['baselines'][1]
    point = result['baselines'][2]

    assert unconditional['baseline_id'] == 'unconditional_distribution_baseline'
    assert unconditional['baseline_model'] == 'empirical_joint_distribution_v1'
    assert unconditional['origins'][0]['origin_ts'] == 5000
    assert unconditional['origins'][0]['prediction_summary']['train_sample_count'] == 2
    assert unconditional['origins'][0]['prediction_summary']['sample_count'] == 32
    assert unconditional['origins'][0]['prediction_summary']['forecast_mean']['r_open'] == 0.0
    assert unconditional['origins'][0]['prediction_summary']['forecast_mean']['r_close'] == 0.1
    assert unconditional['origins'][0]['prediction_summary']['forecast_mean']['u'] == 0.4
    assert unconditional['origins'][0]['prediction_summary']['forecast_mean']['d'] == 0.5
    assert unconditional['origins'][0]['forecast_metrics']['joint_nll'] < 10.0

    assert independent['baseline_id'] == 'independent_marginal_baseline'
    assert independent['origins'][0]['prediction_summary']['forecast_mean']['r_close'] == 0.1

    assert point['baseline_id'] == 'point_baseline'
    assert point['origins'][0]['prediction_summary']['forecast_mean']['r_open'] == 0.0
    assert point['origins'][0]['prediction_summary']['forecast_mean']['r_close'] == 0.0
    assert point['origins'][0]['prediction_summary']['forecast_mean']['u'] == 0.4
    assert point['origins'][0]['prediction_summary']['forecast_mean']['d'] == 0.5
    assert 'net_return' in point['origins'][0]['decision_metrics']
    assert 'max_drawdown' in point['origins'][0]['decision_metrics']
    assert 'turnover_mean' in point['origins'][0]['decision_metrics']
    assert 'hit_rate' in point['origins'][0]['decision_metrics']
    assert 'exposure_rate' in point['origins'][0]['decision_metrics']
    assert 'downside_tail_risk' in point['origins'][0]['decision_metrics']


def _build_row(
    decision_ts: int,
    *,
    r_open: float,
    r_close: float,
    u: float,
    d: float,
) -> dict[str, object]:
    return {
        'session_id': 'sess-1',
        'inst_id': 'BTC-USDT-SWAP',
        'decision_ts': decision_ts,
        'hour_of_day': 8,
        'day_of_week': 1,
        'realized_vol_proxy_2h': 10.0,
        'liquidity_snapshot_bin': 1,
        'spread_snapshot_bps': 0.01,
        'funding_regime': 'neutral',
        'shift_state': {
            'slot_15m': 0,
            'weekend_flag': 0,
            'near_funding_flag': 0,
            'rv_2h_bps': 10.0,
            'depth_10bps_log': 2.0,
            'spread_median_60s_bps': 0.1,
        },
        'r_open': r_open,
        'r_close': r_close,
        'u': u,
        'd': d,
    }
