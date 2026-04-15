from __future__ import annotations

import pytest

from app.core.research_platform.training.decision_refit import fit_origin_decision_parameters


def _forecast_sample(*, r_open: float, r_close: float, u: float, d: float) -> dict[str, float]:
    return {
        'r_open': r_open,
        'r_close': r_close,
        'u': u,
        'd': d,
    }


def test_fit_origin_decision_parameters_uses_inner_validation_grid_search():
    result = fit_origin_decision_parameters(
        split_row={
            'origin_ts': 4000,
            'inner_validation_folds': [
                {
                    'fold_id': 'fold-1',
                    'origin_ts': 4000,
                    'validation_start_ts': 1000,
                    'validation_end_ts': 1900,
                    'embargo_sec': 8100,
                },
                {
                    'fold_id': 'fold-2',
                    'origin_ts': 4000,
                    'validation_start_ts': 2000,
                    'validation_end_ts': 2900,
                    'embargo_sec': 8100,
                },
            ],
        },
        fold_rows=[
            {
                'fold_id': 'fold-1',
                'rows': [
                    {
                        'decision_ts': 1000,
                        'r_open': 0.0,
                        'r_close': -0.0008,
                        'u': 0.0004,
                        'd': 0.0010,
                        'spread_snapshot_bps': 0.001,
                    },
                ],
                'forecast_sample_sets': [
                    [
                        _forecast_sample(
                            r_open=0.0,
                            r_close=0.0012,
                            u=0.0002,
                            d=0.0002,
                        )
                    ]
                ],
            },
            {
                'fold_id': 'fold-2',
                'rows': [
                    {
                        'decision_ts': 2000,
                        'r_open': 0.0,
                        'r_close': -0.0007,
                        'u': 0.0004,
                        'd': 0.0010,
                        'spread_snapshot_bps': 0.001,
                    },
                ],
                'forecast_sample_sets': [
                    [
                        _forecast_sample(
                            r_open=0.0,
                            r_close=0.0011,
                            u=0.0002,
                            d=0.0002,
                        )
                    ]
                ],
            },
        ],
    )

    assert result['policy_selection']['selection_method'] == 'inner_validation_grid_search_v1'
    assert result['policy_selection']['selected_fold_count'] == 2
    assert result['policy_selection']['candidate_count'] >= 2
    assert result['policy_parameters']['tau_entry'] > 0.0
    assert result['utility_selection']['selection_method'] == 'inner_validation_grid_search_v1'
    assert result['utility_selection']['candidate_count'] >= 2


def test_fit_origin_decision_parameters_selects_utility_parameters_from_inner_validation():
    result = fit_origin_decision_parameters(
        split_row={
            'origin_ts': 4000,
            'inner_validation_folds': [
                {
                    'fold_id': 'fold-1',
                    'origin_ts': 4000,
                    'validation_start_ts': 1000,
                    'validation_end_ts': 1900,
                    'embargo_sec': 8100,
                },
            ],
        },
        fold_rows=[
            {
                'fold_id': 'fold-1',
                'rows': [
                    {
                        'decision_ts': 1000,
                        'r_open': 0.0,
                        'r_close': 0.0020,
                        'u': 0.0001,
                        'd': 0.0001,
                        'spread_snapshot_bps': 0.001,
                    },
                    {
                        'decision_ts': 1010,
                        'r_open': 0.0,
                        'r_close': -0.0060,
                        'u': 0.0002,
                        'd': 0.0060,
                        'spread_snapshot_bps': 0.001,
                    },
                ],
                'forecast_sample_sets': [
                    [
                        _forecast_sample(
                            r_open=0.0,
                            r_close=0.0020,
                            u=0.0001,
                            d=0.0001,
                        )
                    ],
                    [
                        _forecast_sample(
                            r_open=0.0,
                            r_close=0.0050,
                            u=0.0001,
                            d=0.0040,
                        )
                    ],
                ],
            },
        ],
    )

    assert result['utility_parameters']['lambda_ae'] == 1.0
    assert result['utility_selection']['selection_method'] == 'inner_validation_grid_search_v1'
    assert result['utility_selection']['selection_source'] == 'inner_validation'


def test_fit_origin_decision_parameters_rejects_missing_inner_validation_rows():
    with pytest.raises(ValueError, match='protocol-invalid: no complete inner-validation folds'):
        fit_origin_decision_parameters(
            split_row={
                'origin_ts': 4000,
                'inner_validation_folds': [
                    {
                        'fold_id': 'fold-1',
                        'origin_ts': 4000,
                        'validation_start_ts': 1000,
                        'validation_end_ts': 1900,
                        'embargo_sec': 8100,
                    },
                ],
            },
            fold_rows=[],
        )
