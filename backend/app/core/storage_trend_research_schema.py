from __future__ import annotations

from collections.abc import Iterable

from .trend_research.models import FactorScore, FeatureBar1s


FEATURE_BAR_COLUMN_DEFS = (
    ("bid_price", "REAL NOT NULL DEFAULT 0"),
    ("ask_price", "REAL NOT NULL DEFAULT 0"),
    ("bid_size", "REAL NOT NULL DEFAULT 0"),
    ("ask_size", "REAL NOT NULL DEFAULT 0"),
    ("buy_notional", "REAL NOT NULL DEFAULT 0"),
    ("sell_notional", "REAL NOT NULL DEFAULT 0"),
    ("buy_count", "INTEGER NOT NULL DEFAULT 0"),
    ("sell_count", "INTEGER NOT NULL DEFAULT 0"),
    ("max_trade_notional", "REAL NOT NULL DEFAULT 0"),
    ("buy_burst_count", "INTEGER NOT NULL DEFAULT 0"),
    ("sell_burst_count", "INTEGER NOT NULL DEFAULT 0"),
    ("buy_burst_notional", "REAL NOT NULL DEFAULT 0"),
    ("sell_burst_notional", "REAL NOT NULL DEFAULT 0"),
    ("open_price", "REAL NOT NULL DEFAULT 0"),
    ("high_price", "REAL NOT NULL DEFAULT 0"),
    ("low_price", "REAL NOT NULL DEFAULT 0"),
    ("close_price", "REAL NOT NULL DEFAULT 0"),
    ("microprice", "REAL NOT NULL DEFAULT 0"),
    ("basis_bps", "REAL NOT NULL DEFAULT 0"),
    ("open_interest", "REAL NOT NULL DEFAULT 0"),
    ("funding_rate", "REAL NOT NULL DEFAULT 0"),
    ("funding_delta", "REAL NOT NULL DEFAULT 0"),
    ("premium", "REAL NOT NULL DEFAULT 0"),
    ("book_level_count", "INTEGER NOT NULL DEFAULT 0"),
    ("multi_level_book_imbalance", "REAL NOT NULL DEFAULT 0"),
    ("book_slope", "REAL NOT NULL DEFAULT 0"),
)

FACTOR_SCORE_COLUMN_DEFS = (
    ("category", "TEXT NOT NULL DEFAULT ''"),
    ("tier", "INTEGER NOT NULL DEFAULT 0"),
    ("available", "INTEGER NOT NULL DEFAULT 1"),
    ("unavailable_reason", "TEXT NOT NULL DEFAULT ''"),
)

FEATURE_BAR_COLUMNS = (
    "inst_id",
    "second_bucket",
    "ts_exchange",
    "ts_local",
    "mid_price",
    "mark_price",
    "index_price",
    "spread_bps",
    "signed_trade_notional",
    "trade_count",
    "oi_delta",
    "basis_zscore",
    "data_quality",
    *(column_name for column_name, _ in FEATURE_BAR_COLUMN_DEFS),
)

FACTOR_SCORE_COLUMNS = (
    "inst_id",
    "factor_name",
    "spearman_ic",
    "stability_score",
    "redundancy_cluster",
    *(column_name for column_name, _ in FACTOR_SCORE_COLUMN_DEFS),
)


def ensure_columns(cursor, table_name: str, column_defs: Iterable[tuple[str, str]]) -> None:
    existing_columns = _read_existing_columns(cursor, table_name)
    for column_name, ddl in column_defs:
        if column_name in existing_columns:
            continue
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {ddl}")


def build_feature_bar(row) -> FeatureBar1s:
    return FeatureBar1s(
        inst_id=row["inst_id"],
        second_bucket=int(row["second_bucket"]),
        ts_exchange=float(row["ts_exchange"]),
        ts_local=float(row["ts_local"]),
        mid_price=float(row["mid_price"]),
        mark_price=float(row["mark_price"]),
        index_price=float(row["index_price"]),
        spread_bps=float(row["spread_bps"]),
        signed_trade_notional=float(row["signed_trade_notional"]),
        trade_count=int(row["trade_count"]),
        oi_delta=float(row["oi_delta"]),
        basis_zscore=float(row["basis_zscore"]),
        data_quality=row["data_quality"],
        bid_price=float(row["bid_price"]),
        ask_price=float(row["ask_price"]),
        bid_size=float(row["bid_size"]),
        ask_size=float(row["ask_size"]),
        buy_notional=float(row["buy_notional"]),
        sell_notional=float(row["sell_notional"]),
        buy_count=int(row["buy_count"]),
        sell_count=int(row["sell_count"]),
        max_trade_notional=float(row["max_trade_notional"]),
        buy_burst_count=int(row["buy_burst_count"]),
        sell_burst_count=int(row["sell_burst_count"]),
        buy_burst_notional=float(row["buy_burst_notional"]),
        sell_burst_notional=float(row["sell_burst_notional"]),
        open_price=float(row["open_price"]),
        high_price=float(row["high_price"]),
        low_price=float(row["low_price"]),
        close_price=float(row["close_price"]),
        microprice=float(row["microprice"]),
        basis_bps=float(row["basis_bps"]),
        open_interest=float(row["open_interest"]),
        funding_rate=float(row["funding_rate"]),
        funding_delta=float(row["funding_delta"]),
        premium=float(row["premium"]),
        book_level_count=int(row["book_level_count"]),
        multi_level_book_imbalance=float(row["multi_level_book_imbalance"]),
        book_slope=float(row["book_slope"]),
    )


def feature_bar_values(bar: FeatureBar1s) -> tuple:
    return tuple(getattr(bar, column_name) for column_name in FEATURE_BAR_COLUMNS)


def build_factor_score(row) -> FactorScore:
    return FactorScore(
        inst_id=row["inst_id"],
        factor_name=row["factor_name"],
        spearman_ic=float(row["spearman_ic"]) if row["spearman_ic"] is not None else None,
        stability_score=float(row["stability_score"]) if row["stability_score"] is not None else None,
        redundancy_cluster=row["redundancy_cluster"],
        category=row["category"],
        tier=int(row["tier"]),
        available=bool(row["available"]),
        unavailable_reason=row["unavailable_reason"],
    )


def factor_score_values(score: FactorScore) -> tuple:
    return tuple(getattr(score, column_name) for column_name in FACTOR_SCORE_COLUMNS)


def _read_existing_columns(cursor, table_name: str) -> set[str]:
    cursor.execute(f"PRAGMA table_info({table_name})")
    return {
        row["name"] if hasattr(row, "keys") else row[1]
        for row in cursor.fetchall()
    }
