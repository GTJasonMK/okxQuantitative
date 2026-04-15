from __future__ import annotations

from .storage_research_platform_schema import build_values, ensure_columns
from .storage_research_platform_training_schema import (
    TRAINING_RUN_COLUMN_DEFS,
    TRAINING_RUN_COLUMNS,
)


class StorageResearchPlatformTrainingMixin:
    def _init_db(self):
        super()._init_db()
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS research_training_runs (
                    run_id TEXT PRIMARY KEY,
                    dataset_id TEXT NOT NULL,
                    model_family TEXT NOT NULL,
                    model_spec_ref TEXT NOT NULL,
                    candidate_set_ref TEXT NOT NULL,
                    training_seed INTEGER NOT NULL,
                    status TEXT NOT NULL,
                    progress_stage TEXT NOT NULL,
                    failure_reason TEXT NOT NULL DEFAULT '',
                    split_definition_version TEXT NOT NULL,
                    evaluation_protocol_version TEXT NOT NULL,
                    refit_policy_version TEXT NOT NULL,
                    outer_origin_selection_policy TEXT NOT NULL DEFAULT '',
                    weighting_version TEXT NOT NULL,
                    weight_definition TEXT NOT NULL,
                    weight_estimator_version TEXT NOT NULL,
                    weight_fit_ref TEXT NOT NULL,
                    domain_classifier_version TEXT NOT NULL,
                    domain_classifier_fit_ref TEXT NOT NULL,
                    score_definition_version TEXT NOT NULL,
                    prerank_definition_version TEXT NOT NULL,
                    regime_definition_version TEXT NOT NULL DEFAULT '',
                    bootstrap_definition_version TEXT NOT NULL,
                    policy_definition_version TEXT NOT NULL,
                    policy_parameter_ref TEXT NOT NULL,
                    decision_utility_version TEXT NOT NULL,
                    utility_parameter_ref TEXT NOT NULL,
                    execution_assumption_version TEXT NOT NULL,
                    multiple_comparison_version TEXT NOT NULL,
                    split_artifact_ref TEXT NOT NULL DEFAULT '',
                    forecast_metrics_ref TEXT NOT NULL DEFAULT '',
                    decision_metrics_ref TEXT NOT NULL DEFAULT '',
                    diagnostics_ref TEXT NOT NULL DEFAULT '',
                    bootstrap_result_ref TEXT NOT NULL DEFAULT '',
                    baseline_result_ref TEXT NOT NULL DEFAULT '',
                    comparison_result_ref TEXT NOT NULL DEFAULT '',
                    created_at REAL NOT NULL,
                    started_at REAL,
                    finished_at REAL
                )
                """
            )
            ensure_columns(cursor, 'research_training_runs', TRAINING_RUN_COLUMN_DEFS)

    def create_research_training_run(self, row: dict[str, object]) -> dict[str, object]:
        placeholders = ', '.join('?' for _ in TRAINING_RUN_COLUMNS)
        columns = ', '.join(TRAINING_RUN_COLUMNS)
        with self._get_cursor() as cursor:
            cursor.execute(
                f'INSERT OR REPLACE INTO research_training_runs ({columns}) VALUES ({placeholders})',
                build_values(TRAINING_RUN_COLUMNS, row),
            )
        return self.get_research_training_run(str(row['run_id']))

    def get_research_training_run(self, run_id: str) -> dict[str, object] | None:
        with self._get_cursor() as cursor:
            cursor.execute(
                'SELECT * FROM research_training_runs WHERE run_id = ?',
                (run_id,),
            )
            row = cursor.fetchone()
        return dict(row) if row is not None else None

    def list_research_training_runs(
        self,
        *,
        dataset_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        params: tuple[object, ...]
        query = 'SELECT * FROM research_training_runs'
        if dataset_id:
            query += ' WHERE dataset_id = ?'
            params = (dataset_id, max(int(limit or 50), 1))
        else:
            params = (max(int(limit or 50), 1),)
        query += ' ORDER BY created_at DESC LIMIT ?'
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            rows = cursor.fetchall()
        return [dict(row) for row in rows]

    def update_research_training_run(self, run_id: str, **updates: object) -> dict[str, object] | None:
        if not updates:
            return self.get_research_training_run(run_id)
        assignments = ', '.join(f'{key} = ?' for key in updates)
        values = tuple(updates.values()) + (run_id,)
        with self._get_cursor() as cursor:
            cursor.execute(
                f'UPDATE research_training_runs SET {assignments} WHERE run_id = ?',
                values,
            )
        return self.get_research_training_run(run_id)
