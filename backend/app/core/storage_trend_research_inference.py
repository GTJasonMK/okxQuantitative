from __future__ import annotations

import json

from .storage_trend_research_schema import ensure_columns
from .trend_research.models import TrendInferenceSnapshot


INFERENCE_COLUMN_DEFS = (
    ("current_price", "REAL NOT NULL DEFAULT 0"),
    ("predicted_top_eta_seconds", "INTEGER DEFAULT NULL"),
    ("predicted_bottom_eta_seconds", "INTEGER DEFAULT NULL"),
    ("predicted_top_price", "REAL DEFAULT NULL"),
    ("predicted_bottom_price", "REAL DEFAULT NULL"),
    ("predicted_top_return", "REAL DEFAULT NULL"),
    ("predicted_bottom_return", "REAL DEFAULT NULL"),
    ("top_time_distribution", "TEXT NOT NULL DEFAULT '[]'"),
    ("bottom_time_distribution", "TEXT NOT NULL DEFAULT '[]'"),
)


def _snapshot_field(row, key: str, default=None):
    if isinstance(row, dict):
        return row.get(key, default)
    return getattr(row, key, default)


class StorageTrendResearchInferenceMixin:
    def _init_db(self):
        super()._init_db()
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS inference_snapshots (
                    inst_id TEXT NOT NULL,
                    second_bucket INTEGER NOT NULL,
                    trend_score REAL NOT NULL,
                    trend_state TEXT NOT NULL,
                    top_probability REAL NOT NULL,
                    bottom_probability REAL NOT NULL,
                    confidence REAL NOT NULL,
                    current_price REAL NOT NULL DEFAULT 0,
                    predicted_top_eta_seconds INTEGER DEFAULT NULL,
                    predicted_bottom_eta_seconds INTEGER DEFAULT NULL,
                    predicted_top_price REAL DEFAULT NULL,
                    predicted_bottom_price REAL DEFAULT NULL,
                    predicted_top_return REAL DEFAULT NULL,
                    predicted_bottom_return REAL DEFAULT NULL,
                    top_time_distribution TEXT NOT NULL DEFAULT '[]',
                    bottom_time_distribution TEXT NOT NULL DEFAULT '[]',
                    data_quality TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (inst_id, second_bucket)
                )
                """
            )
            ensure_columns(cursor, "inference_snapshots", INFERENCE_COLUMN_DEFS)

    def save_inference_snapshots(self, rows) -> int:
        if not rows:
            return 0
        with self._get_cursor() as cursor:
            for row in rows:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO inference_snapshots (
                        inst_id, second_bucket, trend_score, trend_state,
                        top_probability, bottom_probability, confidence,
                        current_price,
                        predicted_top_eta_seconds, predicted_bottom_eta_seconds,
                        predicted_top_price, predicted_bottom_price,
                        predicted_top_return, predicted_bottom_return,
                        top_time_distribution, bottom_time_distribution,
                        data_quality
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        str(_snapshot_field(row, "inst_id", "")),
                        int(_snapshot_field(row, "second_bucket", 0) or 0),
                        float(_snapshot_field(row, "trend_score", 0.0) or 0.0),
                        str(_snapshot_field(row, "trend_state", "range")),
                        float(_snapshot_field(row, "top_probability", 0.0) or 0.0),
                        float(_snapshot_field(row, "bottom_probability", 0.0) or 0.0),
                        float(_snapshot_field(row, "confidence", 0.0) or 0.0),
                        float(_snapshot_field(row, "current_price", 0.0) or 0.0),
                        _snapshot_field(row, "predicted_top_eta_seconds"),
                        _snapshot_field(row, "predicted_bottom_eta_seconds"),
                        _snapshot_field(row, "predicted_top_price"),
                        _snapshot_field(row, "predicted_bottom_price"),
                        _snapshot_field(row, "predicted_top_return"),
                        _snapshot_field(row, "predicted_bottom_return"),
                        _serialize_distribution(_snapshot_field(row, "top_time_distribution", ()) or ()),
                        _serialize_distribution(_snapshot_field(row, "bottom_time_distribution", ()) or ()),
                        str(_snapshot_field(row, "data_quality", "partial")),
                    ),
                )
        return len(rows)

    def list_inference_snapshots(
        self,
        limit: int = 100,
        inst_ids: list[str] | None = None,
    ) -> list[TrendInferenceSnapshot]:
        clauses = []
        params: list[object] = []
        if inst_ids:
            placeholders = ", ".join("?" for _ in inst_ids)
            clauses.append(f"inst_id IN ({placeholders})")
            params.extend(inst_ids)
        where_sql = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with self._get_cursor() as cursor:
            cursor.execute(
                f"""
                SELECT inst_id, second_bucket, trend_score, trend_state,
                       top_probability, bottom_probability, confidence, current_price,
                       predicted_top_eta_seconds, predicted_bottom_eta_seconds,
                       predicted_top_price, predicted_bottom_price,
                       predicted_top_return, predicted_bottom_return,
                       top_time_distribution, bottom_time_distribution,
                       data_quality
                FROM inference_snapshots
                {where_sql}
                ORDER BY second_bucket DESC, inst_id ASC
                LIMIT ?
                """,
                (*params, max(int(limit or 100), 1)),
            )
            rows = cursor.fetchall()
        return [_build_inference_snapshot(row) for row in rows]

    def list_latest_inference_snapshots(
        self,
        limit: int = 100,
        inst_ids: list[str] | None = None,
    ) -> list[TrendInferenceSnapshot]:
        clauses = []
        params: list[object] = []
        if inst_ids:
            placeholders = ", ".join("?" for _ in inst_ids)
            clauses.append(f"s.inst_id IN ({placeholders})")
            params.extend(inst_ids)
        where_sql = f"AND {' AND '.join(clauses)}" if clauses else ""
        with self._get_cursor() as cursor:
            cursor.execute(
                f"""
                SELECT s.inst_id, s.second_bucket, s.trend_score, s.trend_state,
                       s.top_probability, s.bottom_probability, s.confidence, s.current_price,
                       s.predicted_top_eta_seconds, s.predicted_bottom_eta_seconds,
                       s.predicted_top_price, s.predicted_bottom_price,
                       s.predicted_top_return, s.predicted_bottom_return,
                       s.top_time_distribution, s.bottom_time_distribution,
                       s.data_quality
                FROM inference_snapshots AS s
                WHERE s.second_bucket = (
                    SELECT MAX(i.second_bucket)
                    FROM inference_snapshots AS i
                    WHERE i.inst_id = s.inst_id
                )
                {where_sql}
                ORDER BY s.second_bucket DESC, s.inst_id ASC
                LIMIT ?
                """,
                (*params, max(int(limit or 100), 1)),
            )
            rows = cursor.fetchall()
        return [_build_inference_snapshot(row) for row in rows]


def _serialize_distribution(values) -> str:
    return json.dumps([float(value) for value in values], ensure_ascii=False)


def _deserialize_distribution(value) -> tuple[float, ...]:
    if not value:
        return ()
    return tuple(float(item) for item in json.loads(value))


def _build_inference_snapshot(row) -> TrendInferenceSnapshot:
    return TrendInferenceSnapshot(
        inst_id=row["inst_id"],
        second_bucket=int(row["second_bucket"]),
        trend_score=float(row["trend_score"]),
        trend_state=row["trend_state"],
        confidence=float(row["confidence"]),
        data_quality=row["data_quality"],
        current_price=float(row["current_price"]),
        predicted_top_eta_seconds=int(row["predicted_top_eta_seconds"]) if row["predicted_top_eta_seconds"] is not None else None,
        predicted_bottom_eta_seconds=int(row["predicted_bottom_eta_seconds"]) if row["predicted_bottom_eta_seconds"] is not None else None,
        predicted_top_price=float(row["predicted_top_price"]) if row["predicted_top_price"] is not None else None,
        predicted_bottom_price=float(row["predicted_bottom_price"]) if row["predicted_bottom_price"] is not None else None,
        predicted_top_return=float(row["predicted_top_return"]) if row["predicted_top_return"] is not None else None,
        predicted_bottom_return=float(row["predicted_bottom_return"]) if row["predicted_bottom_return"] is not None else None,
        top_time_distribution=_deserialize_distribution(row["top_time_distribution"]),
        bottom_time_distribution=_deserialize_distribution(row["bottom_time_distribution"]),
        top_probability=float(row["top_probability"]),
        bottom_probability=float(row["bottom_probability"]),
    )
