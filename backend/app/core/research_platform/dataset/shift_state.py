from __future__ import annotations

import json


SHIFT_STATE_FIELDS_V1 = (
    'slot_15m',
    'weekend_flag',
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
    'near_funding_flag',
    'book_stale_ratio_60s',
    'state_stale_ratio_60s',
    'source_health_flag',
    'session_active_flag',
)

REGIME_FIELDS_V1 = (
    'hour_of_day',
    'day_of_week',
    'realized_vol_bin',
    'spread_bin',
    'liquidity_bin',
    'funding_regime',
)

REGIME_WEIGHTED_MEAN_FIELDS = (
    'joint_nll_mean',
    'energy_score_mean',
    'variogram_score_mean',
    'calibration_error',
    'sharpness_mean',
)

REGIME_OUTPUT_FIELDS_V1 = (
    'regime_key',
    'sample_count',
    'raw_weight_sum',
    *REGIME_WEIGHTED_MEAN_FIELDS,
)


def parse_shift_state_blob(census_row: dict[str, object]) -> dict[str, float]:
    raw_state = json.loads(str(census_row['shift_state_blob_json']))
    validate_shift_state_schema(raw_state)
    return {
        field_name: float(raw_state[field_name])
        for field_name in SHIFT_STATE_FIELDS_V1
    }


def validate_shift_state_schema(blob: dict[str, object]) -> None:
    """校验 shift state blob 字段集合与 SHIFT_STATE_FIELDS_V1 精确匹配。

    不允许不升版本自由扩展字段，也不允许缺少字段。
    """
    expected = set(SHIFT_STATE_FIELDS_V1)
    actual = set(blob.keys())
    missing = expected - actual
    extra = actual - expected
    if missing or extra:
        parts: list[str] = []
        if missing:
            parts.append(f'缺少字段: {sorted(missing)}')
        if extra:
            parts.append(f'多余字段: {sorted(extra)}')
        raise ValueError(
            f'shift_state_blob schema 与 compact_boundary_state_v1 不匹配: '
            f'{"; ".join(parts)}'
        )


def build_labeled_shift_row(
    *,
    sample_row: dict[str, object],
    target_row: dict[str, object],
    census_row: dict[str, object],
) -> dict[str, object]:
    shift_state = parse_shift_state_blob(census_row)
    return {
        'session_id': sample_row['session_id'],
        'inst_id': sample_row['inst_id'],
        'decision_ts': int(sample_row['decision_ts']),
        'r_close': float(target_row['r_close']),
        'shift_state': shift_state,
        'hour_of_day': int(census_row['hour_of_day']),
        'day_of_week': int(census_row['day_of_week']),
        'funding_regime': str(census_row['funding_regime']),
        'spread_snapshot_bps': float(census_row['spread_snapshot_bps']),
        'realized_vol_proxy_2h': float(census_row['realized_vol_proxy_2h']),
        'liquidity_snapshot_bin': int(census_row['liquidity_snapshot_bin']),
    }


def build_boundary_regime_schema() -> dict[str, object]:
    return {
        'definition_version': 'boundary_regimes_v1',
        'required_fields': list(REGIME_FIELDS_V1),
        'output_fields': list(REGIME_OUTPUT_FIELDS_V1),
    }
