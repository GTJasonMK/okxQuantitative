from __future__ import annotations

import json
import time
from math import isfinite

from .storage_research_platform_schema import (
    CENSUS_COLUMN_DEFS,
    CENSUS_COLUMNS,
    CENSUS_TABLE_COLUMNS,
    CENSUS_TABLE_CONSTRAINTS,
    CENSUS_SECOND_STATE_COLUMNS,
    CENSUS_SECOND_STATE_TABLE_COLUMNS,
    CENSUS_SECOND_STATE_TABLE_CONSTRAINTS,
    SECOND_STATE_COLUMNS,
    SECOND_STATE_COLUMN_DEFS,
    SECOND_STATE_TABLE_COLUMNS,
    SECOND_STATE_TABLE_CONSTRAINTS,
    SESSION_COLUMNS,
    SESSION_COLUMN_DEFS,
    SESSION_TABLE_COLUMNS,
    build_create_table_sql,
    build_values,
    ensure_columns,
)


SESSION_STATUS_STARTING = 'starting'
SESSION_STATUS_RUNNING = 'running'
SESSION_STATUS_STOPPING = 'stopping'
SESSION_STATUS_STOPPED = 'stopped'
SESSION_STATUS_FINISHED = 'finished'
SESSION_STATUS_FAILED = 'failed'


class StorageResearchPlatformMixin:
    def _init_db(self):
        super()._init_db()
        with self._get_cursor() as cursor:
            cursor.execute(build_create_table_sql('research_collection_sessions', SESSION_TABLE_COLUMNS))
            ensure_columns(cursor, 'research_collection_sessions', SESSION_COLUMN_DEFS)
            cursor.execute(
                build_create_table_sql(
                    'research_second_states',
                    SECOND_STATE_TABLE_COLUMNS,
                    table_constraints=SECOND_STATE_TABLE_CONSTRAINTS,
                )
            )
            ensure_columns(cursor, 'research_second_states', SECOND_STATE_COLUMN_DEFS)
            cursor.execute(
                build_create_table_sql(
                    'research_census_second_states',
                    CENSUS_SECOND_STATE_TABLE_COLUMNS,
                    table_constraints=CENSUS_SECOND_STATE_TABLE_CONSTRAINTS,
                )
            )
            ensure_columns(cursor, 'research_census_second_states', SECOND_STATE_COLUMN_DEFS)
            cursor.execute(
                build_create_table_sql(
                    'research_target_census_15m',
                    CENSUS_TABLE_COLUMNS,
                    table_constraints=CENSUS_TABLE_CONSTRAINTS,
                )
            )
            ensure_columns(cursor, 'research_target_census_15m', CENSUS_COLUMN_DEFS)
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS research_artifacts (
                    artifact_ref TEXT PRIMARY KEY,
                    artifact_kind TEXT NOT NULL,
                    artifact_json TEXT NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )

    def list_table_names(self) -> list[str]:
        with self._get_cursor() as cursor:
            cursor.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name ASC"
            )
            rows = cursor.fetchall()
        return [str(row['name']) for row in rows]

    def save_research_artifact(
        self,
        *,
        artifact_ref: str,
        artifact_kind: str,
        payload: dict[str, object],
    ) -> None:
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT OR REPLACE INTO research_artifacts (
                    artifact_ref,
                    artifact_kind,
                    artifact_json,
                    created_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    artifact_ref,
                    artifact_kind,
                    json.dumps(payload, ensure_ascii=False, sort_keys=True),
                    float(time.time()),
                ),
            )

    def get_research_artifact(self, artifact_ref: str) -> dict[str, object] | None:
        with self._get_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM research_artifacts WHERE artifact_ref = ?',
                (artifact_ref,),
            )
            row = cursor.fetchone()
        return dict(row) if row is not None else None

    def deserialize_research_artifact(self, row: dict[str, object]) -> dict[str, object]:
        return json.loads(str(row['artifact_json']))

    def create_research_collection_session(self, **payload: object) -> str:
        started_at = float(time.time())
        session_id = f"sess-{time.time_ns()}"
        row = {
            'session_id': session_id,
            'inst_id': payload['inst_id'],
            'started_at': started_at,
            'ended_at': None,
            'planned_duration_sec': int(payload['planned_duration_sec']),
            'status': SESSION_STATUS_STARTING,
            'stop_reason': '',
            'last_error_code': '',
            'last_error_message': '',
            'failed_at': None,
            'collector_version': payload['collector_version'],
            'source_config_hash': payload['source_config_hash'],
            'trigger_mode': payload['trigger_mode'],
            'trigger_note': payload.get('trigger_note', ''),
            'sampling_policy_id': payload['sampling_policy_id'],
            'integrity_policy_version': payload['integrity_policy_version'],
            'feature_recipe_version': payload['feature_recipe_version'],
            'book_channel': payload['book_channel'],
            'valid_second_count': 0,
            'missing_second_count': 0,
            'book_stale_second_count': 0,
            'state_stale_second_count': 0,
            'coverage_ratio': 0.0,
            'quality_score': 0.0,
        }
        placeholders = ', '.join('?' for _ in SESSION_COLUMNS)
        columns = ', '.join(SESSION_COLUMNS)
        with self._get_cursor() as cursor:
            cursor.execute(
                f'INSERT INTO research_collection_sessions ({columns}) VALUES ({placeholders})',
                build_values(SESSION_COLUMNS, row),
            )
        return session_id

    def get_research_collection_session(self, session_id: str) -> dict[str, object] | None:
        with self._get_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM research_collection_sessions WHERE session_id = ?',
                (session_id,),
            )
            row = cursor.fetchone()
        return dict(row) if row is not None else None

    def list_research_collection_sessions(self, *, limit: int = 50) -> list[dict[str, object]]:
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM research_collection_sessions
                ORDER BY started_at DESC
                LIMIT ?
                """,
                (max(int(limit or 50), 1),),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def update_research_collection_session(self, session_id: str, **updates: object) -> dict[str, object]:
        assignments = ', '.join(f'{key} = ?' for key in updates)
        values = tuple(updates.values()) + (session_id,)
        with self._get_cursor() as cursor:
            cursor.execute(
                f'UPDATE research_collection_sessions SET {assignments} WHERE session_id = ?',
                values,
            )
        return self.get_research_collection_session(session_id)

    def save_research_second_state(self, **row: object) -> None:
        placeholders = ', '.join('?' for _ in SECOND_STATE_COLUMNS)
        columns = ', '.join(SECOND_STATE_COLUMNS)
        with self._get_cursor() as cursor:
            cursor.execute(
                f'INSERT OR REPLACE INTO research_second_states ({columns}) VALUES ({placeholders})',
                build_values(SECOND_STATE_COLUMNS, row),
            )

    def list_research_second_states(self, session_id: str, *, limit: int = 100) -> list[dict[str, object]]:
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM research_second_states
                WHERE session_id = ?
                ORDER BY second_bucket DESC
                LIMIT ?
                """,
                (session_id, max(int(limit or 100), 1)),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def list_research_second_states_for_inst(self, inst_id: str, *, end_ts: int, lookback_sec: int) -> list[dict[str, object]]:
        start_ts = int(end_ts) - max(int(lookback_sec or 0), 0)
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM research_second_states
                WHERE inst_id = ? AND second_bucket >= ? AND second_bucket < ?
                ORDER BY second_bucket ASC
                """,
                (inst_id, start_ts, int(end_ts)),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def list_research_second_state_inst_ids(self) -> list[str]:
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT inst_id
                FROM research_second_states
                ORDER BY inst_id ASC
                """
            )
            rows = cursor.fetchall()
        return [str(row['inst_id']) for row in rows if row['inst_id']]

    def save_research_census_second_state(self, **row: object) -> None:
        placeholders = ', '.join('?' for _ in CENSUS_SECOND_STATE_COLUMNS)
        columns = ', '.join(CENSUS_SECOND_STATE_COLUMNS)
        with self._get_cursor() as cursor:
            cursor.execute(
                f'INSERT OR REPLACE INTO research_census_second_states ({columns}) VALUES ({placeholders})',
                build_values(CENSUS_SECOND_STATE_COLUMNS, row),
            )

    def list_research_census_second_states_for_inst(
        self,
        inst_id: str,
        *,
        end_ts: int,
        lookback_sec: int,
    ) -> list[dict[str, object]]:
        start_ts = int(end_ts) - max(int(lookback_sec or 0), 0)
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM research_census_second_states
                WHERE inst_id = ? AND second_bucket >= ? AND second_bucket < ?
                ORDER BY second_bucket ASC
                """,
                (inst_id, start_ts, int(end_ts)),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def list_research_census_inst_ids(self) -> list[str]:
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT DISTINCT inst_id
                FROM research_census_second_states
                ORDER BY inst_id ASC
                """
            )
            rows = cursor.fetchall()
        return [str(row['inst_id']) for row in rows if row['inst_id']]

    def save_research_target_census(self, **row: object) -> None:
        placeholders = ', '.join('?' for _ in CENSUS_COLUMNS)
        columns = ', '.join(CENSUS_COLUMNS)
        with self._get_cursor() as cursor:
            cursor.execute(
                f'INSERT OR REPLACE INTO research_target_census_15m ({columns}) VALUES ({placeholders})',
                build_values(CENSUS_COLUMNS, row),
            )

    def get_research_target_census(self, inst_id: str, decision_ts: int) -> dict[str, object] | None:
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM research_target_census_15m
                WHERE inst_id = ? AND decision_ts = ?
                """,
                (inst_id, int(decision_ts)),
            )
            row = cursor.fetchone()
        return dict(row) if row is not None else None

    def refresh_research_collection_quality(self, session_id: str) -> dict[str, object]:
        rows = self.list_research_second_states(session_id, limit=100000)
        stats = _compute_quality_stats(rows)
        return self.update_research_collection_session(session_id, **stats)

    def get_research_session_coverage_summary(self, session_id: str) -> dict[str, object]:
        session = self.get_research_collection_session(session_id) or {}
        return {
            'coverage_ratio': session.get('coverage_ratio', 0.0),
            'valid_second_count': session.get('valid_second_count', 0),
            'missing_second_count': session.get('missing_second_count', 0),
            'book_stale_second_count': session.get('book_stale_second_count', 0),
            'state_stale_second_count': session.get('state_stale_second_count', 0),
            'quality_score': session.get('quality_score', 0.0),
        }

    def get_research_session_progress_summary(self, session_id: str) -> dict[str, object]:
        session = self.get_research_collection_session(session_id) or {}
        rows = self.list_research_second_states(session_id, limit=1)
        written_seconds = int(session.get('valid_second_count', 0)) + int(session.get('missing_second_count', 0))
        planned_duration_sec = max(int(session.get('planned_duration_sec', 0) or 0), 0)
        latest_second_bucket = int(rows[0]['second_bucket']) if rows else None
        seconds_to_next_boundary = _resolve_seconds_to_next_boundary(latest_second_bucket)
        return {
            'written_seconds': written_seconds,
            'remaining_seconds': max(planned_duration_sec - written_seconds, 0),
            'seconds_to_full_window': max(7200 - written_seconds, 0),
            'seconds_to_next_boundary': seconds_to_next_boundary,
        }

    def get_research_session_chart_series(self, session_id: str) -> dict[str, list[dict[str, object]]]:
        rows = list(reversed(self.list_research_second_states(session_id, limit=5000)))
        return {
            'price': [{'second_bucket': row['second_bucket'], 'close_price': row['close_price']} for row in rows],
            'trade': [{'second_bucket': row['second_bucket'], 'trade_count': row['trade_count']} for row in rows],
            'book': [{'second_bucket': row['second_bucket'], 'spread_bps': row['spread_bps']} for row in rows],
        }


def _compute_quality_stats(rows: list[dict[str, object]]) -> dict[str, object]:
    if not rows:
        return _empty_quality_stats()
    second_buckets = [int(row['second_bucket']) for row in rows]
    expected_count = max(second_buckets) - min(second_buckets) + 1
    valid_second_count = sum(int(row['is_valid_second']) for row in rows)
    missing_second_count = max(expected_count - len(rows), 0)
    book_stale_second_count = sum(1 for row in rows if float(row['book_age_seconds']) > 0.0)
    state_stale_second_count = sum(1 for row in rows if float(row['state_age_seconds']) > 0.0)
    coverage_ratio = valid_second_count / expected_count if expected_count > 0 else 0.0
    quality_score = coverage_ratio if isfinite(coverage_ratio) else 0.0
    return {
        'valid_second_count': valid_second_count,
        'missing_second_count': missing_second_count,
        'book_stale_second_count': book_stale_second_count,
        'state_stale_second_count': state_stale_second_count,
        'coverage_ratio': coverage_ratio,
        'quality_score': quality_score,
    }


def _empty_quality_stats() -> dict[str, object]:
    return {
        'valid_second_count': 0,
        'missing_second_count': 0,
        'book_stale_second_count': 0,
        'state_stale_second_count': 0,
        'coverage_ratio': 0.0,
        'quality_score': 0.0,
    }


def _resolve_seconds_to_next_boundary(latest_second_bucket: int | None) -> int:
    if latest_second_bucket is None:
        return 900
    elapsed_in_window = (int(latest_second_bucket) + 1) % 900
    if elapsed_in_window == 0:
        return 0
    return 900 - elapsed_in_window
