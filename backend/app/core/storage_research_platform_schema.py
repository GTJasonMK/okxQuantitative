from __future__ import annotations

from collections.abc import Iterable


SESSION_COLUMNS = (
    'session_id',
    'inst_id',
    'started_at',
    'ended_at',
    'planned_duration_sec',
    'status',
    'stop_reason',
    'last_error_code',
    'last_error_message',
    'failed_at',
    'collector_version',
    'source_config_hash',
    'trigger_mode',
    'trigger_note',
    'sampling_policy_id',
    'integrity_policy_version',
    'feature_recipe_version',
    'book_channel',
    'valid_second_count',
    'missing_second_count',
    'book_stale_second_count',
    'state_stale_second_count',
    'coverage_ratio',
    'quality_score',
)

SECOND_STATE_COLUMNS = (
    'session_id',
    'inst_id',
    'second_bucket',
    'ts_exchange',
    'ts_local',
    'bid_price',
    'ask_price',
    'bid_size',
    'ask_size',
    'bid_depth_10bps',
    'ask_depth_10bps',
    'mid_price',
    'microprice',
    'open_price',
    'high_price',
    'low_price',
    'close_price',
    'mark_price',
    'index_price',
    'trade_count',
    'signed_trade_notional',
    'buy_notional',
    'sell_notional',
    'buy_count',
    'sell_count',
    'max_trade_notional',
    'buy_burst_count',
    'sell_burst_count',
    'buy_burst_notional',
    'sell_burst_notional',
    'open_interest',
    'oi_delta',
    'funding_rate',
    'funding_delta',
    'premium',
    'basis_bps',
    'spread_bps',
    'book_level_count',
    'multi_level_book_imbalance',
    'book_slope',
    'has_trade_input',
    'has_book_input',
    'has_state_input',
    'book_age_seconds',
    'state_age_seconds',
    'clock_skew_ms',
    'is_valid_second',
    'quality_grade',
    'invalid_reason',
    'integrity_policy_version',
)

CENSUS_SECOND_STATE_COLUMNS = tuple(
    column
    for column in SECOND_STATE_COLUMNS
    if column != 'session_id'
)

CENSUS_COLUMNS = (
    'census_id',
    'inst_id',
    'decision_ts',
    'deployment_eligible',
    'census_policy_version',
    'shift_state_definition_version',
    'shift_state_blob_json',
    'hour_of_day',
    'day_of_week',
    'realized_vol_proxy_2h',
    'spread_snapshot_bps',
    'liquidity_snapshot_bin',
    'funding_regime',
    'session_active_flag',
    'source_health_flag',
    'invalid_reason',
    'observation_source_kind',
)

SECOND_STATE_COLUMN_DEFS = (
    ('bid_depth_10bps', 'REAL NOT NULL DEFAULT 0.0'),
    ('ask_depth_10bps', 'REAL NOT NULL DEFAULT 0.0'),
)

CENSUS_COLUMN_DEFS = (
    ('observation_source_kind', "TEXT NOT NULL DEFAULT 'legacy_session_coupled_v0'"),
)


def build_values(columns: tuple[str, ...], row: dict[str, object]) -> tuple[object, ...]:
    return tuple(row[column] for column in columns)


def ensure_columns(cursor, table_name: str, column_defs: Iterable[tuple[str, str]]) -> None:
    existing_columns = _read_existing_columns(cursor, table_name)
    for column_name, ddl in column_defs:
        if column_name in existing_columns:
            continue
        cursor.execute(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}')


def _read_existing_columns(cursor, table_name: str) -> set[str]:
    cursor.execute(f'PRAGMA table_info({table_name})')
    return {
        row['name'] if hasattr(row, 'keys') else row[1]
        for row in cursor.fetchall()
    }
