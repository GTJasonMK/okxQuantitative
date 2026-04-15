from __future__ import annotations

from .protocol_versions import OUTER_ORIGIN_SELECTION_POLICY


SUPPORTED_PROTOCOL_VALUES = {
    'sample_filter_rule': {'single_session_strict_7200x900_v1'},
    'feature_recipe_version': {'second_state_causal_tensor_v1'},
    'label_definition_version': {'next_bar_15m_ohlc_reparam_from_session_seconds_v1'},
    'integrity_policy_version': {'strict_v1'},
    'deployment_target_version': {'single_inst_all_deployment_eligible_15m_v1'},
    'target_census_policy_version': {'deployment_eligible_boundary_census_v1'},
    'target_window_policy_version': {'expanding_pre_origin_census_v1'},
    'shift_state_definition_version': {'compact_boundary_state_v1'},
    'shift_assumption_version': {'A_shift_suff_v1'},
    'shift_diagnostic_version': {'support_mmd_propensity_v1'},
    'strata_definition_version': {'coarse_shift_strata_v1'},
    'split_definition_version': {'blocked_temporal_hv_v1'},
    'outer_origin_selection_policy': {OUTER_ORIGIN_SELECTION_POLICY},
    'weighting_version': {
        'strata_ratio_weighting',
        'classifier_density_ratio_weighting',
    },
    'weight_definition': {
        'raw_ratio_no_clip_no_self_normalization',
        'raw_odds_ratio_no_clip_no_self_normalization',
    },
    'weight_estimator_version': {
        'exact_strata_ratio_v1',
        'oof_logistic_odds_ratio_v1',
    },
    'refit_policy_version': {'expanding_refit_recompute_all_statistics_v1'},
    'domain_classifier_version': {'', 'l2_logistic_shift_state_v1'},
    'regime_definition_version': {'boundary_regimes_v1'},
    'bootstrap_definition_version': {'stationary_block_bootstrap_min9_v1'},
    'evaluation_protocol_version': {'rolling_origin_v1'},
    'score_definition_version': {'joint_scores_v1'},
    'prerank_definition_version': {'multicalibration_v1'},
    'policy_definition_version': {'ternary_expected_utility_policy_v1'},
    'decision_utility_version': {
        'bar_close_return_with_adverse_excursion_penalty_v1'
    },
    'execution_assumption_version': {'boundary_rebalance_hold_to_close_v1'},
    'multiple_comparison_version': {'locked_candidate_set_v1'},
}

PROTOCOL_FIELD_NAMES = tuple(SUPPORTED_PROTOCOL_VALUES.keys())


def validate_protocol_bundle(*, scope: str, payload: dict[str, object]) -> None:
    errors: list[str] = []
    for field_name, allowed_values in SUPPORTED_PROTOCOL_VALUES.items():
        if field_name not in payload:
            continue
        value = payload.get(field_name)
        if value in allowed_values:
            continue
        errors.append(f'{field_name}={value}')
    if errors:
        raise ValueError(f"unsupported protocol bundle ({scope}): {', '.join(errors)}")
