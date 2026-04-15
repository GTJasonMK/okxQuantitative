from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.data_storage import DataStorage
from app.core.research_platform.dataset.strata import fit_strata_cutpoints
from app.core.research_platform.dataset.service import ResearchDatasetService
from tests.research_platform_dataset_helpers import (
    DEFAULT_DECISION_TS,
    DEFAULT_INPUT_SECONDS,
    DEFAULT_INST_ID,
    DEFAULT_LABEL_SECONDS,
    DEFAULT_SESSION_ID,
    build_second_rows,
    close_storage,
)


@pytest.fixture
def storage(tmp_path: Path):
    instance = DataStorage(tmp_path / 'research_dataset_manifest.db')
    yield instance
    close_storage(instance)


@pytest.fixture
def dataset_service(storage):
    _seed_dataset_rows(storage, shift_gap=False)
    return ResearchDatasetService(storage=storage)


@pytest.fixture
def gap_dataset_service(storage):
    _seed_dataset_rows(storage, shift_gap=False)
    _save_background_census(storage, base_decision_ts=DEFAULT_DECISION_TS - DEFAULT_INPUT_SECONDS)
    return ResearchDatasetService(storage=storage)


def test_create_dataset_manifest_persists_full_protocol_bundle(dataset_service):
    manifest = dataset_service.create_dataset_manifest(_base_manifest_payload())

    assert manifest['dataset_id']
    assert manifest['deployment_target_version'] == 'single_inst_all_deployment_eligible_15m_v1'
    assert manifest['target_window_policy_version'] == 'expanding_pre_origin_census_v1'
    assert manifest['outer_origin_selection_policy'] == 'max_4_eligible_test_blocks_v1'
    assert manifest['embargo_sec'] == 8100
    assert manifest['multiple_comparison_version'] == 'locked_candidate_set_v1'
    assert manifest['integrity_policy']['integrity_policy_version'] == 'strict_v1'
    assert manifest['integrity_policy']['book_stale_threshold_sec'] > 0.0
    assert manifest['shift_diagnostic_result']['checks']['support_overlap']['status'] in {'ok', 'gap_detected'}
    assert manifest['shift_diagnostic_result']['checks']['mmd_test']['status'] in {'acceptable', 'failed'}
    assert manifest['shift_diagnostic_result']['checks']['propensity_check']['status'] in {'acceptable', 'failed'}
    assert manifest['train_effective_sample_size'] <= manifest['train_sample_count']
    assert manifest['val_effective_sample_size'] <= manifest['val_sample_count']
    assert manifest['dataset_status'] in {'ready', 'research_only'}


def test_create_dataset_manifest_rejects_v2_weighting_without_acceptable_shift_diagnostics(
    gap_dataset_service,
):
    payload = {
        **_base_manifest_payload(),
        'weighting_version': 'classifier_density_ratio_weighting',
        'weight_definition': 'raw_odds_ratio_no_clip_no_self_normalization',
        'weight_estimator_version': 'oof_logistic_odds_ratio_v1',
        'domain_classifier_version': 'l2_logistic_shift_state_v1',
    }

    with pytest.raises(ValueError, match='classifier weighting requires acceptable support overlap'):
        gap_dataset_service.create_dataset_manifest(payload)


def test_create_dataset_manifest_rejects_unsupported_protocol_version(dataset_service):
    payload = {
        **_base_manifest_payload(),
        'target_window_policy_version': 'expanding_pre_origin_census_v9',
    }

    with pytest.raises(ValueError, match='unsupported protocol bundle'):
        dataset_service.create_dataset_manifest(payload)


def test_create_dataset_manifest_materializes_distinct_shift_diagnostic_methods(dataset_service):
    manifest = dataset_service.create_dataset_manifest(
        {
            **_base_manifest_payload(),
            'embargo_sec': 0,
        }
    )

    mmd_test = manifest['shift_diagnostic_result']['checks']['mmd_test']
    propensity_check = manifest['shift_diagnostic_result']['checks']['propensity_check']

    assert mmd_test['method'] == 'linear_rbf_mmd_permutation_v1'
    assert 'p_value' in mmd_test
    assert 'bandwidth' in mmd_test
    assert propensity_check['method'] == 'blocked_temporal_logistic_auc_v1'
    assert 'auc' in propensity_check
    assert propensity_check['split_version'] == 'domainwise_session_temporal_two_fold_v1'


def test_dataset_preview_materializes_fit_artifacts_by_outer_origin(dataset_service):
    manifest = dataset_service.create_dataset_manifest(
        {
            **_base_manifest_payload(),
            'embargo_sec': 0,
        }
    )

    fit_preview = dataset_service.get_dataset_fit_artifact_preview(manifest['dataset_id'])
    strata_fit = fit_preview['strata_fit_bundle']
    weight_fit = fit_preview['weight_fit_bundle']

    assert manifest['domain_classifier_fit_ref'] == ''
    assert strata_fit['strata_fit_ref'] == manifest['strata_fit_ref']
    assert strata_fit['fit_scope'] == 'dataset_outer_origins'
    assert strata_fit['strata_definition_version'] == manifest['strata_definition_version']
    assert strata_fit['origin_count'] == len(strata_fit['by_origin'])
    assert strata_fit['origin_count'] > 1
    assert strata_fit['by_origin'][0]['fit_scope'] == 'outer_origin_pre_origin_fit'
    assert 'rv_2h_bps' in strata_fit['by_origin'][0]['fit_cutpoints']
    assert 'liquidity_score' in strata_fit['by_origin'][0]['fit_cutpoints']
    assert weight_fit['weight_fit_ref'] == manifest['weight_fit_ref']
    assert weight_fit['fit_scope'] == 'dataset_outer_origins'
    assert weight_fit['origin_count'] == len(weight_fit['by_origin'])
    assert weight_fit['by_origin'][0]['fit_scope'] == 'outer_origin_pre_origin_fit'
    assert weight_fit['by_origin'][0]['weight_fit']['weight_estimator_version'] == manifest['weight_estimator_version']
    assert fit_preview['domain_classifier_fit_bundle'] is None


def test_dataset_preview_uses_frozen_census_only_artifacts(dataset_service, storage):
    manifest = dataset_service.create_dataset_manifest(
        {
            **_base_manifest_payload(),
            'embargo_sec': 0,
        }
    )
    census_rows = storage.list_research_target_census_for_inst(DEFAULT_INST_ID)
    expected_cutpoints = fit_strata_cutpoints(
        shift_states=[json.loads(row['shift_state_blob_json']) for row in census_rows],
    )

    preview = dataset_service.get_dataset_fit_artifact_preview(manifest['dataset_id'])
    first_origin = preview['strata_fit_bundle']['by_origin'][0]
    expected_cutpoints = fit_strata_cutpoints(
        shift_states=[
            json.loads(row['shift_state_blob_json'])
            for row in census_rows
            if int(row['decision_ts']) <= int(first_origin['census_window_end_ts'])
        ],
    )
    _save_census(
        storage,
        DEFAULT_DECISION_TS + (24 * DEFAULT_LABEL_SECONDS),
        200,
        shift_gap=False,
    )
    frozen_preview = dataset_service.get_dataset_fit_artifact_preview(manifest['dataset_id'])

    assert first_origin['fit_cutpoints'] == expected_cutpoints
    assert frozen_preview == preview


def _seed_dataset_rows(storage: DataStorage, *, shift_gap: bool) -> None:
    decision_ts = DEFAULT_DECISION_TS
    for index in range(6):
        current_decision_ts = decision_ts + (index * DEFAULT_LABEL_SECONDS)
        _save_boundary_target(storage, current_decision_ts, index)
        _save_sample_index(storage, current_decision_ts)
        _save_census(storage, current_decision_ts, index, shift_gap=shift_gap)
    if shift_gap:
        _save_background_census(storage, base_decision_ts=decision_ts - DEFAULT_INPUT_SECONDS)


def _save_boundary_target(storage: DataStorage, decision_ts: int, index: int) -> None:
    close_price = 65001.0 + (index * 0.2)
    storage.save_research_boundary_target_15m(
        target_id=f'{DEFAULT_SESSION_ID}:{decision_ts}',
        session_id=DEFAULT_SESSION_ID,
        inst_id=DEFAULT_INST_ID,
        decision_ts=decision_ts,
        anchor_second_bucket=decision_ts - 1,
        anchor_close_price=65000.0 + (index * 0.1),
        label_start_ts=decision_ts,
        label_end_ts=decision_ts + DEFAULT_LABEL_SECONDS,
        open_price=65000.1 + (index * 0.1),
        high_price=close_price + 0.4,
        low_price=64999.8 + (index * 0.1),
        close_price=close_price,
        r_open=0.00001 * (index + 1),
        r_close=0.00002 * (index + 1),
        u=0.00003,
        d=0.00002,
        label_complete=1,
        invalid_reason='',
        label_definition_version='next_bar_15m_ohlc_reparam_from_session_seconds_v1',
    )


def _save_sample_index(storage: DataStorage, decision_ts: int) -> None:
    storage.save_research_sample_index_15m(
        sample_id=f'{DEFAULT_SESSION_ID}:{decision_ts}',
        session_id=DEFAULT_SESSION_ID,
        inst_id=DEFAULT_INST_ID,
        decision_ts=decision_ts,
        input_start_ts=decision_ts - DEFAULT_INPUT_SECONDS,
        input_end_ts=decision_ts,
        label_start_ts=decision_ts,
        label_end_ts=decision_ts + DEFAULT_LABEL_SECONDS,
        input_second_count=DEFAULT_INPUT_SECONDS,
        label_second_count=DEFAULT_LABEL_SECONDS,
        input_complete_7200=1,
        label_complete_900=1,
        sample_valid=1,
        ready_for_inference=1,
        ready_for_training=1,
        invalid_reason='',
        prev_sample_overlap_seconds=DEFAULT_INPUT_SECONDS - DEFAULT_LABEL_SECONDS,
        stride_seconds=DEFAULT_LABEL_SECONDS,
    )


def _save_census(
    storage: DataStorage,
    decision_ts: int,
    index: int,
    *,
    shift_gap: bool,
) -> None:
    rv_value = 80.0 + index
    depth_value = 7.2 + (index * 0.02)
    if shift_gap:
        rv_value += 300.0
        depth_value += 4.0
    storage.save_research_target_census(
        census_id=f'census-{decision_ts}',
        inst_id=DEFAULT_INST_ID,
        decision_ts=decision_ts,
        deployment_eligible=0 if shift_gap else 1,
        census_policy_version='deployment_eligible_boundary_census_v1',
        shift_state_definition_version='compact_boundary_state_v1',
        shift_state_blob_json=json.dumps(
            {
                'slot_15m': index,
                'weekend_flag': 0,
                'ret_15m_bps': 18.0 + index,
                'ret_2h_bps': 44.0 + index,
                'rv_15m_bps': 31.0 + index,
                'rv_2h_bps': rv_value,
                'range_15m_bps': 47.0 + index,
                'range_2h_bps': 126.0 + index,
                'spread_last_bps': 0.08,
                'spread_median_60s_bps': 0.09,
                'depth_10bps_log': depth_value,
                'imbalance_10bps': 0.11,
                'trade_count_60s': 850 + index,
                'trade_notional_60s_log': 14.2,
                'funding_countdown_min': 110,
                'near_funding_flag': 0,
                'book_stale_ratio_60s': 0.0,
                'state_stale_ratio_60s': 0.0,
                'source_health_flag': 1,
                'session_active_flag': 1,
            }
        ),
        hour_of_day=(8 + index) % 24,
        day_of_week=6,
        realized_vol_proxy_2h=rv_value,
        spread_snapshot_bps=0.08,
        liquidity_snapshot_bin=2,
        funding_regime='neutral',
        session_active_flag=1,
        source_health_flag=1,
        invalid_reason='',
        observation_source_kind='independent_census_runtime_v1',
    )


def _save_background_census(storage: DataStorage, *, base_decision_ts: int) -> None:
    for index in range(6):
        decision_ts = base_decision_ts + (index * DEFAULT_LABEL_SECONDS)
        storage.save_research_target_census(
            census_id=f'background-census-{decision_ts}',
            inst_id=DEFAULT_INST_ID,
            decision_ts=decision_ts,
            deployment_eligible=1,
            census_policy_version='deployment_eligible_boundary_census_v1',
            shift_state_definition_version='compact_boundary_state_v1',
            shift_state_blob_json=json.dumps(
                {
                    'slot_15m': index,
                    'weekend_flag': 0,
                    'ret_15m_bps': 5.0 + index,
                    'ret_2h_bps': 8.0 + index,
                    'rv_15m_bps': 12.0 + index,
                    'rv_2h_bps': 20.0 + index,
                    'range_15m_bps': 15.0 + index,
                    'range_2h_bps': 30.0 + index,
                    'spread_last_bps': 0.05,
                    'spread_median_60s_bps': 0.05,
                    'depth_10bps_log': 6.0 + (index * 0.02),
                    'imbalance_10bps': 0.02,
                    'trade_count_60s': 400 + index,
                    'trade_notional_60s_log': 12.5,
                    'funding_countdown_min': 150,
                    'near_funding_flag': 0,
                    'book_stale_ratio_60s': 0.0,
                    'state_stale_ratio_60s': 0.0,
                    'source_health_flag': 1,
                    'session_active_flag': 1,
                }
            ),
            hour_of_day=(2 + index) % 24,
            day_of_week=6,
            realized_vol_proxy_2h=20.0 + index,
            spread_snapshot_bps=0.05,
            liquidity_snapshot_bin=1,
            funding_regime='neutral',
            session_active_flag=1,
            source_health_flag=1,
            invalid_reason='',
            observation_source_kind='independent_census_runtime_v1',
        )


def _base_manifest_payload() -> dict[str, object]:
    return {
        'included_session_ids': [DEFAULT_SESSION_ID],
        'sample_filter_rule': 'single_session_strict_7200x900_v1',
        'feature_recipe_version': 'second_state_causal_tensor_v1',
        'label_definition_version': 'next_bar_15m_ohlc_reparam_from_session_seconds_v1',
        'integrity_policy_version': 'strict_v1',
        'deployment_target_version': 'single_inst_all_deployment_eligible_15m_v1',
        'target_census_policy_version': 'deployment_eligible_boundary_census_v1',
        'target_window_policy_version': 'expanding_pre_origin_census_v1',
        'shift_state_definition_version': 'compact_boundary_state_v1',
        'shift_assumption_version': 'A_shift_suff_v1',
        'shift_diagnostic_version': 'support_mmd_propensity_v1',
        'strata_definition_version': 'coarse_shift_strata_v1',
        'sampling_stride_sec': DEFAULT_LABEL_SECONDS,
        'split_definition_version': 'blocked_temporal_hv_v1',
        'embargo_sec': 8100,
        'weighting_version': 'strata_ratio_weighting',
        'weight_definition': 'raw_ratio_no_clip_no_self_normalization',
        'weight_estimator_version': 'exact_strata_ratio_v1',
        'refit_policy_version': 'expanding_refit_recompute_all_statistics_v1',
        'domain_classifier_version': '',
        'regime_definition_version': 'boundary_regimes_v1',
        'bootstrap_definition_version': 'stationary_block_bootstrap_min9_v1',
        'evaluation_protocol_version': 'rolling_origin_v1',
        'score_definition_version': 'joint_scores_v1',
        'prerank_definition_version': 'multicalibration_v1',
        'policy_definition_version': 'ternary_expected_utility_policy_v1',
        'policy_parameter_ref': 'policy://defaults/ternary_expected_utility_policy_v1',
        'decision_utility_version': 'bar_close_return_with_adverse_excursion_penalty_v1',
        'utility_parameter_ref': 'utility://defaults/bar_close_return_with_adverse_excursion_penalty_v1',
        'execution_assumption_version': 'boundary_rebalance_hold_to_close_v1',
        'multiple_comparison_version': 'locked_candidate_set_v1',
    }
