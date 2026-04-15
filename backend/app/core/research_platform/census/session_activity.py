from __future__ import annotations


class StorageBackedSessionActivityProvider:
    def __init__(self, *, storage):
        self._storage = storage

    def is_active(self, inst_id: str, decision_ts: int) -> bool:
        query_ts = float(decision_ts)
        with self._storage._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT 1
                FROM research_collection_sessions
                WHERE inst_id = ?
                  AND started_at <= ?
                  AND (ended_at IS NULL OR ended_at >= ?)
                LIMIT 1
                """,
                (inst_id, query_ts, query_ts),
            )
            return cursor.fetchone() is not None
