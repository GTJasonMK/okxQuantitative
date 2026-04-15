from __future__ import annotations

from app.core.research_platform.training import origin_pipeline


def test_build_origin_bundle_uses_fold_local_forecasts_for_inner_validation(monkeypatch):
    calls: list[dict[str, list[int]]] = []
    captured_forecast_batch: dict[str, object] = {}

    def fake_build_weighting_bundle(**kwargs):
        return ({'weighting_version': 'uniform'}, [1.0])

    def fake_build_origin_forecast_bundle(*, fit_rows, scored_rows, **kwargs):
        calls.append(
            {
                'fit_decision_ts': [int(row['decision_ts']) for row in fit_rows],
                'scored_decision_ts': [int(row['decision_ts']) for row in scored_rows],
            }
        )
        predicted_rows = [
            {
                **row,
                'forecast_r_open': 0.0,
                'forecast_r_close': float(row['r_close']),
                'forecast_u': float(row['u']),
                'forecast_d': float(row['d']),
            }
            for row in scored_rows
        ]
        sample_sets = [
            [
                {
                    'r_open': 0.0,
                    'r_close': float(row['r_close']),
                    'u': float(row['u']),
                    'd': float(row['d']),
                }
            ]
            for row in scored_rows
        ]
        return {
            'predicted_rows': predicted_rows,
            'sample_sets': sample_sets,
            'joint_nll_values': [0.1 for _ in scored_rows],
            'generation_summary': {'sample_count': 1},
        }

    def fake_fit_origin_decision_parameters(**kwargs):
        return {
            'policy_parameters': {'tau_entry': 0.0, 'tau_switch': 0.0},
            'utility_parameters': {'slippage_const_bps': 1.0, 'lambda_ae': 0.5, 'previous_action': 0},
            'policy_selection': {'selection_method': 'inner_validation_grid_search_v1'},
            'utility_selection': {'selection_method': 'inner_validation_grid_search_v1'},
        }

    monkeypatch.setattr(origin_pipeline, 'build_weighting_bundle', fake_build_weighting_bundle)
    monkeypatch.setattr(origin_pipeline, 'build_origin_forecast_bundle', fake_build_origin_forecast_bundle)
    monkeypatch.setattr(origin_pipeline, 'fit_origin_decision_parameters', fake_fit_origin_decision_parameters)
    monkeypatch.setattr(
        origin_pipeline,
        'evaluate_forecast_batch',
        lambda **kwargs: _capture_forecast_batch(
            captured_forecast_batch,
            kwargs,
        ),
    )
    monkeypatch.setattr(origin_pipeline, '_build_decision_metrics', lambda *args, **kwargs: {'mean_utility': 0.0})

    origin_pipeline.build_origin_bundle(
        storage=object(),
        manifest={'dataset_id': 'dataset-1'},
        run={'training_seed': 7},
        split_row={
            'origin_ts': 4000,
            'test_start_ts': 4900,
            'test_end_ts': 5000,
            'census_window_end_ts': 3900,
            'inner_validation_folds': [
                {
                    'fold_id': 'fold-1',
                    'train_start_ts': 1000,
                    'train_end_ts': 1000,
                    'validation_start_ts': 2000,
                    'validation_end_ts': 2000,
                },
                {
                    'fold_id': 'fold-2',
                    'train_start_ts': 1000,
                    'train_end_ts': 2000,
                    'validation_start_ts': 3000,
                    'validation_end_ts': 3000,
                },
            ],
        },
        qualified_rows=[
            _build_row(1000),
            _build_row(2000),
            _build_row(3000),
            _build_row(5000),
        ],
        census_rows=[{'decision_ts': 3800}],
    )

    assert calls == [
        {'fit_decision_ts': [1000], 'scored_decision_ts': [2000]},
        {'fit_decision_ts': [1000, 2000], 'scored_decision_ts': [3000]},
        {'fit_decision_ts': [1000, 2000, 3000], 'scored_decision_ts': [5000]},
    ]
    assert 'comparison_delta_sequence' not in captured_forecast_batch
    assert captured_forecast_batch['regimes'] == [
        {
            'hour_of_day': 0,
            'day_of_week': 1,
            'realized_vol_bin': 0,
            'spread_bin': 0,
            'liquidity_bin': 2,
            'funding_regime': 'neutral',
        }
    ]


def _build_row(decision_ts: int) -> dict[str, object]:
    return {
        'session_id': 'sess-1',
        'inst_id': 'BTC-USDT-SWAP',
        'decision_ts': decision_ts,
        'hour_of_day': 0,
        'day_of_week': 1,
        'liquidity_snapshot_bin': 2,
        'realized_vol_proxy_2h': 20.0,
        'spread_snapshot_bps': 0.01,
        'funding_regime': 'neutral',
        'r_open': 0.0,
        'r_close': 0.001,
        'u': 0.0002,
        'd': 0.0002,
    }


def _capture_forecast_batch(store: dict[str, object], kwargs: dict[str, object]) -> dict[str, object]:
    store.update(kwargs)
    return {
        'forecast_metrics': {'joint_nll': 0.1, 'energy_score': 0.1, 'variogram_score': 0.1},
        'weighted_diagnostics': {},
        'unweighted_diagnostics': {},
        'regime_metrics': {},
        'n_eff_summary': {},
    }
