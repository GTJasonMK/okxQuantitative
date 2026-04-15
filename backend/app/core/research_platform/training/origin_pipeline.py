from __future__ import annotations

from .decision_policy import EXECUTION_ASSUMPTION_VERSION, evaluate_decision_path
from .decision_refit import fit_origin_decision_parameters
from .evaluation import evaluate_forecast_batch
from .forecast_projection import build_observation_row
from .forecast_projection import build_spread_last_bps
from .joint_forecasts import build_origin_forecast_bundle
from .origin_weighting import build_weighting_bundle
from .regime_rows import build_regime_row


def build_origin_bundle(
    *,
    storage,
    manifest: dict[str, object],
    run: dict[str, object],
    split_row: dict[str, object],
    qualified_rows: list[dict[str, object]],
    census_rows: list[dict[str, object]],
) -> dict[str, object]:
    origin_ts = int(split_row['origin_ts'])
    fit_rows = _select_fit_rows(qualified_rows, split_row=split_row)
    test_rows = _select_test_rows(qualified_rows, split_row=split_row)
    if not test_rows:
        raise ValueError(f'rolling-origin split produced empty test rows for origin {origin_ts}')
    origin_census_rows = _select_origin_census_rows(census_rows, split_row=split_row)
    weighting, sample_weights = build_weighting_bundle(
        manifest=manifest,
        origin_ts=origin_ts,
        fit_rows=fit_rows,
        test_rows=test_rows,
        census_rows=origin_census_rows,
    )
    inner_validation_folds = _build_inner_validation_fold_rows(
        storage=storage,
        split_row=split_row,
        qualified_rows=fit_rows,
        training_seed=int(run['training_seed']),
        origin_ts=origin_ts,
    )
    forecast_bundle = build_origin_forecast_bundle(
        storage=storage,
        fit_rows=fit_rows,
        scored_rows=test_rows,
        training_seed=int(run['training_seed']),
        origin_ts=origin_ts,
    )
    predicted_rows = forecast_bundle['predicted_rows']
    decision_refit = fit_origin_decision_parameters(
        split_row=split_row,
        fold_rows=inner_validation_folds,
    )
    forecast_summary = evaluate_forecast_batch(
        observations=[build_observation_row(row) for row in predicted_rows],
        samples=_select_forecast_outputs(predicted_rows, forecast_bundle, key='sample_sets'),
        joint_nll_values=_select_forecast_outputs(predicted_rows, forecast_bundle, key='joint_nll_values'),
        sample_weights=sample_weights,
        regimes=[build_regime_row(row) for row in predicted_rows],
    )
    raw_nll_values = _select_forecast_outputs(predicted_rows, forecast_bundle, key='joint_nll_values')
    weighted_score_sequence = _build_weighted_score_sequence(
        raw_values=raw_nll_values,
        sample_weights=sample_weights,
    )
    return {
        'origin_ts': origin_ts,
        'split': dict(split_row),
        'weighting': weighting,
        'policy_parameters': decision_refit['policy_parameters'],
        'utility_parameters': decision_refit['utility_parameters'],
        'policy_selection': decision_refit['policy_selection'],
        'utility_selection': decision_refit['utility_selection'],
        'forecast_metrics': forecast_summary['forecast_metrics'],
        'decision_metrics': _build_decision_metrics(
            predicted_rows,
            forecast_sample_sets=_select_forecast_outputs(predicted_rows, forecast_bundle, key='sample_sets'),
            policy_parameters=decision_refit['policy_parameters'],
            utility_parameters=decision_refit['utility_parameters'],
        ),
        'weighted_diagnostics': forecast_summary['weighted_diagnostics'],
        'unweighted_diagnostics': forecast_summary['unweighted_diagnostics'],
        'regime_metrics': forecast_summary['regime_metrics'],
        'n_eff_summary': forecast_summary['n_eff_summary'],
        'forecast_generation': forecast_bundle['generation_summary'],
        'forecast_score_sequence': list(weighted_score_sequence),
    }


def _select_test_rows(
    qualified_rows: list[dict[str, object]],
    *,
    split_row: dict[str, object],
) -> list[dict[str, object]]:
    start_ts = int(split_row['test_start_ts'])
    end_ts = int(split_row['test_end_ts'])
    return [
        row
        for row in qualified_rows
        if start_ts <= int(row['decision_ts']) <= end_ts
    ]


def _select_fit_rows(
    qualified_rows: list[dict[str, object]],
    *,
    split_row: dict[str, object],
) -> list[dict[str, object]]:
    if 'pre_origin_fit_start_ts' not in split_row or 'pre_origin_fit_end_ts' not in split_row:
        origin_ts = int(split_row['origin_ts'])
        return [
            row
            for row in qualified_rows
            if int(row['decision_ts']) < origin_ts
        ]
    start_ts = int(split_row['pre_origin_fit_start_ts'])
    end_ts = int(split_row['pre_origin_fit_end_ts'])
    return [
        row
        for row in qualified_rows
        if start_ts <= int(row['decision_ts']) <= end_ts
    ]


def _select_origin_census_rows(
    census_rows: list[dict[str, object]],
    *,
    split_row: dict[str, object],
) -> list[dict[str, object]]:
    cutoff_ts = int(split_row['census_window_end_ts'])
    return [
        row
        for row in census_rows
        if int(row['decision_ts']) <= cutoff_ts
    ]


def _build_inner_validation_fold_rows(
    *,
    storage,
    split_row: dict[str, object],
    qualified_rows: list[dict[str, object]],
    training_seed: int,
    origin_ts: int,
) -> list[dict[str, object]]:
    folds = []
    for fold_index, fold in enumerate(split_row.get('inner_validation_folds', [])):
        train_rows = _select_rows_in_range(
            qualified_rows,
            start_ts=int(fold['train_start_ts']),
            end_ts=int(fold['train_end_ts']),
        )
        validation_rows = _select_rows_in_range(
            qualified_rows,
            start_ts=int(fold['validation_start_ts']),
            end_ts=int(fold['validation_end_ts']),
        )
        if not train_rows or not validation_rows:
            continue
        forecast_bundle = build_origin_forecast_bundle(
            storage=storage,
            fit_rows=train_rows,
            scored_rows=validation_rows,
            training_seed=training_seed + fold_index + 1,
            origin_ts=origin_ts,
        )
        folds.append(
            {
                'fold_id': str(fold['fold_id']),
                'rows': list(forecast_bundle['predicted_rows']),
                'forecast_sample_sets': list(forecast_bundle['sample_sets']),
            }
        )
    return folds


def _select_rows_in_range(
    rows: list[dict[str, object]],
    *,
    start_ts: int,
    end_ts: int,
) -> list[dict[str, object]]:
    return [
        row
        for row in rows
        if start_ts <= int(row['decision_ts']) <= end_ts
    ]


def _select_forecast_outputs(
    test_rows: list[dict[str, object]],
    forecast_bundle: dict[str, object],
    *,
    key: str,
) -> list[object]:
    lookup = {
        (str(row['session_id']), int(row['decision_ts'])): output
        for row, output in zip(forecast_bundle['predicted_rows'], forecast_bundle[key])
    }
    return [
        lookup[(str(row['session_id']), int(row['decision_ts']))]
        for row in test_rows
    ]

def _build_decision_metrics(
    test_rows: list[dict[str, object]],
    *,
    forecast_sample_sets: list[list[dict[str, float]]],
    policy_parameters: dict[str, float],
    utility_parameters: dict[str, float],
) -> dict[str, object]:
    return evaluate_decision_path(
        forecast_sample_sets=forecast_sample_sets,
        realized_rows=[build_observation_row(row) for row in test_rows],
        spread_last_bps=[build_spread_last_bps(row) for row in test_rows],
        policy_parameters=dict(policy_parameters),
        utility_parameters=dict(utility_parameters),
        execution_assumption_version=EXECUTION_ASSUMPTION_VERSION,
    )


def _build_weighted_score_sequence(
    *,
    raw_values: list[float],
    sample_weights: list[float],
) -> list[float]:
    """构造逐样本加权贡献序列：w_i * nll_i，使 bootstrap 重采样与加权点估计统一。"""
    return [
        float(weight) * float(value)
        for weight, value in zip(sample_weights, raw_values)
    ]
