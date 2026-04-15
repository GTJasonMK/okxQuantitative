from __future__ import annotations

from .decision_policy import (
    DECISION_UTILITY_VERSION,
    DEFAULT_POLICY_PARAMETERS,
    DEFAULT_UTILITY_PARAMETERS,
    EXECUTION_ASSUMPTION_VERSION,
    POLICY_DEFINITION_VERSION,
    compute_expected_utility_for_action,
    evaluate_decision_path,
)
from .forecast_projection import (
    build_observation_row,
    build_spread_last_bps,
)


POLICY_SELECTION_VERSION = 'inner_validation_grid_search_v1'
UTILITY_SELECTION_VERSION = 'inner_validation_grid_search_v1'
ENTRY_CANDIDATE_QUANTILES = (0.5, 1.0)
SWITCH_CANDIDATE_QUANTILES = (0.5,)
SLIPPAGE_CANDIDATE_QUANTILES = (0.5, 1.0)
LAMBDA_CANDIDATES = (0.25, 0.5, 1.0)
BASE_SLIPPAGE_CANDIDATES = (0.5, 1.0, 2.0)
OBJECTIVE_NAME = 'mean_utility'


def fit_origin_decision_parameters(
    *,
    split_row: dict[str, object],
    fold_rows: list[dict[str, object]],
) -> dict[str, object]:
    if not fold_rows:
        raise ValueError(
            'protocol-invalid: no complete inner-validation folds '
            f"for origin {int(split_row.get('origin_ts', 0))}"
        )
    utility_grid = _build_utility_candidate_grid(fold_rows)
    best_candidate, best_utility, best_score, policy_candidate_count = _select_best_configuration(
        fold_rows=fold_rows,
        utility_grid=utility_grid,
    )
    fold_ids = [fold['fold_id'] for fold in fold_rows]
    return {
        'policy_parameters': best_candidate,
        'utility_parameters': best_utility,
        'policy_selection': {
            'selection_method': POLICY_SELECTION_VERSION,
            'policy_definition_version': POLICY_DEFINITION_VERSION,
            'objective_name': OBJECTIVE_NAME,
            'selected_fold_count': len(fold_rows),
            'candidate_count': policy_candidate_count,
            'fold_ids': fold_ids,
            'best_objective_value': best_score['mean_utility'],
            'best_turnover_mean': best_score['turnover_mean'],
            'best_exposure_rate': best_score['exposure_rate'],
        },
        'utility_selection': {
            'selection_method': UTILITY_SELECTION_VERSION,
            'decision_utility_version': DECISION_UTILITY_VERSION,
            'selected_fold_count': len(fold_rows),
            'candidate_count': len(utility_grid),
            'fold_ids': fold_ids,
            'selection_source': 'inner_validation',
        },
    }


def _build_utility_candidate_grid(
    fold_rows: list[dict[str, object]],
) -> list[dict[str, float]]:
    previous_action = int(DEFAULT_UTILITY_PARAMETERS['previous_action'])
    return [
        {
            'slippage_const_bps': slippage_const_bps,
            'lambda_ae': lambda_ae,
            'previous_action': previous_action,
        }
        for slippage_const_bps in _build_slippage_candidates(fold_rows)
        for lambda_ae in LAMBDA_CANDIDATES
    ]


def _build_slippage_candidates(fold_rows: list[dict[str, object]]) -> list[float]:
    spreads = sorted(
        max(0.0, build_spread_last_bps(row))
        for fold in fold_rows
        for row in fold['rows']
    )
    candidates = {float(value) for value in BASE_SLIPPAGE_CANDIDATES}
    if spreads:
        for quantile in SLIPPAGE_CANDIDATE_QUANTILES:
            candidates.add(max(0.5, _value_at_quantile(spreads, quantile=quantile)))
    return sorted(candidates)


def _build_policy_candidate_grid(
    fold_rows: list[dict[str, object]],
    *,
    utility_parameters: dict[str, float],
) -> list[dict[str, float]]:
    directional_scores = _collect_directional_scores(fold_rows, utility_parameters=utility_parameters)
    tau_entry_candidates = _build_threshold_candidates(
        directional_scores,
        quantiles=ENTRY_CANDIDATE_QUANTILES,
    )
    tau_switch_candidates = _build_threshold_candidates(
        directional_scores,
        quantiles=SWITCH_CANDIDATE_QUANTILES,
    )
    return [
        {'tau_entry': tau_entry, 'tau_switch': tau_switch}
        for tau_entry in tau_entry_candidates
        for tau_switch in tau_switch_candidates
    ]


def _collect_directional_scores(
    fold_rows: list[dict[str, object]],
    *,
    utility_parameters: dict[str, float],
) -> list[float]:
    scores = []
    for fold in fold_rows:
        for row, forecast_sample_set in zip(fold['rows'], fold['forecast_sample_sets']):
            spread_last_bps = build_spread_last_bps(row)
            for action in (-1, 1):
                score = compute_expected_utility_for_action(
                    action=action,
                    forecast_sample_set=forecast_sample_set,
                    spread_last_bps=spread_last_bps,
                    slippage_const_bps=float(utility_parameters['slippage_const_bps']),
                    previous_action=int(utility_parameters['previous_action']),
                    lambda_ae=float(utility_parameters['lambda_ae']),
                )
                if score > 0.0:
                    scores.append(score)
    return scores


def _build_threshold_candidates(
    scores: list[float],
    *,
    quantiles: tuple[float, ...],
) -> list[float]:
    if not scores:
        return [0.0]
    ordered = sorted(scores)
    candidates = {0.0}
    for quantile in quantiles:
        candidates.add(_value_at_quantile(ordered, quantile=quantile))
    return sorted(candidates)


def _value_at_quantile(ordered: list[float], *, quantile: float) -> float:
    index = max(0, min(len(ordered) - 1, int((len(ordered) - 1) * quantile)))
    return ordered[index]


def _select_best_configuration(
    *,
    fold_rows: list[dict[str, object]],
    utility_grid: list[dict[str, float]],
) -> tuple[dict[str, float], dict[str, float], dict[str, float], int]:
    best_candidate = dict(DEFAULT_POLICY_PARAMETERS)
    best_utility = dict(DEFAULT_UTILITY_PARAMETERS)
    best_score = _evaluate_candidate(
        best_candidate,
        fold_rows=fold_rows,
        utility_parameters=best_utility,
    )
    best_policy_candidate_count = 1
    for utility_parameters in utility_grid:
        candidate_grid = _build_policy_candidate_grid(
            fold_rows=fold_rows,
            utility_parameters=utility_parameters,
        )
        candidate, score = _select_best_policy_candidate(
            candidate_grid=candidate_grid,
            fold_rows=fold_rows,
            utility_parameters=utility_parameters,
        )
        if _configuration_key(
            score=score,
            candidate=candidate,
            utility_parameters=utility_parameters,
        ) > _configuration_key(
            score=best_score,
            candidate=best_candidate,
            utility_parameters=best_utility,
        ):
            best_candidate = dict(candidate)
            best_utility = dict(utility_parameters)
            best_score = score
            best_policy_candidate_count = len(candidate_grid)
    return best_candidate, best_utility, best_score, best_policy_candidate_count


def _select_best_policy_candidate(
    *,
    candidate_grid: list[dict[str, float]],
    fold_rows: list[dict[str, object]],
    utility_parameters: dict[str, float],
) -> tuple[dict[str, float], dict[str, float]]:
    best_candidate = dict(DEFAULT_POLICY_PARAMETERS)
    best_score = _evaluate_candidate(
        best_candidate,
        fold_rows=fold_rows,
        utility_parameters=utility_parameters,
    )
    for candidate in candidate_grid:
        score = _evaluate_candidate(
            candidate,
            fold_rows=fold_rows,
            utility_parameters=utility_parameters,
        )
        if _policy_key(score=score, candidate=candidate) > _policy_key(score=best_score, candidate=best_candidate):
            best_candidate = dict(candidate)
            best_score = score
    return best_candidate, best_score


def _evaluate_candidate(
    candidate: dict[str, float],
    *,
    fold_rows: list[dict[str, object]],
    utility_parameters: dict[str, float],
) -> dict[str, float]:
    fold_metrics = [
        evaluate_decision_path(
            forecast_sample_sets=list(fold['forecast_sample_sets']),
            realized_rows=[build_observation_row(row) for row in fold['rows']],
            spread_last_bps=[build_spread_last_bps(row) for row in fold['rows']],
            policy_parameters=candidate,
            utility_parameters=utility_parameters,
            execution_assumption_version=EXECUTION_ASSUMPTION_VERSION,
        )
        for fold in fold_rows
    ]
    return {
        'mean_utility': _mean([float(metrics['mean_utility']) for metrics in fold_metrics]),
        'turnover_mean': _mean([float(metrics['turnover_mean']) for metrics in fold_metrics]),
        'exposure_rate': _mean([float(metrics['exposure_rate']) for metrics in fold_metrics]),
    }


def _configuration_key(
    *,
    score: dict[str, float],
    candidate: dict[str, float],
    utility_parameters: dict[str, float],
) -> tuple[float, float, float, float, float, float, float]:
    return (
        float(score['mean_utility']),
        -float(score['turnover_mean']),
        -float(score['exposure_rate']),
        float(utility_parameters['lambda_ae']),
        -float(utility_parameters['slippage_const_bps']),
        -float(candidate['tau_entry']),
        -float(candidate['tau_switch']),
    )


def _policy_key(
    *,
    score: dict[str, float],
    candidate: dict[str, float],
) -> tuple[float, float, float, float, float]:
    return (
        float(score['mean_utility']),
        -float(score['turnover_mean']),
        -float(score['exposure_rate']),
        -float(candidate['tau_entry']),
        -float(candidate['tau_switch']),
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values)
