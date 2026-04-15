from __future__ import annotations

from .storage_research_platform_dataset_schema import (
    BOUNDARY_TARGET_COLUMNS,
    MANIFEST_COLUMN_DEFS,
    MANIFEST_COLUMNS,
    SAMPLE_INDEX_COLUMNS,
)
from .storage_research_platform_schema import build_values
from .storage_research_platform_schema import ensure_columns


class StorageResearchPlatformDatasetMixin:
    def _init_db(self):
        super()._init_db()
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS research_boundary_targets_15m (
                    target_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    inst_id TEXT NOT NULL,
                    decision_ts INTEGER NOT NULL,
                    anchor_second_bucket INTEGER NOT NULL,
                    anchor_close_price REAL NOT NULL,
                    label_start_ts INTEGER NOT NULL,
                    label_end_ts INTEGER NOT NULL,
                    open_price REAL NOT NULL,
                    high_price REAL NOT NULL,
                    low_price REAL NOT NULL,
                    close_price REAL NOT NULL,
                    r_open REAL NOT NULL,
                    r_close REAL NOT NULL,
                    u REAL NOT NULL,
                    d REAL NOT NULL,
                    label_complete INTEGER NOT NULL,
                    invalid_reason TEXT NOT NULL DEFAULT '',
                    label_definition_version TEXT NOT NULL,
                    UNIQUE (session_id, decision_ts)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS research_sample_index_15m (
                    sample_id TEXT PRIMARY KEY,
                    session_id TEXT NOT NULL,
                    inst_id TEXT NOT NULL,
                    decision_ts INTEGER NOT NULL,
                    input_start_ts INTEGER NOT NULL,
                    input_end_ts INTEGER NOT NULL,
                    label_start_ts INTEGER NOT NULL,
                    label_end_ts INTEGER NOT NULL,
                    input_second_count INTEGER NOT NULL,
                    label_second_count INTEGER NOT NULL,
                    input_complete_7200 INTEGER NOT NULL,
                    label_complete_900 INTEGER NOT NULL,
                    sample_valid INTEGER NOT NULL,
                    ready_for_inference INTEGER NOT NULL,
                    ready_for_training INTEGER NOT NULL,
                    invalid_reason TEXT NOT NULL DEFAULT '',
                    prev_sample_overlap_seconds INTEGER NOT NULL,
                    stride_seconds INTEGER NOT NULL,
                    UNIQUE (session_id, decision_ts)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS research_dataset_manifests (
                    dataset_id TEXT PRIMARY KEY,
                    inst_id TEXT NOT NULL,
                    included_session_ids_json TEXT NOT NULL,
                    sample_filter_rule TEXT NOT NULL,
                    feature_recipe_version TEXT NOT NULL,
                    label_definition_version TEXT NOT NULL,
                    integrity_policy_version TEXT NOT NULL,
                    integrity_policy_json TEXT NOT NULL DEFAULT '{}',
                    deployment_target_version TEXT NOT NULL,
                    target_census_policy_version TEXT NOT NULL,
                    target_window_policy_version TEXT NOT NULL,
                    strata_definition_version TEXT NOT NULL,
                    strata_fit_ref TEXT NOT NULL,
                    sampling_stride_sec INTEGER NOT NULL,
                    split_definition_version TEXT NOT NULL,
                    outer_origin_selection_policy TEXT NOT NULL DEFAULT '',
                    embargo_sec INTEGER NOT NULL,
                    weighting_version TEXT NOT NULL,
                    weight_definition TEXT NOT NULL,
                    weight_estimator_version TEXT NOT NULL,
                    weight_fit_ref TEXT NOT NULL,
                    shift_state_definition_version TEXT NOT NULL,
                    shift_assumption_version TEXT NOT NULL,
                    shift_diagnostic_version TEXT NOT NULL,
                    refit_policy_version TEXT NOT NULL,
                    domain_classifier_version TEXT NOT NULL,
                    domain_classifier_fit_ref TEXT NOT NULL,
                    regime_definition_version TEXT NOT NULL,
                    bootstrap_definition_version TEXT NOT NULL,
                    evaluation_protocol_version TEXT NOT NULL,
                    score_definition_version TEXT NOT NULL,
                    prerank_definition_version TEXT NOT NULL,
                    policy_definition_version TEXT NOT NULL,
                    policy_parameter_ref TEXT NOT NULL,
                    decision_utility_version TEXT NOT NULL,
                    utility_parameter_ref TEXT NOT NULL,
                    execution_assumption_version TEXT NOT NULL,
                    multiple_comparison_version TEXT NOT NULL,
                    dataset_status TEXT NOT NULL,
                    shift_diagnostic_result TEXT NOT NULL,
                    target_census_count INTEGER NOT NULL,
                    support_overlap_result TEXT NOT NULL,
                    train_sample_count INTEGER NOT NULL,
                    val_sample_count INTEGER NOT NULL,
                    test_sample_count INTEGER NOT NULL,
                    train_effective_sample_size REAL NOT NULL,
                    val_effective_sample_size REAL NOT NULL,
                    test_effective_sample_size REAL NOT NULL,
                    created_at REAL NOT NULL
                )
                """
            )
            ensure_columns(cursor, 'research_dataset_manifests', MANIFEST_COLUMN_DEFS)

    def save_research_boundary_target_15m(self, **row: object) -> None:
        placeholders = ', '.join('?' for _ in BOUNDARY_TARGET_COLUMNS)
        columns = ', '.join(BOUNDARY_TARGET_COLUMNS)
        with self._get_cursor() as cursor:
            cursor.execute(
                f'INSERT OR REPLACE INTO research_boundary_targets_15m ({columns}) VALUES ({placeholders})',
                build_values(BOUNDARY_TARGET_COLUMNS, row),
            )

    def get_research_boundary_target_15m(
        self,
        session_id: str,
        decision_ts: int,
    ) -> dict[str, object] | None:
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM research_boundary_targets_15m
                WHERE session_id = ? AND decision_ts = ?
                """,
                (session_id, int(decision_ts)),
            )
            row = cursor.fetchone()
        return dict(row) if row is not None else None

    def list_research_boundary_targets_15m_for_sessions(
        self,
        session_ids: list[str],
    ) -> list[dict[str, object]]:
        return self._list_by_sessions(
            table_name='research_boundary_targets_15m',
            session_ids=session_ids,
        )

    def save_research_sample_index_15m(self, **row: object) -> None:
        placeholders = ', '.join('?' for _ in SAMPLE_INDEX_COLUMNS)
        columns = ', '.join(SAMPLE_INDEX_COLUMNS)
        with self._get_cursor() as cursor:
            cursor.execute(
                f'INSERT OR REPLACE INTO research_sample_index_15m ({columns}) VALUES ({placeholders})',
                build_values(SAMPLE_INDEX_COLUMNS, row),
            )

    def get_research_sample_index_15m(
        self,
        session_id: str,
        decision_ts: int,
    ) -> dict[str, object] | None:
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM research_sample_index_15m
                WHERE session_id = ? AND decision_ts = ?
                """,
                (session_id, int(decision_ts)),
            )
            row = cursor.fetchone()
        return dict(row) if row is not None else None

    def list_research_sample_index_15m_for_sessions(
        self,
        session_ids: list[str],
    ) -> list[dict[str, object]]:
        return self._list_by_sessions(
            table_name='research_sample_index_15m',
            session_ids=session_ids,
        )

    def list_research_target_census_for_inst(
        self,
        inst_id: str,
    ) -> list[dict[str, object]]:
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM research_target_census_15m
                WHERE inst_id = ?
                ORDER BY decision_ts ASC
                """,
                (inst_id,),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def save_research_dataset_manifest(self, **row: object) -> None:
        placeholders = ', '.join('?' for _ in MANIFEST_COLUMNS)
        columns = ', '.join(MANIFEST_COLUMNS)
        with self._get_cursor() as cursor:
            cursor.execute(
                f'INSERT OR REPLACE INTO research_dataset_manifests ({columns}) VALUES ({placeholders})',
                build_values(MANIFEST_COLUMNS, row),
            )

    def get_research_dataset_manifest(
        self,
        dataset_id: str,
    ) -> dict[str, object] | None:
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM research_dataset_manifests
                WHERE dataset_id = ?
                """,
                (dataset_id,),
            )
            row = cursor.fetchone()
        return dict(row) if row is not None else None

    def list_research_dataset_manifests(
        self,
        *,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT * FROM research_dataset_manifests
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (max(int(limit or 50), 1),),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def _list_by_sessions(
        self,
        *,
        table_name: str,
        session_ids: list[str],
    ) -> list[dict[str, object]]:
        if not session_ids:
            return []
        placeholders = ', '.join('?' for _ in session_ids)
        with self._get_cursor() as cursor:
            cursor.execute(
                f"""
                SELECT * FROM {table_name}
                WHERE session_id IN ({placeholders})
                ORDER BY decision_ts ASC
                """,
                tuple(session_ids),
            )
            rows = cursor.fetchall()
        return [dict(row) for row in rows]
