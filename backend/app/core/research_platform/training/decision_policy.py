from __future__ import annotations


ACTION_SPACE = (-1, 0, 1)
TAIL_RISK_ALPHA = 0.05
EXECUTION_ASSUMPTION_VERSION = 'boundary_rebalance_hold_to_close_v1'
POLICY_DEFINITION_VERSION = 'ternary_expected_utility_policy_v1'
DECISION_UTILITY_VERSION = 'bar_close_return_with_adverse_excursion_penalty_v1'

DEFAULT_POLICY_PARAMETERS = {
    'tau_entry': 0.0,
    'tau_switch': 0.0,
}

DEFAULT_UTILITY_PARAMETERS = {
    'slippage_const_bps': 1.0,
    'lambda_ae': 0.5,
    'previous_action': 0,
}


def compute_bar_utility(
    *,
    action: int,
    r_close: float,
    r_open: float,
    u: float,
    d: float,
    spread_last_bps: float,
    slippage_const_bps: float,
    previous_action: int,
    lambda_ae: float,
) -> float:
    high_return = max(r_open, r_close) + u
    low_return = min(r_open, r_close) - d
    turnover = abs(action - previous_action)
    execution_cost = compute_execution_cost_rate(
        spread_last_bps=spread_last_bps,
        slippage_const_bps=slippage_const_bps,
    )
    adverse_penalty = _compute_adverse_penalty(
        action=action,
        high_return=high_return,
        low_return=low_return,
    )
    return (action * r_close) - (execution_cost * turnover) - (lambda_ae * adverse_penalty)


def choose_ternary_action(
    *,
    expected_utilities: dict[int, float],
    previous_action: int,
    tau_entry: float,
    tau_switch: float,
) -> int:
    best_action = max(expected_utilities, key=expected_utilities.get)
    directional_best = max(expected_utilities.get(1, 0.0), expected_utilities.get(-1, 0.0))
    if directional_best <= tau_entry:
        return 0
    if best_action != previous_action:
        improvement = expected_utilities[best_action] - expected_utilities.get(previous_action, 0.0)
        if improvement < tau_switch:
            return previous_action
    return best_action


def evaluate_decision_path(
    *,
    forecast_sample_sets: list[list[dict[str, float]]],
    realized_rows: list[dict[str, float]],
    spread_last_bps: list[float],
    policy_parameters: dict[str, float],
    utility_parameters: dict[str, float],
    execution_assumption_version: str,
) -> dict[str, object]:
    _validate_decision_inputs(
        forecast_sample_sets=forecast_sample_sets,
        realized_rows=realized_rows,
        spread_last_bps=spread_last_bps,
        execution_assumption_version=execution_assumption_version,
    )
    previous_action = int(utility_parameters['previous_action'])
    path_rows = []
    for forecast_sample_set, realized_row, spread_bps in zip(forecast_sample_sets, realized_rows, spread_last_bps):
        action = _choose_action_for_forecast(
            forecast_sample_set=forecast_sample_set,
            spread_last_bps=float(spread_bps),
            previous_action=previous_action,
            policy_parameters=policy_parameters,
            utility_parameters=utility_parameters,
        )
        path_rows.append(
            _realize_action_row(
                action=action,
                realized_row=realized_row,
                spread_last_bps=float(spread_bps),
                previous_action=previous_action,
                utility_parameters=utility_parameters,
            )
        )
        previous_action = action
    return _summarize_decision_path(path_rows)


def build_policy_parameter_bundle(
    *,
    origins: list[dict[str, object]],
    policy_parameter_ref: str,
) -> dict[str, object]:
    return {
        'policy_parameter_ref': policy_parameter_ref,
        'by_origin': [
            {
                'origin_ts': int(origin['origin_ts']),
                'policy_parameters': dict(origin.get('policy_parameters', DEFAULT_POLICY_PARAMETERS)),
                'selection_summary': dict(origin.get('policy_selection', {})),
            }
            for origin in origins
        ],
    }


def build_utility_parameter_bundle(
    *,
    origins: list[dict[str, object]],
    utility_parameter_ref: str,
) -> dict[str, object]:
    return {
        'utility_parameter_ref': utility_parameter_ref,
        'by_origin': [
            {
                'origin_ts': int(origin['origin_ts']),
                'utility_parameters': dict(origin.get('utility_parameters', DEFAULT_UTILITY_PARAMETERS)),
                'selection_summary': dict(origin.get('utility_selection', {})),
            }
            for origin in origins
        ],
    }


def compute_execution_cost_rate(*, spread_last_bps: float, slippage_const_bps: float) -> float:
    return ((spread_last_bps / 2.0) + slippage_const_bps) / 1e4


def _compute_adverse_penalty(*, action: int, high_return: float, low_return: float) -> float:
    if action == 1:
        return max(0.0, -low_return)
    if action == -1:
        return max(0.0, high_return)
    return 0.0


def _validate_decision_inputs(
    *,
    forecast_sample_sets: list[list[dict[str, float]]],
    realized_rows: list[dict[str, float]],
    spread_last_bps: list[float],
    execution_assumption_version: str,
) -> None:
    if execution_assumption_version != EXECUTION_ASSUMPTION_VERSION:
        raise ValueError(f'unsupported execution assumption version: {execution_assumption_version}')
    if not forecast_sample_sets:
        raise ValueError('decision path requires at least one forecast sample set')
    if len(forecast_sample_sets) != len(realized_rows) or len(forecast_sample_sets) != len(spread_last_bps):
        raise ValueError('decision path inputs must have the same length')
    if any(not sample_set for sample_set in forecast_sample_sets):
        raise ValueError('decision path requires non-empty forecast sample sets')


def _choose_action_for_forecast(
    *,
    forecast_sample_set: list[dict[str, float]],
    spread_last_bps: float,
    previous_action: int,
    policy_parameters: dict[str, float],
    utility_parameters: dict[str, float],
) -> int:
    expected_utilities = {
        action: _expected_utility_for_action(
            action=action,
            forecast_sample_set=forecast_sample_set,
            spread_last_bps=spread_last_bps,
            slippage_const_bps=float(utility_parameters['slippage_const_bps']),
            previous_action=previous_action,
            lambda_ae=float(utility_parameters['lambda_ae']),
        )
        for action in ACTION_SPACE
    }
    return choose_ternary_action(
        expected_utilities=expected_utilities,
        previous_action=previous_action,
        tau_entry=float(policy_parameters['tau_entry']),
        tau_switch=float(policy_parameters['tau_switch']),
    )


def compute_expected_utility_for_action(
    *,
    action: int,
    forecast_sample_set: list[dict[str, float]],
    spread_last_bps: float,
    slippage_const_bps: float,
    previous_action: int,
    lambda_ae: float,
) -> float:
    return _expected_utility_for_action(
        action=action,
        forecast_sample_set=forecast_sample_set,
        spread_last_bps=spread_last_bps,
        slippage_const_bps=slippage_const_bps,
        previous_action=previous_action,
        lambda_ae=lambda_ae,
    )


def _expected_utility_for_action(
    *,
    action: int,
    forecast_sample_set: list[dict[str, float]],
    spread_last_bps: float,
    slippage_const_bps: float,
    previous_action: int,
    lambda_ae: float,
) -> float:
    return sum(
        compute_bar_utility(
            action=action,
            r_close=float(sample['r_close']),
            r_open=float(sample['r_open']),
            u=float(sample['u']),
            d=float(sample['d']),
            spread_last_bps=spread_last_bps,
            slippage_const_bps=slippage_const_bps,
            previous_action=previous_action,
            lambda_ae=lambda_ae,
        )
        for sample in forecast_sample_set
    ) / len(forecast_sample_set)


def _realize_action_row(
    *,
    action: int,
    realized_row: dict[str, float],
    spread_last_bps: float,
    previous_action: int,
    utility_parameters: dict[str, float],
) -> dict[str, float | int]:
    turnover = abs(action - previous_action)
    execution_cost = compute_execution_cost_rate(
        spread_last_bps=spread_last_bps,
        slippage_const_bps=float(utility_parameters['slippage_const_bps']),
    )
    net_return = (action * float(realized_row['r_close'])) - (execution_cost * turnover)
    utility = compute_bar_utility(
        action=action,
        r_close=float(realized_row['r_close']),
        r_open=float(realized_row['r_open']),
        u=float(realized_row['u']),
        d=float(realized_row['d']),
        spread_last_bps=spread_last_bps,
        slippage_const_bps=float(utility_parameters['slippage_const_bps']),
        previous_action=previous_action,
        lambda_ae=float(utility_parameters['lambda_ae']),
    )
    return {
        'action': action,
        'utility': utility,
        'net_return': net_return,
        'turnover': float(turnover),
    }


def _summarize_decision_path(path_rows: list[dict[str, float | int]]) -> dict[str, object]:
    utilities = [float(row['utility']) for row in path_rows]
    net_returns = [float(row['net_return']) for row in path_rows]
    actions = [int(row['action']) for row in path_rows]
    turnovers = [float(row['turnover']) for row in path_rows]
    exposed_net_returns = [value for action, value in zip(actions, net_returns) if action != 0]
    return {
        'mean_utility': sum(utilities) / len(utilities),
        'net_return': sum(net_returns),
        'utility_sequence': utilities,
        'net_return_sequence': net_returns,
        'max_drawdown': _compute_max_drawdown(net_returns),
        'turnover_mean': sum(turnovers) / len(turnovers),
        'hit_rate': _compute_hit_rate(exposed_net_returns),
        'exposure_rate': sum(1 for action in actions if action != 0) / len(actions),
        'downside_tail_risk': _percentile(exposed_net_returns or net_returns, TAIL_RISK_ALPHA),
        'action_path': actions,
        'action_counts': {str(action): actions.count(action) for action in ACTION_SPACE},
        'policy_definition_version': POLICY_DEFINITION_VERSION,
        'decision_utility_version': DECISION_UTILITY_VERSION,
        'execution_assumption_version': EXECUTION_ASSUMPTION_VERSION,
    }


def _compute_hit_rate(net_returns: list[float]) -> float:
    if not net_returns:
        return 0.0
    return sum(1 for value in net_returns if value > 0.0) / len(net_returns)


def _compute_max_drawdown(net_returns: list[float]) -> float:
    cumulative = 0.0
    peak = 0.0
    max_drawdown = 0.0
    for value in net_returns:
        cumulative += value
        peak = max(peak, cumulative)
        max_drawdown = min(max_drawdown, cumulative - peak)
    return max_drawdown


def _percentile(values: list[float], alpha: float) -> float:
    ordered = sorted(values)
    index = max(0, int((len(ordered) - 1) * alpha))
    return ordered[index]
