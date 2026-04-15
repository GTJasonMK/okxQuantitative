from __future__ import annotations

from app.core.research_platform.training.splits import build_blocked_temporal_hv_v1


def test_build_blocked_temporal_splits_respects_embargo_and_origin_causality():
    splits = build_blocked_temporal_hv_v1(
        decision_ts=[1713000900, 1713001800, 1713002700, 1713003600, 1713004500],
        embargo_sec=8100,
        outer_origin_count=2,
    )

    assert splits[0]['train_end_ts'] + 8100 <= splits[0]['validation_start_ts']
    assert splits[0]['validation_end_ts'] + 8100 <= splits[0]['test_start_ts']
    assert splits[0]['census_window_end_ts'] < splits[0]['origin_ts']
    assert len(splits[0]['inner_validation_folds']) >= 2
    assert splits[0]['inner_validation_folds'][0]['embargo_sec'] == 8100


def test_build_blocked_temporal_splits_partition_future_test_blocks_without_overlap():
    decision_ts = [1713000900 + (index * 900) for index in range(24)]

    splits = build_blocked_temporal_hv_v1(
        decision_ts=decision_ts,
        embargo_sec=8100,
        outer_origin_count=2,
    )

    assert len(splits) == 2
    assert splits[0]['origin_ts'] == splits[0]['test_start_ts']
    assert splits[1]['origin_ts'] == splits[1]['test_start_ts']
    assert splits[0]['test_end_ts'] < splits[1]['test_start_ts']
    assert splits[0]['test_block_sample_count'] >= 1
    assert splits[1]['test_block_sample_count'] >= 1
    assert splits[0]['pre_origin_fit_end_ts'] == splits[0]['origin_ts'] - 900
    assert splits[1]['pre_origin_fit_end_ts'] == splits[1]['origin_ts'] - 900
