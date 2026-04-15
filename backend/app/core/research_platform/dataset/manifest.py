from __future__ import annotations

import hashlib
import json
import time

from app.core.data_center_collection.integrity_policy import get_integrity_policy
from app.core.research_platform.protocol_versions import OUTER_ORIGIN_SELECTION_POLICY


def create_dataset_id(payload: dict[str, object]) -> str:
    encoded_payload = json.dumps(payload, sort_keys=True, ensure_ascii=True)
    digest = hashlib.sha1(encoded_payload.encode('ascii')).hexdigest()[:12]
    return f'dataset-{int(time.time())}-{digest}'


def build_dataset_manifest(
    *,
    payload: dict[str, object],
    stats: dict[str, object],
) -> dict[str, object]:
    return {
        'dataset_id': stats['dataset_id'],
        'inst_id': stats['inst_id'],
        'included_session_ids_json': json.dumps(payload['included_session_ids']),
        'sample_filter_rule': payload['sample_filter_rule'],
        'feature_recipe_version': payload['feature_recipe_version'],
        'label_definition_version': payload['label_definition_version'],
        'integrity_policy_version': payload['integrity_policy_version'],
        'integrity_policy': get_integrity_policy(str(payload['integrity_policy_version'])),
        'deployment_target_version': payload['deployment_target_version'],
        'target_census_policy_version': payload['target_census_policy_version'],
        'target_window_policy_version': payload['target_window_policy_version'],
        'strata_definition_version': payload['strata_definition_version'],
        'strata_fit_ref': stats['strata_fit_ref'],
        'sampling_stride_sec': int(payload['sampling_stride_sec']),
        'split_definition_version': payload['split_definition_version'],
        'outer_origin_selection_policy': OUTER_ORIGIN_SELECTION_POLICY,
        'embargo_sec': int(payload['embargo_sec']),
        'weighting_version': payload['weighting_version'],
        'weight_definition': payload['weight_definition'],
        'weight_estimator_version': payload['weight_estimator_version'],
        'weight_fit_ref': stats['weight_fit_ref'],
        'shift_state_definition_version': payload['shift_state_definition_version'],
        'shift_assumption_version': payload['shift_assumption_version'],
        'shift_diagnostic_version': payload['shift_diagnostic_version'],
        'refit_policy_version': payload['refit_policy_version'],
        'domain_classifier_version': payload['domain_classifier_version'],
        'domain_classifier_fit_ref': stats['domain_classifier_fit_ref'],
        'regime_definition_version': payload['regime_definition_version'],
        'bootstrap_definition_version': payload['bootstrap_definition_version'],
        'evaluation_protocol_version': payload['evaluation_protocol_version'],
        'score_definition_version': payload['score_definition_version'],
        'prerank_definition_version': payload['prerank_definition_version'],
        'policy_definition_version': payload['policy_definition_version'],
        'policy_parameter_ref': payload['policy_parameter_ref'],
        'decision_utility_version': payload['decision_utility_version'],
        'utility_parameter_ref': payload['utility_parameter_ref'],
        'execution_assumption_version': payload['execution_assumption_version'],
        'multiple_comparison_version': payload['multiple_comparison_version'],
        'dataset_status': stats['dataset_status'],
        'shift_diagnostic_result': stats['shift_diagnostic_result'],
        'target_census_count': stats['target_census_count'],
        'support_overlap_result': stats['support_overlap_result'],
        'train_sample_count': stats['train_sample_count'],
        'val_sample_count': stats['val_sample_count'],
        'test_sample_count': stats['test_sample_count'],
        'train_effective_sample_size': stats['train_effective_sample_size'],
        'val_effective_sample_size': stats['val_effective_sample_size'],
        'test_effective_sample_size': stats['test_effective_sample_size'],
        'created_at': stats['created_at'],
    }


def validate_weighting_preconditions(
    *,
    payload: dict[str, object],
    shift_diagnostic_result: dict[str, object],
) -> None:
    if payload['weighting_version'] == 'strata_ratio_weighting':
        if payload['domain_classifier_version'] != '':
            raise ValueError('strata_ratio_weighting requires empty domain_classifier_version')
        if payload['weight_estimator_version'] != 'exact_strata_ratio_v1':
            raise ValueError('strata_ratio_weighting requires exact_strata_ratio_v1')
        return
    if payload['domain_classifier_version'] != 'l2_logistic_shift_state_v1':
        raise ValueError('classifier_density_ratio_weighting requires l2_logistic_shift_state_v1')
    if payload['weight_estimator_version'] != 'oof_logistic_odds_ratio_v1':
        raise ValueError('classifier_density_ratio_weighting requires oof_logistic_odds_ratio_v1')
    overall_status = shift_diagnostic_result['overall_status']
    support_status = shift_diagnostic_result['checks']['support_overlap']['status']
    if overall_status != 'acceptable' or support_status != 'ok':
        raise ValueError('classifier weighting requires acceptable support overlap')


def serialize_manifest(manifest: dict[str, object]) -> dict[str, object]:
    return {
        **manifest,
        'integrity_policy_json': json.dumps(manifest['integrity_policy'], sort_keys=True),
        'shift_diagnostic_result': json.dumps(manifest['shift_diagnostic_result']),
    }


def deserialize_manifest(row: dict[str, object] | None) -> dict[str, object] | None:
    if row is None:
        return None
    return {
        **row,
        'included_session_ids': json.loads(str(row['included_session_ids_json'])),
        'integrity_policy': json.loads(str(row['integrity_policy_json'])),
        'shift_diagnostic_result': json.loads(str(row['shift_diagnostic_result'])),
    }
