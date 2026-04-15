from __future__ import annotations

from app.core.research_platform.dataset.diagnostic_propensity import run_propensity_check


def test_run_propensity_check_materializes_session_blocked_folds():
    result = run_propensity_check(
        labeled_shift_rows=[
            _build_labeled_row(session_id='source-a', decision_ts=1000, rv_2h_bps=10.0),
            _build_labeled_row(session_id='source-a', decision_ts=1100, rv_2h_bps=10.5),
            _build_labeled_row(session_id='source-b', decision_ts=20000, rv_2h_bps=12.0),
            _build_labeled_row(session_id='source-b', decision_ts=20100, rv_2h_bps=12.5),
        ],
        census_shift_rows=[
            _build_census_row(decision_ts=2000, rv_2h_bps=18.0),
            _build_census_row(decision_ts=2100, rv_2h_bps=18.5),
            _build_census_row(decision_ts=21000, rv_2h_bps=20.0),
            _build_census_row(decision_ts=21100, rv_2h_bps=20.5),
        ],
    )

    assert result['split_version'] == 'domainwise_session_temporal_two_fold_v1'
    assert len(result['folds']) == 2
    assert result['oof_sample_count'] == 8
    for fold in result['folds']:
        assert fold['embargo_sec'] == 8100
        assert set(fold['source_train_session_ids']).isdisjoint(fold['source_eval_session_ids'])
        assert fold['source_eval_row_count'] > 0
        assert fold['target_eval_row_count'] > 0
        assert fold['eval_start_ts'] <= fold['eval_end_ts']
        assert fold['train_end_ts'] <= fold['eval_start_ts'] - fold['embargo_sec'] or (
            fold['train_start_ts'] >= fold['eval_end_ts'] + fold['embargo_sec']
        )


def _build_labeled_row(*, session_id: str, decision_ts: int, rv_2h_bps: float) -> dict[str, object]:
    return {
        'session_id': session_id,
        'decision_ts': decision_ts,
        'shift_state': _build_shift_state(rv_2h_bps=rv_2h_bps),
    }


def _build_census_row(*, decision_ts: int, rv_2h_bps: float) -> dict[str, object]:
    return {
        'decision_ts': decision_ts,
        'shift_state_blob_json': '{"slot_15m": 1, "weekend_flag": 0, "ret_15m_bps": 2.0, "ret_2h_bps": 8.0, "rv_15m_bps": 5.0, "rv_2h_bps": %s, "range_15m_bps": 4.0, "range_2h_bps": 10.0, "spread_last_bps": 0.08, "spread_median_60s_bps": 0.09, "depth_10bps_log": 3.0, "imbalance_10bps": 0.02, "trade_count_60s": 200, "trade_notional_60s_log": 12.0, "funding_countdown_min": 100, "near_funding_flag": 0, "book_stale_ratio_60s": 0.0, "state_stale_ratio_60s": 0.0, "source_health_flag": 1, "session_active_flag": 1}' % rv_2h_bps,
    }


def _build_shift_state(*, rv_2h_bps: float) -> dict[str, float]:
    return {
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
        'depth_10bps_log': 3.0,
        'imbalance_10bps': 0.02,
        'trade_count_60s': 200.0,
        'trade_notional_60s_log': 12.0,
        'funding_countdown_min': 100.0,
        'near_funding_flag': 0.0,
        'book_stale_ratio_60s': 0.0,
        'state_stale_ratio_60s': 0.0,
        'source_health_flag': 1.0,
        'session_active_flag': 1.0,
    }
