from __future__ import annotations

from typing import List

from .storage_trend_research_schema import (
    FACTOR_SCORE_COLUMNS,
    FACTOR_SCORE_COLUMN_DEFS,
    FEATURE_BAR_COLUMNS,
    FEATURE_BAR_COLUMN_DEFS,
    build_factor_score,
    build_feature_bar,
    ensure_columns,
    factor_score_values,
    feature_bar_values,
)
from .storage_trend_research_inference import StorageTrendResearchInferenceMixin
from .trend_research.models import FactorScore, FeatureBar1s, SwingLabel


class StorageTrendResearchMixin(StorageTrendResearchInferenceMixin):
    """趋势研究链路的本地存储能力。"""

    def _init_db(self):
        super()._init_db()

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS feature_bars_1s (
                    inst_id TEXT NOT NULL,
                    second_bucket INTEGER NOT NULL,
                    ts_exchange REAL NOT NULL,
                    ts_local REAL NOT NULL,
                    mid_price REAL NOT NULL,
                    mark_price REAL NOT NULL,
                    index_price REAL NOT NULL,
                    spread_bps REAL NOT NULL,
                    signed_trade_notional REAL NOT NULL,
                    trade_count INTEGER NOT NULL,
                    oi_delta REAL NOT NULL,
                    basis_zscore REAL NOT NULL,
                    data_quality TEXT NOT NULL,
                    bid_price REAL NOT NULL DEFAULT 0,
                    ask_price REAL NOT NULL DEFAULT 0,
                    bid_size REAL NOT NULL DEFAULT 0,
                    ask_size REAL NOT NULL DEFAULT 0,
                    buy_notional REAL NOT NULL DEFAULT 0,
                    sell_notional REAL NOT NULL DEFAULT 0,
                    buy_count INTEGER NOT NULL DEFAULT 0,
                    sell_count INTEGER NOT NULL DEFAULT 0,
                    max_trade_notional REAL NOT NULL DEFAULT 0,
                    buy_burst_count INTEGER NOT NULL DEFAULT 0,
                    sell_burst_count INTEGER NOT NULL DEFAULT 0,
                    buy_burst_notional REAL NOT NULL DEFAULT 0,
                    sell_burst_notional REAL NOT NULL DEFAULT 0,
                    open_price REAL NOT NULL DEFAULT 0,
                    high_price REAL NOT NULL DEFAULT 0,
                    low_price REAL NOT NULL DEFAULT 0,
                    close_price REAL NOT NULL DEFAULT 0,
                    microprice REAL NOT NULL DEFAULT 0,
                    basis_bps REAL NOT NULL DEFAULT 0,
                    open_interest REAL NOT NULL DEFAULT 0,
                    funding_rate REAL NOT NULL DEFAULT 0,
                    funding_delta REAL NOT NULL DEFAULT 0,
                    premium REAL NOT NULL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (inst_id, second_bucket)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS swing_labels (
                    inst_id TEXT NOT NULL,
                    second_bucket INTEGER NOT NULL,
                    trend_state TEXT NOT NULL,
                    swing_top_confirmed INTEGER NOT NULL,
                    swing_bottom_confirmed INTEGER NOT NULL,
                    time_to_top INTEGER NOT NULL,
                    time_to_bottom INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (inst_id, second_bucket)
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS factor_scores (
                    inst_id TEXT NOT NULL,
                    factor_name TEXT NOT NULL,
                    spearman_ic REAL NOT NULL,
                    stability_score REAL NOT NULL,
                    redundancy_cluster TEXT NOT NULL,
                    category TEXT NOT NULL DEFAULT '',
                    tier INTEGER NOT NULL DEFAULT 0,
                    available INTEGER NOT NULL DEFAULT 1,
                    unavailable_reason TEXT NOT NULL DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (inst_id, factor_name)
                )
                """
            )
            ensure_columns(cursor, "feature_bars_1s", FEATURE_BAR_COLUMN_DEFS)
            ensure_columns(cursor, "factor_scores", FACTOR_SCORE_COLUMN_DEFS)

    def save_feature_bars_1s(self, bars: List[FeatureBar1s]) -> int:
        if not bars:
            return 0

        insert_columns = ", ".join(FEATURE_BAR_COLUMNS)
        placeholders = ", ".join("?" for _ in FEATURE_BAR_COLUMNS)
        with self._get_cursor() as cursor:
            for bar in bars:
                cursor.execute(
                    f"INSERT OR REPLACE INTO feature_bars_1s ({insert_columns}) VALUES ({placeholders})",
                    feature_bar_values(bar),
                )
        return len(bars)

    def list_feature_bars_1s(self, inst_id: str, limit: int = 100) -> List[FeatureBar1s]:
        select_columns = ", ".join(FEATURE_BAR_COLUMNS)
        with self._get_cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {select_columns}
                FROM feature_bars_1s
                WHERE inst_id = ?
                ORDER BY second_bucket DESC
                LIMIT ?
                """,
                (inst_id, max(int(limit or 100), 1)),
            )
            rows = cursor.fetchall()

        return [build_feature_bar(row) for row in rows]

    def replace_swing_labels(self, inst_id: str, labels: List[SwingLabel]) -> int:
        with self._get_cursor() as cursor:
            cursor.execute("DELETE FROM swing_labels WHERE inst_id = ?", (inst_id,))
            for label in labels:
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO swing_labels (
                        inst_id, second_bucket, trend_state,
                        swing_top_confirmed, swing_bottom_confirmed,
                        time_to_top, time_to_bottom
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        label.inst_id,
                        label.second_bucket,
                        label.trend_state,
                        int(label.swing_top_confirmed),
                        int(label.swing_bottom_confirmed),
                        label.time_to_top,
                        label.time_to_bottom,
                    ),
                )
        return len(labels)

    def list_swing_labels(self, inst_id: str, limit: int = 100) -> List[SwingLabel]:
        with self._get_cursor() as cursor:
            cursor.execute(
                """
                SELECT inst_id, second_bucket, trend_state,
                       swing_top_confirmed, swing_bottom_confirmed,
                       time_to_top, time_to_bottom
                FROM swing_labels
                WHERE inst_id = ?
                ORDER BY second_bucket DESC
                LIMIT ?
                """,
                (inst_id, max(int(limit or 100), 1)),
            )
            rows = cursor.fetchall()

        return [
            SwingLabel(
                inst_id=row["inst_id"],
                second_bucket=int(row["second_bucket"]),
                trend_state=row["trend_state"],
                swing_top_confirmed=bool(row["swing_top_confirmed"]),
                swing_bottom_confirmed=bool(row["swing_bottom_confirmed"]),
                time_to_top=int(row["time_to_top"]),
                time_to_bottom=int(row["time_to_bottom"]),
            )
            for row in rows
        ]

    def replace_factor_scores(self, inst_id: str, scores: List[FactorScore]) -> int:
        insert_columns = ", ".join(FACTOR_SCORE_COLUMNS)
        placeholders = ", ".join("?" for _ in FACTOR_SCORE_COLUMNS)
        with self._get_cursor() as cursor:
            cursor.execute("DELETE FROM factor_scores WHERE inst_id = ?", (inst_id,))
            for score in scores:
                cursor.execute(
                    f"INSERT OR REPLACE INTO factor_scores ({insert_columns}) VALUES ({placeholders})",
                    factor_score_values(score),
                )
        return len(scores)

    def list_factor_scores(self, inst_id: str, limit: int = 20) -> List[FactorScore]:
        select_columns = ", ".join(FACTOR_SCORE_COLUMNS)
        with self._get_cursor() as cursor:
            cursor.execute(
                f"""
                SELECT {select_columns}
                FROM factor_scores
                WHERE inst_id = ?
                ORDER BY stability_score DESC, factor_name ASC
                LIMIT ?
                """,
                (inst_id, max(int(limit or 20), 1)),
            )
            rows = cursor.fetchall()

        return [build_factor_score(row) for row in rows]
