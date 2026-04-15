from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core.research_platform_delete_errors import DatasetDeleteBlockedError


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / 'app' / 'api' / 'research_platform.py'
    spec = importlib.util.spec_from_file_location('research_platform_api_module', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_create_dataset_manifest_api():
    module = _load_module()

    class FakeService:
        def list_dataset_manifests(self, *, limit=50):
            return []

        def create_dataset_manifest(self, payload):
            return {
                'dataset_id': 'dataset-1',
                'evaluation_protocol_version': payload['evaluation_protocol_version'],
            }

    class FakeContext:
        def research_platform(self):
            return FakeService()

    request = module.DatasetCreateRequest(
        included_session_ids=['sess-1'],
        sample_filter_rule='single_session_strict_7200x900_v1',
        feature_recipe_version='second_state_causal_tensor_v1',
        label_definition_version='next_bar_15m_ohlc_reparam_from_session_seconds_v1',
        integrity_policy_version='strict_v1',
        deployment_target_version='single_inst_all_deployment_eligible_15m_v1',
        target_census_policy_version='deployment_eligible_boundary_census_v1',
        target_window_policy_version='expanding_pre_origin_census_v1',
        shift_state_definition_version='compact_boundary_state_v1',
        shift_assumption_version='A_shift_suff_v1',
        shift_diagnostic_version='support_mmd_propensity_v1',
        strata_definition_version='coarse_shift_strata_v1',
        sampling_stride_sec=900,
        split_definition_version='blocked_temporal_hv_v1',
        embargo_sec=8100,
        weighting_version='strata_ratio_weighting',
        weight_definition='raw_ratio_no_clip_no_self_normalization',
        weight_estimator_version='exact_strata_ratio_v1',
        refit_policy_version='expanding_refit_recompute_all_statistics_v1',
        domain_classifier_version='',
        regime_definition_version='boundary_regimes_v1',
        bootstrap_definition_version='stationary_block_bootstrap_min9_v1',
        evaluation_protocol_version='rolling_origin_v1',
        score_definition_version='joint_scores_v1',
        prerank_definition_version='multicalibration_v1',
        policy_definition_version='ternary_expected_utility_policy_v1',
        policy_parameter_ref='policy://defaults/ternary_expected_utility_policy_v1',
        decision_utility_version='bar_close_return_with_adverse_excursion_penalty_v1',
        utility_parameter_ref='utility://defaults/bar_close_return_with_adverse_excursion_penalty_v1',
        execution_assumption_version='boundary_rebalance_hold_to_close_v1',
        multiple_comparison_version='locked_candidate_set_v1',
    )

    list_result = asyncio.run(module.list_datasets(limit=20, ctx=FakeContext()))
    create_result = asyncio.run(module.create_dataset(request, FakeContext()))

    assert list_result['datasets'] == []
    assert create_result['dataset']['dataset_id'] == 'dataset-1'
    assert create_result['dataset']['evaluation_protocol_version'] == 'rolling_origin_v1'


def test_get_dataset_preview_api():
    module = _load_module()

    class FakeService:
        def get_dataset_manifest(self, dataset_id):
            return {'dataset_id': dataset_id, 'evaluation_protocol_version': 'rolling_origin_v1'}

        def get_dataset_protocol_validation_status(self, dataset_id):
            return 'ok'

        def get_dataset_split_summary(self, dataset_id):
            return {'train_sample_count': 3, 'val_sample_count': 1, 'test_sample_count': 1}

        def get_dataset_weight_summary(self, dataset_id):
            return {'weighting_version': 'strata_ratio_weighting'}

        def get_dataset_regime_schema(self, dataset_id):
            return {'definition_version': 'boundary_regimes_v1'}

        def get_dataset_effective_size_summary(self, dataset_id):
            return {'sequence_definitions': {'label_r_close_sequence': {'estimates': {'train': 2.0}}}}

        def get_dataset_shift_diagnostic_preview(self, dataset_id):
            return {'overall_status': 'acceptable'}

        def get_dataset_shift_diagnostics_bundle(self, dataset_id):
            return {'weighting_version': 'strata_ratio_weighting', 'shift_diagnostic_result': {'overall_status': 'acceptable'}}

        def get_dataset_fit_artifact_preview(self, dataset_id):
            return {
                'strata_fit_bundle': {'strata_fit_ref': 'artifact://dataset/1/strata'},
                'weight_fit_bundle': {'weight_fit_ref': 'artifact://dataset/1/weight'},
                'domain_classifier_fit_bundle': None,
            }

    class FakeContext:
        def research_platform(self):
            return FakeService()

    result = asyncio.run(module.get_dataset_preview('dataset-1', FakeContext()))
    preview = result['preview']

    assert 'manifest' in preview
    assert preview['protocol_validation_status'] == 'ok'
    assert 'regime_schema' in preview
    assert 'sequence_definitions' in preview['n_eff_summary']
    assert 'shift_diagnostics_bundle' in preview
    assert 'split_summary' in preview
    assert preview['strata_fit_bundle']['strata_fit_ref'] == 'artifact://dataset/1/strata'
    assert preview['weight_fit_bundle']['weight_fit_ref'] == 'artifact://dataset/1/weight'
    assert preview['domain_classifier_fit_bundle'] is None


def test_delete_dataset_manifest_api():
    module = _load_module()

    class FakeService:
        def delete_dataset_manifest(self, dataset_id):
            return {
                'dataset_id': dataset_id,
                'deleted_dataset_count': 1,
            }

    class FakeContext:
        def research_platform(self):
            return FakeService()

    result = asyncio.run(module.delete_dataset('dataset-1', FakeContext()))

    assert result['deleted_dataset']['dataset_id'] == 'dataset-1'
    assert result['deleted_dataset']['deleted_dataset_count'] == 1


def test_delete_dataset_manifest_api_returns_409_when_training_runs_block():
    module = _load_module()

    class FakeService:
        def delete_dataset_manifest(self, dataset_id):
            raise DatasetDeleteBlockedError.referenced_by_training_runs(
                dataset_id,
                ['run-1'],
            )

    class FakeContext:
        def research_platform(self):
            return FakeService()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(module.delete_dataset('dataset-1', FakeContext()))

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail['blocking_training_run_ids'] == ['run-1']


def test_create_dataset_manifest_api_returns_400_for_protocol_error():
    module = _load_module()

    class FakeService:
        def create_dataset_manifest(self, payload):
            raise ValueError('unsupported protocol bundle: bad version')

    class FakeContext:
        def research_platform(self):
            return FakeService()

    request = module.DatasetCreateRequest(
        included_session_ids=['sess-1'],
        sample_filter_rule='single_session_strict_7200x900_v1',
        feature_recipe_version='second_state_causal_tensor_v1',
        label_definition_version='next_bar_15m_ohlc_reparam_from_session_seconds_v1',
        integrity_policy_version='strict_v1',
        deployment_target_version='single_inst_all_deployment_eligible_15m_v1',
        target_census_policy_version='deployment_eligible_boundary_census_v1',
        target_window_policy_version='expanding_pre_origin_census_v1',
        shift_state_definition_version='compact_boundary_state_v1',
        shift_assumption_version='A_shift_suff_v1',
        shift_diagnostic_version='support_mmd_propensity_v1',
        strata_definition_version='coarse_shift_strata_v1',
        sampling_stride_sec=900,
        split_definition_version='blocked_temporal_hv_v1',
        embargo_sec=8100,
        weighting_version='strata_ratio_weighting',
        weight_definition='raw_ratio_no_clip_no_self_normalization',
        weight_estimator_version='exact_strata_ratio_v1',
        refit_policy_version='expanding_refit_recompute_all_statistics_v1',
        domain_classifier_version='',
        regime_definition_version='boundary_regimes_v1',
        bootstrap_definition_version='stationary_block_bootstrap_min9_v1',
        evaluation_protocol_version='rolling_origin_v1',
        score_definition_version='joint_scores_v1',
        prerank_definition_version='multicalibration_v1',
        policy_definition_version='ternary_expected_utility_policy_v1',
        policy_parameter_ref='policy://defaults/ternary_expected_utility_policy_v1',
        decision_utility_version='bar_close_return_with_adverse_excursion_penalty_v1',
        utility_parameter_ref='utility://defaults/bar_close_return_with_adverse_excursion_penalty_v1',
        execution_assumption_version='boundary_rebalance_hold_to_close_v1',
        multiple_comparison_version='locked_candidate_set_v1',
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(module.create_dataset(request, FakeContext()))

    assert exc_info.value.status_code == 400
    assert 'unsupported protocol bundle' in exc_info.value.detail
