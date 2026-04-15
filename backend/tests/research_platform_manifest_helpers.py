from __future__ import annotations

import json

from app.core.data_storage import DataStorage
from app.core.research_platform.dataset.service import ResearchDatasetService

from .research_platform_dataset_helpers import (
    DEFAULT_DECISION_TS,
    DEFAULT_INPUT_SECONDS,
    DEFAULT_INST_ID,
    DEFAULT_LABEL_SECONDS,
    DEFAULT_SESSION_ID,
)


def build_manifest_payload() -> dict[str, object]:
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


def seed_dataset_rows(
    storage: DataStorage,
    *,
    shift_gap: bool = False,
    sample_count: int = 6,
) -> None:
    for index in range(int(sample_count)):
        decision_ts = DEFAULT_DECISION_TS + (index * DEFAULT_LABEL_SECONDS)
        _save_boundary_target(storage, decision_ts, index)
        _save_sample_index(storage, decision_ts)
        _save_census(storage, decision_ts, index, shift_gap=shift_gap)
    if shift_gap:
        _save_background_census(storage, base_decision_ts=DEFAULT_DECISION_TS - DEFAULT_INPUT_SECONDS)


def create_dataset_manifest(
    storage: DataStorage,
    *,
    shift_gap: bool = False,
    sample_count: int = 6,
    payload_overrides: dict[str, object] | None = None,
) -> dict[str, object]:
    seed_dataset_rows(storage, shift_gap=shift_gap, sample_count=sample_count)
    payload = build_manifest_payload()
    if payload_overrides:
        payload.update(payload_overrides)
    return ResearchDatasetService(storage=storage).create_dataset_manifest(payload)


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


def _save_census(storage: DataStorage, decision_ts: int, index: int, *, shift_gap: bool) -> None:
    rv_value = 80.0 + index + (300.0 if shift_gap else 0.0)
    depth_value = 7.2 + (index * 0.02) + (4.0 if shift_gap else 0.0)
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
