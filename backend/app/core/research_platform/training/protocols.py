from __future__ import annotations

from app.core.research_platform.protocol_registry import validate_protocol_bundle

from .candidate_sets import validate_candidate_set_request


TRAINING_PROTOCOL_FIELDS = (
    'split_definition_version',
    'evaluation_protocol_version',
    'refit_policy_version',
    'outer_origin_selection_policy',
    'weighting_version',
    'weight_definition',
    'weight_estimator_version',
    'domain_classifier_version',
    'score_definition_version',
    'prerank_definition_version',
    'regime_definition_version',
    'bootstrap_definition_version',
    'policy_definition_version',
    'decision_utility_version',
    'execution_assumption_version',
    'multiple_comparison_version',
)

DATASET_PROTOCOL_FIELDS = (
    'label_definition_version',
    'integrity_policy_version',
    'target_census_policy_version',
    'target_window_policy_version',
    'shift_state_definition_version',
    'deployment_target_version',
    'strata_definition_version',
    'shift_assumption_version',
    'shift_diagnostic_version',
)

JOINT_MODEL_FAMILIES = {
    'joint_density_model_v1',
}
BASELINE_ONLY_MODEL_FAMILIES = {
    'joint_distribution_baseline',
    'independent_four_head_regression_v1',
    'point_forecast_head_v1',
}


def validate_training_protocol_bundle(manifest: dict[str, object]) -> None:
    training_payload = {field_name: manifest[field_name] for field_name in TRAINING_PROTOCOL_FIELDS}
    validate_protocol_bundle(scope='training_run', payload=training_payload)
    _validate_dataset_protocol_fields_frozen(manifest)
    if manifest['score_definition_version'] != 'joint_scores_v1':
        raise ValueError('unsupported protocol bundle: score_definition_version must be joint_scores_v1')
    if manifest['multiple_comparison_version'] != 'locked_candidate_set_v1':
        raise ValueError('unsupported protocol bundle: multiple_comparison_version must be locked_candidate_set_v1')


def _validate_dataset_protocol_fields_frozen(manifest: dict[str, object]) -> None:
    """校验数据侧协议字段均已冻结（非空），确保训练依赖的上游协议对象完整。"""
    missing = [
        field_name
        for field_name in DATASET_PROTOCOL_FIELDS
        if not str(manifest.get(field_name, '') or '').strip()
    ]
    if missing:
        raise ValueError(
            f'数据侧协议字段未冻结，训练无法启动: {sorted(missing)}'
        )


def validate_model_output_contract(model_family: str) -> None:
    if model_family in JOINT_MODEL_FAMILIES:
        return
    if model_family in BASELINE_ONLY_MODEL_FAMILIES:
        raise ValueError('baseline-only model families cannot be registered as official challengers')
    raise ValueError(f'unknown model family: {model_family}')


def validate_training_candidate_request(*, candidate_set_ref: str, model_family: str) -> None:
    validate_candidate_set_request(
        candidate_set_ref=candidate_set_ref,
        model_family=model_family,
    )
