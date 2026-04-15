from __future__ import annotations

from collections import Counter

from .density_ratio_oof import fit_blocked_density_ratio_origin
from .density_ratio_oof import score_density_ratio_feature_vector


CATEGORICAL_FEATURE_NAMES = (
    'tod_bucket_6h',
    'weekend_flag',
    'near_funding_flag',
)
CONTINUOUS_FEATURE_NAMES = (
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
)
FEATURE_NAMES = CATEGORICAL_FEATURE_NAMES + CONTINUOUS_FEATURE_NAMES


def compute_strata_ratio_weights(
    *,
    dataset_strata: list[str],
    census_strata: list[str],
    estimator_version: str,
    definition_version: str,
) -> dict[str, object]:
    p_counter = Counter(census_strata)
    q_counter = Counter(dataset_strata)
    p_total = sum(p_counter.values()) or 1
    q_total = sum(q_counter.values()) or 1
    missing_support = [key for key, count in p_counter.items() if count > 0 and q_counter.get(key, 0) == 0]
    weights = {
        key: (p_counter[key] / p_total) / (q_counter[key] / q_total)
        for key in q_counter
    }
    return {
        'weights': weights,
        'support_overlap_result': 'ok' if not missing_support else 'gap_detected',
        'dataset_status': 'ready' if not missing_support else 'research_only',
        'weight_fit': {
            'weight_estimator_version': estimator_version,
            'weight_definition': definition_version,
            'p_counter': dict(p_counter),
            'q_counter': dict(q_counter),
            'missing_support': missing_support,
        },
    }


def fit_logistic_density_ratio_oof(*, rows: list[dict[str, object]]) -> dict[str, object]:
    grouped = _group_rows_by_origin(rows)
    fit_bundle = {}
    weight_bundle = {}
    for origin_ts, origin_rows in grouped.items():
        fit, weight_fit = fit_blocked_density_ratio_origin(
            rows=origin_rows,
            vector_builder=build_density_ratio_feature_vector,
            categorical_feature_names=list(CATEGORICAL_FEATURE_NAMES),
            continuous_feature_names=list(CONTINUOUS_FEATURE_NAMES),
        )
        fit_bundle[str(origin_ts)] = fit
        weight_bundle[str(origin_ts)] = weight_fit
    return {
        'domain_classifier_version': 'l2_logistic_shift_state_v1',
        'weight_estimator_version': 'oof_logistic_odds_ratio_v1',
        'weight_definition': 'raw_odds_ratio_no_clip_no_self_normalization',
        'fold_protocol': 'blocked_by_time_and_session_v1',
        'domain_classifier_fit': fit_bundle,
        'weight_fit': weight_bundle,
    }


def _group_rows_by_origin(rows: list[dict[str, object]]) -> dict[int, list[dict[str, object]]]:
    grouped: dict[int, list[dict[str, object]]] = {}
    for row in rows:
        grouped.setdefault(int(row['origin_ts']), []).append(row)
    return grouped


def build_density_ratio_feature_row(*, shift_state: dict[str, float]) -> dict[str, float]:
    return {
        'tod_bucket_6h': float(int(shift_state['slot_15m']) // 24),
        'weekend_flag': float(shift_state['weekend_flag']),
        'near_funding_flag': float(shift_state['near_funding_flag']),
        'ret_15m_bps': float(shift_state['ret_15m_bps']),
        'ret_2h_bps': float(shift_state['ret_2h_bps']),
        'rv_15m_bps': float(shift_state['rv_15m_bps']),
        'rv_2h_bps': float(shift_state['rv_2h_bps']),
        'range_15m_bps': float(shift_state['range_15m_bps']),
        'range_2h_bps': float(shift_state['range_2h_bps']),
        'spread_last_bps': float(shift_state['spread_last_bps']),
        'spread_median_60s_bps': float(shift_state['spread_median_60s_bps']),
        'depth_10bps_log': float(shift_state['depth_10bps_log']),
        'imbalance_10bps': float(shift_state['imbalance_10bps']),
        'trade_count_60s': float(shift_state['trade_count_60s']),
        'trade_notional_60s_log': float(shift_state['trade_notional_60s_log']),
        'funding_countdown_min': float(shift_state['funding_countdown_min']),
        'book_stale_ratio_60s': float(shift_state['book_stale_ratio_60s']),
        'state_stale_ratio_60s': float(shift_state['state_stale_ratio_60s']),
        'source_health_flag': float(shift_state['source_health_flag']),
        'session_active_flag': float(shift_state['session_active_flag']),
    }


def build_density_ratio_feature_vector(row: dict[str, object]) -> list[float]:
    return [float(row[name]) for name in FEATURE_NAMES]


def score_density_ratio_row(*, row: dict[str, object], fit: dict[str, object]) -> float:
    vector = build_density_ratio_feature_vector(row)
    return score_density_ratio_feature_vector(vector=vector, fit=fit)
