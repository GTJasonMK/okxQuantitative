from __future__ import annotations

from .baseline_models import (
    EMPIRICAL_JOINT_MODEL,
    INDEPENDENT_MARGINAL_MODEL,
    POINT_BASELINE_MODEL,
    build_empirical_joint_baseline,
    build_independent_marginal_baseline,
    build_point_baseline,
)
from .decision_policy import EXECUTION_ASSUMPTION_VERSION, evaluate_decision_path
from .evaluation import (
    DECISION_METRIC_PREFERENCES,
    FORECAST_METRIC_FIELDS,
    aggregate_metric_bundle,
    aggregate_metric_bundle_by_field,
    evaluate_forecast_batch,
)
from .forecast_projection import build_observation_row
from .forecast_projection import build_spread_last_bps
from .origin_weighting import build_weighting_bundle
from .regime_rows import build_regime_row


BASELINE_SPECS = (
    (
        'unconditional_distribution_baseline',
        EMPIRICAL_JOINT_MODEL,
        build_empirical_joint_baseline,
    ),
    (
        'independent_marginal_baseline',
        INDEPENDENT_MARGINAL_MODEL,
        build_independent_marginal_baseline,
    ),
    (
        'point_baseline',
        POINT_BASELINE_MODEL,
        build_point_baseline,
    ),
)
COMPARISON_BASELINE_ID = 'unconditional_distribution_baseline'


def build_baseline_bundle(
    *,
    manifest: dict[str, object],
    split_artifact: dict[str, object],
    qualified_rows: list[dict[str, object]],
    census_rows: list[dict[str, object]],
    challenger_origins: list[dict[str, object]],
) -> dict[str, object]:
    origin_contexts = _build_origin_contexts(
        manifest=manifest,
        split_artifact=split_artifact,
        qualified_rows=qualified_rows,
        census_rows=census_rows,
        challenger_origins=challenger_origins,
    )
    return {
        'baselines': [
            _build_baseline_result(
                baseline_id=baseline_id,
                baseline_model=baseline_model,
                baseline_builder=baseline_builder,
                origin_contexts=origin_contexts,
            )
            for baseline_id, baseline_model, baseline_builder in BASELINE_SPECS
        ]
    }


def select_reference_baseline(
    baseline_bundle: dict[str, object],
    *,
    baseline_id: str = COMPARISON_BASELINE_ID,
) -> dict[str, object]:
    for baseline in baseline_bundle.get('baselines', []):
        if str(baseline.get('baseline_id', '')) == baseline_id:
            return baseline
    raise ValueError(f'comparison baseline not found: {baseline_id}')


def _build_baseline_result(
    *,
    baseline_id: str,
    baseline_model: str,
    baseline_builder,
    origin_contexts: list[dict[str, object]],
) -> dict[str, object]:
    origins = [
        _build_baseline_origin(
            baseline_builder=baseline_builder,
            origin_context=context,
        )
        for context in origin_contexts
    ]
    return {
        'baseline_id': baseline_id,
        'baseline_model': baseline_model,
        'origins': origins,
        'aggregate': {
            'forecast_metrics': aggregate_metric_bundle(
                origins=origins,
                bundle_key='forecast_metrics',
                metric_fields=FORECAST_METRIC_FIELDS,
                lower_is_better=True,
            ),
            'decision_metrics': aggregate_metric_bundle_by_field(
                origins,
                bundle_key='decision_metrics',
                field_preferences=DECISION_METRIC_PREFERENCES,
            ),
        },
    }


def _build_baseline_origin(
    *,
    baseline_builder,
    origin_context: dict[str, object],
) -> dict[str, object]:
    prediction = baseline_builder(
        train_rows=origin_context['fit_rows'],
        test_rows=origin_context['test_rows'],
    )
    forecast_summary = evaluate_forecast_batch(
        observations=[build_observation_row(row) for row in origin_context['test_rows']],
        samples=list(prediction['sample_sets']),
        joint_nll_values=list(prediction['joint_nll_values']),
        sample_weights=list(origin_context['sample_weights']),
        comparison_delta_sequence=[0.0] * len(origin_context['test_rows']),
        regimes=[build_regime_row(row) for row in origin_context['test_rows']],
    )
    return {
        'origin_ts': int(origin_context['origin_ts']),
        'forecast_metrics': dict(forecast_summary['forecast_metrics']),
        'forecast_score_sequence': [
            float(weight) * float(value)
            for weight, value in zip(origin_context['sample_weights'], prediction['joint_nll_values'])
        ],
        'decision_metrics': _build_baseline_decision_metrics(
            forecast_sample_sets=list(prediction['sample_sets']),
            test_rows=origin_context['test_rows'],
            policy_parameters=origin_context['policy_parameters'],
            utility_parameters=origin_context['utility_parameters'],
        ),
        'prediction_summary': {
            **dict(prediction['prediction_summary']),
            'train_sample_count': len(origin_context['fit_rows']),
            'test_sample_count': len(origin_context['test_rows']),
        },
    }


def _build_baseline_decision_metrics(
    *,
    forecast_sample_sets: list[list[dict[str, float]]],
    test_rows: list[dict[str, object]],
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


def _build_origin_contexts(
    *,
    manifest: dict[str, object],
    split_artifact: dict[str, object],
    qualified_rows: list[dict[str, object]],
    census_rows: list[dict[str, object]],
    challenger_origins: list[dict[str, object]],
) -> list[dict[str, object]]:
    split_rows = list(split_artifact.get('origins', []))
    if len(split_rows) != len(challenger_origins):
        raise ValueError('baseline construction requires aligned split rows and challenger origins')
    contexts = []
    for split_row, challenger_origin in zip(split_rows, challenger_origins):
        origin_ts = int(split_row['origin_ts'])
        if origin_ts != int(challenger_origin['origin_ts']):
            raise ValueError('baseline construction requires origin_ts alignment')
        fit_rows = _select_fit_rows(qualified_rows, split_row=split_row)
        test_rows = _select_rows_between(
            qualified_rows,
            start_ts=int(split_row['test_start_ts']),
            end_ts=int(split_row['test_end_ts']),
        )
        origin_census_rows = [
            row
            for row in census_rows
            if int(row['decision_ts']) <= int(split_row['census_window_end_ts'])
        ]
        _, sample_weights = build_weighting_bundle(
            manifest=manifest,
            origin_ts=origin_ts,
            fit_rows=fit_rows,
            test_rows=test_rows,
            census_rows=origin_census_rows,
        )
        contexts.append(
            {
                'origin_ts': origin_ts,
                'fit_rows': fit_rows,
                'test_rows': test_rows,
                'sample_weights': sample_weights,
                'policy_parameters': dict(challenger_origin['policy_parameters']),
                'utility_parameters': dict(challenger_origin['utility_parameters']),
            }
        )
    return contexts


def _select_rows_between(
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


def _select_fit_rows(
    rows: list[dict[str, object]],
    *,
    split_row: dict[str, object],
) -> list[dict[str, object]]:
    if 'pre_origin_fit_start_ts' not in split_row or 'pre_origin_fit_end_ts' not in split_row:
        origin_ts = int(split_row['origin_ts'])
        return [
            row
            for row in rows
            if int(row['decision_ts']) < origin_ts
        ]
    return _select_rows_between(
        rows,
        start_ts=int(split_row['pre_origin_fit_start_ts']),
        end_ts=int(split_row['pre_origin_fit_end_ts']),
    )
