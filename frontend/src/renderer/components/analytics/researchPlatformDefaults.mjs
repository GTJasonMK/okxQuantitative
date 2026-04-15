export const DATASET_CREATE_DEFAULTS = Object.freeze({
  sample_filter_rule: 'single_session_strict_7200x900_v1',
  feature_recipe_version: 'second_state_causal_tensor_v1',
  label_definition_version: 'next_bar_15m_ohlc_reparam_from_session_seconds_v1',
  integrity_policy_version: 'strict_v1',
  deployment_target_version: 'single_inst_all_deployment_eligible_15m_v1',
  target_census_policy_version: 'deployment_eligible_boundary_census_v1',
  target_window_policy_version: 'expanding_pre_origin_census_v1',
  shift_state_definition_version: 'compact_boundary_state_v1',
  shift_assumption_version: 'A_shift_suff_v1',
  shift_diagnostic_version: 'support_mmd_propensity_v1',
  strata_definition_version: 'coarse_shift_strata_v1',
  sampling_stride_sec: 900,
  split_definition_version: 'blocked_temporal_hv_v1',
  embargo_sec: 8100,
  weighting_version: 'strata_ratio_weighting',
  weight_definition: 'raw_ratio_no_clip_no_self_normalization',
  weight_estimator_version: 'exact_strata_ratio_v1',
  refit_policy_version: 'expanding_refit_recompute_all_statistics_v1',
  domain_classifier_version: '',
  regime_definition_version: 'boundary_regimes_v1',
  bootstrap_definition_version: 'stationary_block_bootstrap_min9_v1',
  evaluation_protocol_version: 'rolling_origin_v1',
  score_definition_version: 'joint_scores_v1',
  prerank_definition_version: 'multicalibration_v1',
  policy_definition_version: 'ternary_expected_utility_policy_v1',
  policy_parameter_ref: 'policy://defaults/ternary_expected_utility_policy_v1',
  decision_utility_version: 'bar_close_return_with_adverse_excursion_penalty_v1',
  utility_parameter_ref: 'utility://defaults/bar_close_return_with_adverse_excursion_penalty_v1',
  execution_assumption_version: 'boundary_rebalance_hold_to_close_v1',
  multiple_comparison_version: 'locked_candidate_set_v1',
});

export const TRAINING_CREATE_DEFAULTS = Object.freeze({
  candidate_set_ref: 'candidate://locked/default-v1',
  model_family: 'joint_density_model_v1',
  model_spec_ref: 'model://joint_density_model_v1/default-v1',
  training_seed: 7,
});

export const TRAINING_MODEL_FAMILY_OPTIONS = Object.freeze([
  { value: 'joint_density_model_v1', label: 'joint_density_model_v1' },
]);

export function buildDatasetCreatePayload(sessionIds) {
  return {
    ...DATASET_CREATE_DEFAULTS,
    included_session_ids: [...sessionIds],
  };
}

export function buildTrainingCreatePayload(datasetId) {
  return {
    ...TRAINING_CREATE_DEFAULTS,
    dataset_id: datasetId,
  };
}
