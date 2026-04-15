from __future__ import annotations

from app.core.research_platform.training.decision_policy import (
    compute_bar_utility,
    evaluate_decision_path,
)


def test_bar_close_return_with_adverse_excursion_penalty():
    utility = compute_bar_utility(
        action=1,
        r_close=0.01,
        r_open=0.002,
        u=0.008,
        d=0.004,
        spread_last_bps=4.0,
        slippage_const_bps=1.0,
        previous_action=0,
        lambda_ae=0.5,
    )

    assert utility < 0.01


def test_evaluate_decision_path_uses_ternary_policy_and_reports_metrics():
    result = evaluate_decision_path(
        forecast_sample_sets=[
            [{'r_open': 0.001, 'r_close': 0.010, 'u': 0.003, 'd': 0.002}],
            [{'r_open': -0.001, 'r_close': -0.008, 'u': 0.002, 'd': 0.003}],
            [{'r_open': 0.0, 'r_close': 0.0, 'u': 0.001, 'd': 0.001}],
        ],
        realized_rows=[
            {'r_open': 0.001, 'r_close': 0.012, 'u': 0.004, 'd': 0.002},
            {'r_open': -0.001, 'r_close': -0.010, 'u': 0.002, 'd': 0.003},
            {'r_open': 0.0, 'r_close': 0.0, 'u': 0.001, 'd': 0.001},
        ],
        spread_last_bps=[8.0, 8.0, 8.0],
        policy_parameters={'tau_entry': 0.0, 'tau_switch': 0.0},
        utility_parameters={
            'slippage_const_bps': 1.0,
            'lambda_ae': 0.5,
            'previous_action': 0,
        },
        execution_assumption_version='boundary_rebalance_hold_to_close_v1',
    )

    assert result['action_path'] == [1, -1, 0]
    assert result['mean_utility'] != 0.0
    assert 'net_return' in result
    assert 'max_drawdown' in result
    assert 'turnover_mean' in result
    assert 'hit_rate' in result
    assert 'exposure_rate' in result
    assert 'downside_tail_risk' in result


def test_evaluate_decision_path_uses_sample_set_expected_utility():
    result = evaluate_decision_path(
        forecast_sample_sets=[
            [
                {'r_open': 0.0, 'r_close': 0.030, 'u': 0.001, 'd': 0.001},
                {'r_open': 0.0, 'r_close': -0.010, 'u': 0.0, 'd': 0.090},
            ]
        ],
        realized_rows=[
            {'r_open': 0.0, 'r_close': 0.0, 'u': 0.0, 'd': 0.0},
        ],
        spread_last_bps=[8.0],
        policy_parameters={'tau_entry': 0.0, 'tau_switch': 0.0},
        utility_parameters={
            'slippage_const_bps': 1.0,
            'lambda_ae': 0.5,
            'previous_action': 0,
        },
        execution_assumption_version='boundary_rebalance_hold_to_close_v1',
    )

    assert result['action_path'] == [0]
