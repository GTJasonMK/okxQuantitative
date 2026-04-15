from __future__ import annotations

import pytest

from app.core.research_platform.training.origin_weighting import build_weighting_bundle
from app.core.research_platform.training.weighting import (
    compute_strata_ratio_weights,
    fit_logistic_density_ratio_oof,
)


def test_compute_strata_ratio_weights_marks_support_gap():
    result = compute_strata_ratio_weights(
        dataset_strata=['a', 'a', 'b'],
        census_strata=['a', 'b', 'b', 'c'],
        estimator_version='exact_strata_ratio_v1',
        definition_version='raw_ratio_no_clip_no_self_normalization',
    )

    assert result['support_overlap_result'] == 'gap_detected'
    assert result['dataset_status'] == 'research_only'


def test_fit_logistic_density_ratio_oof_returns_fit_refs():
    result = fit_logistic_density_ratio_oof(
        rows=[
            _build_density_row(
                domain_label=0,
                session_id='source-a',
                decision_ts=1713000900,
                rv_2h_bps=10.0,
                depth_10bps_log=1.0,
            ),
            _build_density_row(
                domain_label=0,
                session_id='source-b',
                decision_ts=1713014000,
                rv_2h_bps=11.0,
                depth_10bps_log=1.1,
            ),
            _build_density_row(
                domain_label=1,
                session_id='target-a',
                decision_ts=1713001800,
                rv_2h_bps=18.0,
                depth_10bps_log=0.5,
            ),
            _build_density_row(
                domain_label=1,
                session_id='target-b',
                decision_ts=1713015000,
                rv_2h_bps=19.0,
                depth_10bps_log=0.4,
            ),
        ],
    )

    fit = result['domain_classifier_fit']['1713003600']
    weight_fit = result['weight_fit']['1713003600']

    assert result['domain_classifier_version'] == 'l2_logistic_shift_state_v1'
    assert fit['categorical_feature_names'] == ['tod_bucket_6h', 'weekend_flag', 'near_funding_flag']
    assert fit['continuous_feature_names'] == [
        'ret_15m_bps',
        'ret_2h_bps',
        'rv_15m_bps',
        'rv_2h_bps',
        'range_15m_bps',
        'range_2h_bps',
        'spread_last_bps',
        'spread_median_60s_bps',
        'depth_10bps_log',
        'imbalance_10bps',
        'trade_count_60s',
        'trade_notional_60s_log',
        'funding_countdown_min',
        'book_stale_ratio_60s',
        'state_stale_ratio_60s',
        'source_health_flag',
        'session_active_flag',
    ]
    assert fit['class_prior_pi'] == 0.5
    assert fit['sampling_scheme'] == 'balanced_1_to_1'
    assert fit['calibration_method'] == 'none'
    assert 'coef' in fit
    assert 'eta_oof' in weight_fit
    assert result['fold_protocol'] == 'blocked_by_time_and_session_v1'


def test_fit_logistic_density_ratio_oof_materializes_blocked_session_folds():
    rows = [
        _build_density_row(
            domain_label=0,
            session_id='source-a',
            decision_ts=1713000900,
            rv_2h_bps=10.0,
            depth_10bps_log=1.0,
        ),
        _build_density_row(
            domain_label=0,
            session_id='source-a',
            decision_ts=1713001200,
            rv_2h_bps=10.5,
            depth_10bps_log=1.05,
        ),
        _build_density_row(
            domain_label=0,
            session_id='source-b',
            decision_ts=1713014000,
            rv_2h_bps=12.0,
            depth_10bps_log=1.2,
        ),
        _build_density_row(
            domain_label=0,
            session_id='source-b',
            decision_ts=1713014300,
            rv_2h_bps=12.5,
            depth_10bps_log=1.25,
        ),
        _build_density_row(
            domain_label=1,
            session_id='target-a',
            decision_ts=1713001800,
            rv_2h_bps=18.0,
            depth_10bps_log=0.5,
        ),
        _build_density_row(
            domain_label=1,
            session_id='target-a',
            decision_ts=1713002100,
            rv_2h_bps=18.5,
            depth_10bps_log=0.45,
        ),
        _build_density_row(
            domain_label=1,
            session_id='target-b',
            decision_ts=1713015000,
            rv_2h_bps=20.0,
            depth_10bps_log=0.4,
        ),
        _build_density_row(
            domain_label=1,
            session_id='target-b',
            decision_ts=1713015300,
            rv_2h_bps=20.5,
            depth_10bps_log=0.35,
        ),
    ]

    result = fit_logistic_density_ratio_oof(rows=rows)
    fit = result['domain_classifier_fit']['1713003600']
    weight_fit = result['weight_fit']['1713003600']

    assert len(fit['folds']) == 2
    assert fit['eta_oof_summary']['count'] == len(rows)
    assert weight_fit['oof_row_count'] == len(rows)
    assert len(weight_fit['eta_oof']) == len(rows)
    assert len(weight_fit['raw_density_ratio']) == len(rows)
    for fold in fit['folds']:
        assert fold['embargo_sec'] == 8100
        assert set(fold['train_session_ids']).isdisjoint(fold['eval_session_ids'])
        assert fold['eval_start_ts'] <= fold['eval_end_ts']
        assert fold['train_row_count'] > 0
        assert fold['eval_row_count'] > 0
        assert fold['train_end_ts'] <= fold['eval_start_ts'] - fold['embargo_sec'] or (
            fold['train_start_ts'] >= fold['eval_end_ts'] + fold['embargo_sec']
        )


def test_fit_logistic_density_ratio_oof_requires_two_sessions_per_domain():
    rows = [
        _build_density_row(
            domain_label=0,
            session_id='source-only',
            decision_ts=1713000900,
            rv_2h_bps=10.0,
            depth_10bps_log=1.0,
        ),
        _build_density_row(
            domain_label=0,
            session_id='source-only',
            decision_ts=1713001200,
            rv_2h_bps=10.5,
            depth_10bps_log=1.05,
        ),
        _build_density_row(
            domain_label=1,
            session_id='target-a',
            decision_ts=1713001800,
            rv_2h_bps=18.0,
            depth_10bps_log=0.5,
        ),
        _build_density_row(
            domain_label=1,
            session_id='target-b',
            decision_ts=1713005400,
            rv_2h_bps=20.0,
            depth_10bps_log=0.4,
        ),
    ]

    try:
        fit_logistic_density_ratio_oof(rows=rows)
    except ValueError as exc:
        assert 'requires at least 2 session blocks per domain' in str(exc)
        return
    raise AssertionError('expected fit_logistic_density_ratio_oof to reject insufficient session coverage')


def test_build_weighting_bundle_fits_strata_cutpoints_from_census_only():
    manifest = {
        'weighting_version': 'strata_ratio_weighting',
        'weight_estimator_version': 'exact_strata_ratio_v1',
        'weight_definition': 'raw_ratio_no_clip_no_self_normalization',
    }
    fit_rows = [
        _build_labeled_shift_row(rv_2h_bps=11.0, depth_10bps_log=6.05),
        _build_labeled_shift_row(rv_2h_bps=13.0, depth_10bps_log=6.15),
        _build_labeled_shift_row(rv_2h_bps=15.0, depth_10bps_log=6.25),
        _build_labeled_shift_row(rv_2h_bps=9000.0, depth_10bps_log=0.20),
        _build_labeled_shift_row(rv_2h_bps=9001.0, depth_10bps_log=0.21),
        _build_labeled_shift_row(rv_2h_bps=9002.0, depth_10bps_log=0.22),
    ]
    census_rows = [
        _build_census_shift_row(decision_ts=1713000000, rv_2h_bps=10.0, depth_10bps_log=6.0),
        _build_census_shift_row(decision_ts=1713000900, rv_2h_bps=12.0, depth_10bps_log=6.1),
        _build_census_shift_row(decision_ts=1713001800, rv_2h_bps=14.0, depth_10bps_log=6.2),
    ]
    test_rows = [_build_labeled_shift_row(rv_2h_bps=13.0, depth_10bps_log=6.15)]

    weighting, weights = build_weighting_bundle(
        manifest=manifest,
        origin_ts=1713003600,
        fit_rows=fit_rows,
        test_rows=test_rows,
        census_rows=census_rows,
    )

    assert weighting['dataset_status'] == 'ready'
    assert weights == pytest.approx([2.0])


def _build_density_row(
    *,
    domain_label: int,
    session_id: str,
    decision_ts: int,
    rv_2h_bps: float,
    depth_10bps_log: float,
) -> dict[str, object]:
    return {
        'origin_ts': 1713003600,
        'decision_ts': decision_ts,
        'session_id': session_id,
        'domain_label': domain_label,
        'tod_bucket_6h': 1,
        'weekend_flag': 0,
        'near_funding_flag': 0,
        'ret_15m_bps': 2.0 + domain_label,
        'ret_2h_bps': 8.0 + domain_label,
        'rv_15m_bps': 5.0 + domain_label,
        'rv_2h_bps': rv_2h_bps,
        'range_15m_bps': 4.0 + domain_label,
        'range_2h_bps': 10.0 + domain_label,
        'spread_last_bps': 0.08 + (0.01 * domain_label),
        'spread_median_60s_bps': 0.09 + (0.01 * domain_label),
        'depth_10bps_log': depth_10bps_log,
        'imbalance_10bps': 0.02 + (0.01 * domain_label),
        'trade_count_60s': 200.0 + (10 * domain_label),
        'trade_notional_60s_log': 12.0 + (0.5 * domain_label),
        'funding_countdown_min': 100.0,
        'book_stale_ratio_60s': 0.0,
        'state_stale_ratio_60s': 0.0,
        'source_health_flag': 1.0,
        'session_active_flag': 1.0,
    }


def _build_labeled_shift_row(*, rv_2h_bps: float, depth_10bps_log: float) -> dict[str, object]:
    return {
        'decision_ts': 1713000900,
        'session_id': 'sess-1',
        'shift_state': {
            'slot_15m': 1.0,
            'weekend_flag': 0.0,
            'ret_15m_bps': 2.0,
            'ret_2h_bps': 8.0,
            'rv_15m_bps': 5.0,
            'rv_2h_bps': rv_2h_bps,
            'range_15m_bps': 4.0,
            'range_2h_bps': 10.0,
            'spread_last_bps': 0.08,
            'spread_median_60s_bps': 0.09,
            'depth_10bps_log': depth_10bps_log,
            'imbalance_10bps': 0.02,
            'trade_count_60s': 200.0,
            'trade_notional_60s_log': 12.0,
            'funding_countdown_min': 100.0,
            'near_funding_flag': 0.0,
            'book_stale_ratio_60s': 0.0,
            'state_stale_ratio_60s': 0.0,
            'source_health_flag': 1.0,
            'session_active_flag': 1.0,
        },
    }


def _build_census_shift_row(
    *,
    decision_ts: int,
    rv_2h_bps: float,
    depth_10bps_log: float,
) -> dict[str, object]:
    return {
        'decision_ts': decision_ts,
        'shift_state_blob_json': (
            '{"slot_15m": 1, "weekend_flag": 0, "ret_15m_bps": 2.0, '
            '"ret_2h_bps": 8.0, "rv_15m_bps": 5.0, "rv_2h_bps": %s, '
            '"range_15m_bps": 4.0, "range_2h_bps": 10.0, "spread_last_bps": 0.08, '
            '"spread_median_60s_bps": 0.09, "depth_10bps_log": %s, "imbalance_10bps": 0.02, '
            '"trade_count_60s": 200, "trade_notional_60s_log": 12.0, "funding_countdown_min": 100, '
            '"near_funding_flag": 0, "book_stale_ratio_60s": 0.0, '
            '"state_stale_ratio_60s": 0.0, "source_health_flag": 1, "session_active_flag": 1}'
        ) % (rv_2h_bps, depth_10bps_log),
    }
