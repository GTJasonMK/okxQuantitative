from __future__ import annotations

import json


class StorageResearchPlatformDeleteMixin:
    def list_research_dataset_ids_for_session(self, session_id: str) -> list[str]:
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT dataset_id, included_session_ids_json
                FROM research_dataset_manifests
                ORDER BY created_at DESC
                """
            )
            rows = cursor.fetchall()
        dataset_ids = []
        for row in rows:
            session_ids = _load_session_ids(row['included_session_ids_json'])
            if session_id in session_ids:
                dataset_ids.append(str(row['dataset_id']))
        return dataset_ids

    def list_research_training_run_ids_for_dataset(self, dataset_id: str) -> list[str]:
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT run_id FROM research_training_runs
                WHERE dataset_id = ?
                ORDER BY created_at DESC
                """,
                (dataset_id,),
            )
            rows = cursor.fetchall()
        return [str(row['run_id']) for row in rows]

    def delete_research_collection_session_cascade(self, session_id: str) -> dict[str, object] | None:
        session = self.get_research_collection_session(session_id)
        if session is None:
            return None
        with self._get_cursor() as cursor:
            cursor.execute('DELETE FROM research_second_states WHERE session_id = ?', (session_id,))
            deleted_second_state_count = cursor.rowcount
            cursor.execute('DELETE FROM research_sample_index_15m WHERE session_id = ?', (session_id,))
            deleted_sample_index_count = cursor.rowcount
            cursor.execute('DELETE FROM research_boundary_targets_15m WHERE session_id = ?', (session_id,))
            deleted_boundary_target_count = cursor.rowcount
            cursor.execute('DELETE FROM research_collection_sessions WHERE session_id = ?', (session_id,))
            deleted_session_count = cursor.rowcount
        return {
            'session_id': session_id,
            'inst_id': str(session['inst_id']),
            'deleted_second_state_count': deleted_second_state_count,
            'deleted_sample_index_count': deleted_sample_index_count,
            'deleted_boundary_target_count': deleted_boundary_target_count,
            'deleted_session_count': deleted_session_count,
        }

    def delete_research_dataset_manifest(self, dataset_id: str) -> dict[str, object] | None:
        manifest = self.get_research_dataset_manifest(dataset_id)
        if manifest is None:
            return None
        artifact_refs = _extract_dataset_artifact_refs(manifest)
        with self._get_cursor() as cursor:
            if artifact_refs:
                placeholders = ', '.join('?' for _ in artifact_refs)
                cursor.execute(
                    f'DELETE FROM research_artifacts WHERE artifact_ref IN ({placeholders})',
                    tuple(artifact_refs),
                )
            cursor.execute(
                'DELETE FROM research_dataset_manifests WHERE dataset_id = ?',
                (dataset_id,),
            )
            deleted_dataset_count = cursor.rowcount
        return {
            'dataset_id': dataset_id,
            'deleted_dataset_count': deleted_dataset_count,
        }


def _load_session_ids(raw_value: object) -> set[str]:
    try:
        values = json.loads(str(raw_value))
    except json.JSONDecodeError:
        return set()
    return {str(value) for value in values if str(value).strip()}


def _extract_dataset_artifact_refs(manifest: dict[str, object]) -> list[str]:
    return [
        str(manifest[key])
        for key in ('strata_fit_ref', 'weight_fit_ref', 'domain_classifier_fit_ref')
        if str(manifest.get(key, '')).strip()
    ]
