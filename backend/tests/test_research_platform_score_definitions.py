from __future__ import annotations

import pytest

from app.core.research_platform.training.evaluation import evaluate_forecast_batch
from app.core.research_platform.training.sample_scores import variogram_score


def test_variogram_score_uses_sample_expectation_definition():
    score = variogram_score(
        observation={'r_open': 0.0, 'r_close': 1.0, 'u': 0.0, 'd': 0.0},
        sample_set=[
            {'r_open': 0.0, 'r_close': 0.0, 'u': 0.0, 'd': 0.0},
            {'r_open': 0.0, 'r_close': 4.0, 'u': 0.0, 'd': 0.0},
        ],
    )

    assert score == pytest.approx(0.0)


def test_regime_summary_reports_formal_joint_scores():
    summary = evaluate_forecast_batch(
        observations=[{'r_open': 0.0, 'r_close': 1.0, 'u': 0.0, 'd': 0.0}],
        samples=[[
            {'r_open': 0.0, 'r_close': 0.0, 'u': 0.0, 'd': 0.0},
            {'r_open': 0.0, 'r_close': 4.0, 'u': 0.0, 'd': 0.0},
        ]],
        joint_nll_values=[0.25],
        sample_weights=[1.0],
        comparison_delta_sequence=[0.0],
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

    regime_row = summary['regime_metrics']['rows'][0]

    assert regime_row['joint_nll_mean'] == pytest.approx(summary['forecast_metrics']['joint_nll'])
    assert regime_row['energy_score_mean'] == pytest.approx(summary['forecast_metrics']['energy_score'])
    assert regime_row['variogram_score_mean'] == pytest.approx(summary['forecast_metrics']['variogram_score'])
