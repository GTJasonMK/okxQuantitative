from __future__ import annotations

from collections.abc import Iterable

from .research_platform.census.constants import INDEPENDENT_CENSUS_SOURCE_KIND


SESSION_TABLE_COLUMNS = (
    ('session_id', 'TEXT PRIMARY KEY'),
    ('inst_id', 'TEXT NOT NULL'),
    ('started_at', 'REAL NOT NULL'),
    ('ended_at', 'REAL'),
    ('planned_duration_sec', 'INTEGER NOT NULL'),
    ('status', 'TEXT NOT NULL'),
    ('stop_reason', "TEXT NOT NULL DEFAULT ''"),
    ('last_error_code', "TEXT NOT NULL DEFAULT ''"),
    ('last_error_message', "TEXT NOT NULL DEFAULT ''"),
    ('failed_at', 'REAL'),
    ('collector_version', 'TEXT NOT NULL'),
    ('source_config_hash', 'TEXT NOT NULL'),
    ('trigger_mode', 'TEXT NOT NULL'),
    ('trigger_note', "TEXT NOT NULL DEFAULT ''"),
    ('sampling_policy_id', 'TEXT NOT NULL'),
    ('integrity_policy_version', 'TEXT NOT NULL'),
    ('feature_recipe_version', 'TEXT NOT NULL'),
    ('book_channel', 'TEXT NOT NULL'),
    ('valid_second_count', 'INTEGER NOT NULL DEFAULT 0'),
    ('missing_second_count', 'INTEGER NOT NULL DEFAULT 0'),
    ('book_stale_second_count', 'INTEGER NOT NULL DEFAULT 0'),
    ('state_stale_second_count', 'INTEGER NOT NULL DEFAULT 0'),
    ('coverage_ratio', 'REAL NOT NULL DEFAULT 0.0'),
    ('quality_score', 'REAL NOT NULL DEFAULT 0.0'),
)

SECOND_STATE_TABLE_COLUMNS = (
    ('session_id', 'TEXT NOT NULL'),
    ('inst_id', 'TEXT NOT NULL'),
    ('second_bucket', 'INTEGER NOT NULL'),
    ('ts_exchange', 'REAL NOT NULL'),
    ('ts_local', 'REAL NOT NULL'),
    ('bid_price', 'REAL NOT NULL'),
    ('ask_price', 'REAL NOT NULL'),
    ('bid_size', 'REAL NOT NULL'),
    ('ask_size', 'REAL NOT NULL'),
    ('bid_depth_10bps', 'REAL NOT NULL DEFAULT 0.0'),
    ('ask_depth_10bps', 'REAL NOT NULL DEFAULT 0.0'),
    ('mid_price', 'REAL NOT NULL'),
    ('microprice', 'REAL NOT NULL'),
    ('open_price', 'REAL NOT NULL'),
    ('high_price', 'REAL NOT NULL'),
    ('low_price', 'REAL NOT NULL'),
    ('close_price', 'REAL NOT NULL'),
    ('mark_price', 'REAL NOT NULL'),
    ('index_price', 'REAL NOT NULL'),
    ('trade_count', 'INTEGER NOT NULL'),
    ('signed_trade_notional', 'REAL NOT NULL'),
    ('buy_notional', 'REAL NOT NULL'),
    ('sell_notional', 'REAL NOT NULL'),
    ('buy_count', 'INTEGER NOT NULL'),
    ('sell_count', 'INTEGER NOT NULL'),
    ('max_trade_notional', 'REAL NOT NULL'),
    ('buy_burst_count', 'INTEGER NOT NULL'),
    ('sell_burst_count', 'INTEGER NOT NULL'),
    ('buy_burst_notional', 'REAL NOT NULL'),
    ('sell_burst_notional', 'REAL NOT NULL'),
    ('open_interest', 'REAL NOT NULL'),
    ('oi_delta', 'REAL NOT NULL'),
    ('funding_rate', 'REAL NOT NULL'),
    ('funding_delta', 'REAL NOT NULL'),
    ('premium', 'REAL NOT NULL'),
    ('basis_bps', 'REAL NOT NULL'),
    ('spread_bps', 'REAL NOT NULL'),
    ('book_level_count', 'INTEGER NOT NULL'),
    ('multi_level_book_imbalance', 'REAL NOT NULL'),
    ('book_slope', 'REAL NOT NULL'),
    ('has_trade_input', 'INTEGER NOT NULL'),
    ('has_book_input', 'INTEGER NOT NULL'),
    ('has_state_input', 'INTEGER NOT NULL'),
    ('book_age_seconds', 'REAL NOT NULL'),
    ('state_age_seconds', 'REAL NOT NULL'),
    ('clock_skew_ms', 'REAL NOT NULL'),
    ('is_valid_second', 'INTEGER NOT NULL'),
    ('quality_grade', 'TEXT NOT NULL'),
    ('invalid_reason', "TEXT NOT NULL DEFAULT ''"),
    ('integrity_policy_version', 'TEXT NOT NULL'),
)

SECOND_STATE_TABLE_CONSTRAINTS = (
    'PRIMARY KEY (session_id, second_bucket)',
)

CENSUS_SECOND_STATE_TABLE_COLUMNS = tuple(
    (name, ddl)
    for name, ddl in SECOND_STATE_TABLE_COLUMNS
    if name != 'session_id'
)

CENSUS_SECOND_STATE_TABLE_CONSTRAINTS = (
    'PRIMARY KEY (inst_id, second_bucket)',
)

CENSUS_TABLE_COLUMNS = (
    ('census_id', 'TEXT PRIMARY KEY'),
    ('inst_id', 'TEXT NOT NULL'),
    ('decision_ts', 'INTEGER NOT NULL'),
    ('deployment_eligible', 'INTEGER NOT NULL'),
    ('census_policy_version', 'TEXT NOT NULL'),
    ('shift_state_definition_version', 'TEXT NOT NULL'),
    ('shift_state_blob_json', 'TEXT NOT NULL'),
    ('hour_of_day', 'INTEGER NOT NULL'),
    ('day_of_week', 'INTEGER NOT NULL'),
    ('realized_vol_proxy_2h', 'REAL NOT NULL'),
    ('spread_snapshot_bps', 'REAL NOT NULL'),
    ('liquidity_snapshot_bin', 'INTEGER NOT NULL'),
    ('funding_regime', 'TEXT NOT NULL'),
    ('session_active_flag', 'INTEGER NOT NULL'),
    ('source_health_flag', 'INTEGER NOT NULL'),
    ('invalid_reason', "TEXT NOT NULL DEFAULT ''"),
    ('observation_source_kind', f"TEXT NOT NULL DEFAULT '{INDEPENDENT_CENSUS_SOURCE_KIND}'"),
)

CENSUS_TABLE_CONSTRAINTS = (
    'UNIQUE (inst_id, decision_ts)',
)

SESSION_COLUMNS = tuple(name for name, _ in SESSION_TABLE_COLUMNS)
SECOND_STATE_COLUMNS = tuple(name for name, _ in SECOND_STATE_TABLE_COLUMNS)
CENSUS_SECOND_STATE_COLUMNS = tuple(name for name, _ in CENSUS_SECOND_STATE_TABLE_COLUMNS)
CENSUS_COLUMNS = tuple(name for name, _ in CENSUS_TABLE_COLUMNS)


def _pick_column_defs(
    table_columns: tuple[tuple[str, str], ...],
    *names: str,
) -> tuple[tuple[str, str], ...]:
    definitions = {name: ddl for name, ddl in table_columns}
    return tuple((name, definitions[name]) for name in names)


SESSION_COLUMN_DEFS = _pick_column_defs(
    SESSION_TABLE_COLUMNS,
    'last_error_code',
    'last_error_message',
    'failed_at',
)

SECOND_STATE_COLUMN_DEFS = _pick_column_defs(
    SECOND_STATE_TABLE_COLUMNS,
    'bid_depth_10bps',
    'ask_depth_10bps',
)

CENSUS_COLUMN_DEFS = _pick_column_defs(
    CENSUS_TABLE_COLUMNS,
    'observation_source_kind',
)


def build_values(columns: tuple[str, ...], row: dict[str, object]) -> tuple[object, ...]:
    return tuple(row[column] for column in columns)


def build_create_table_sql(
    table_name: str,
    table_columns: tuple[tuple[str, str], ...],
    *,
    table_constraints: tuple[str, ...] = (),
) -> str:
    definitions = [f'{name} {ddl}' for name, ddl in table_columns]
    definitions.extend(table_constraints)
    joined = ',\n                    '.join(definitions)
    return f"""
                CREATE TABLE IF NOT EXISTS {table_name} (
                    {joined}
                )
                """


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
