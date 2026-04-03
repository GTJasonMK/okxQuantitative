from __future__ import annotations

import time
from typing import Any, List, Optional

from .data_fetcher import MarketTrade, Ticker


class StorageMarketStreamsMixin:
    """实时行情与逐笔成交的本地存储能力。"""

    def _init_db(self):
        """在基础表之外补充实时行情相关表。"""
        super()._init_db()

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS market_ticker_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inst_id TEXT NOT NULL,
                    inst_type TEXT NOT NULL DEFAULT 'SPOT',
                    last REAL NOT NULL,
                    last_sz REAL DEFAULT 0,
                    ask_px REAL DEFAULT 0,
                    ask_sz REAL DEFAULT 0,
                    bid_px REAL DEFAULT 0,
                    bid_sz REAL DEFAULT 0,
                    open_24h REAL DEFAULT 0,
                    high_24h REAL DEFAULT 0,
                    low_24h REAL DEFAULT 0,
                    vol_24h REAL DEFAULT 0,
                    vol_ccy_24h REAL DEFAULT 0,
                    timestamp INTEGER NOT NULL,
                    source TEXT NOT NULL DEFAULT 'rest',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(inst_id, inst_type, timestamp, source)
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_market_ticker_inst_time
                ON market_ticker_snapshots(inst_id, inst_type, timestamp DESC)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_market_ticker_type_time
                ON market_ticker_snapshots(inst_type, timestamp DESC)
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS market_recent_trades (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inst_id TEXT NOT NULL,
                    inst_type TEXT NOT NULL DEFAULT 'SPOT',
                    trade_id TEXT NOT NULL DEFAULT '',
                    price REAL NOT NULL,
                    size REAL NOT NULL,
                    side TEXT NOT NULL DEFAULT '',
                    timestamp INTEGER NOT NULL,
                    source TEXT NOT NULL DEFAULT 'rest',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(inst_id, trade_id, timestamp)
                )
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_market_trades_inst_time
                ON market_recent_trades(inst_id, inst_type, timestamp DESC)
                """
            )
            cursor.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_market_trades_type_time
                ON market_recent_trades(inst_type, timestamp DESC)
                """
            )

    def _coerce_inst_type(self, inst_type: Optional[str], inst_id: str = "") -> str:
        """规范化交易类型，缺省时尽量从交易对推断。"""
        normalized = str(inst_type or "").upper().strip()
        if normalized in {"SPOT", "SWAP", "FUTURES", "OPTION"}:
            return normalized
        if inst_id.endswith("-SWAP"):
            return "SWAP"
        return "SPOT"

    def _to_ticker_model(self, row: Any) -> Ticker:
        return Ticker(
            inst_id=row["inst_id"],
            last=float(row["last"]),
            last_sz=float(row["last_sz"]),
            ask_px=float(row["ask_px"]),
            ask_sz=float(row["ask_sz"]),
            bid_px=float(row["bid_px"]),
            bid_sz=float(row["bid_sz"]),
            open_24h=float(row["open_24h"]),
            high_24h=float(row["high_24h"]),
            low_24h=float(row["low_24h"]),
            vol_24h=float(row["vol_24h"]),
            vol_ccy_24h=float(row["vol_ccy_24h"]),
            timestamp=int(row["timestamp"]),
        )

    def _to_trade_model(self, row: Any) -> MarketTrade:
        return MarketTrade(
            inst_id=row["inst_id"],
            trade_id=row["trade_id"],
            price=float(row["price"]),
            size=float(row["size"]),
            side=row["side"],
            timestamp=int(row["timestamp"]),
        )

    def save_ticker_snapshot(
        self,
        ticker: Any,
        inst_type: Optional[str] = None,
        source: str = "rest",
    ) -> bool:
        """保存单条实时行情快照。"""
        if not ticker or not getattr(ticker, "inst_id", ""):
            return False
        if self._is_write_blocked_for_inst_id(getattr(ticker, "inst_id", "")):
            return False

        resolved_inst_type = self._coerce_inst_type(
            inst_type or getattr(ticker, "inst_type", ""),
            getattr(ticker, "inst_id", ""),
        )

        with self._get_cursor() as cursor:
            cursor.execute(
                """
                INSERT OR REPLACE INTO market_ticker_snapshots (
                    inst_id, inst_type, last, last_sz,
                    ask_px, ask_sz, bid_px, bid_sz,
                    open_24h, high_24h, low_24h,
                    vol_24h, vol_ccy_24h,
                    timestamp, source
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ticker.inst_id,
                    resolved_inst_type,
                    float(getattr(ticker, "last", 0) or 0),
                    float(getattr(ticker, "last_sz", 0) or 0),
                    float(getattr(ticker, "ask_px", 0) or 0),
                    float(getattr(ticker, "ask_sz", 0) or 0),
                    float(getattr(ticker, "bid_px", 0) or 0),
                    float(getattr(ticker, "bid_sz", 0) or 0),
                    float(getattr(ticker, "open_24h", 0) or 0),
                    float(getattr(ticker, "high_24h", 0) or 0),
                    float(getattr(ticker, "low_24h", 0) or 0),
                    float(getattr(ticker, "vol_24h", 0) or 0),
                    float(getattr(ticker, "vol_ccy_24h", 0) or 0),
                    int(getattr(ticker, "timestamp", 0) or int(time.time() * 1000)),
                    source,
                ),
            )
        return True

    def save_ticker_snapshots(
        self,
        tickers: List[Any],
        inst_type: Optional[str] = None,
        source: str = "rest",
    ) -> int:
        """批量保存实时行情快照（单事务，避免逐条 commit）。"""
        if not tickers:
            return 0

        saved_count = 0
        with self._get_cursor() as cursor:
            for ticker in tickers:
                if not ticker or not getattr(ticker, "inst_id", ""):
                    continue
                ticker_inst_id = getattr(ticker, "inst_id", "")
                if self._is_write_blocked_for_inst_id(ticker_inst_id):
                    continue

                resolved_inst_type = self._coerce_inst_type(
                    inst_type or getattr(ticker, "inst_type", ""),
                    ticker_inst_id,
                )
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO market_ticker_snapshots (
                        inst_id, inst_type, last, last_sz,
                        ask_px, ask_sz, bid_px, bid_sz,
                        open_24h, high_24h, low_24h,
                        vol_24h, vol_ccy_24h,
                        timestamp, source
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        ticker_inst_id,
                        resolved_inst_type,
                        float(getattr(ticker, "last", 0) or 0),
                        float(getattr(ticker, "last_sz", 0) or 0),
                        float(getattr(ticker, "ask_px", 0) or 0),
                        float(getattr(ticker, "ask_sz", 0) or 0),
                        float(getattr(ticker, "bid_px", 0) or 0),
                        float(getattr(ticker, "bid_sz", 0) or 0),
                        float(getattr(ticker, "open_24h", 0) or 0),
                        float(getattr(ticker, "high_24h", 0) or 0),
                        float(getattr(ticker, "low_24h", 0) or 0),
                        float(getattr(ticker, "vol_24h", 0) or 0),
                        float(getattr(ticker, "vol_ccy_24h", 0) or 0),
                        int(getattr(ticker, "timestamp", 0) or int(time.time() * 1000)),
                        source,
                    ),
                )
                saved_count += 1
        return saved_count

    def get_latest_ticker(
        self,
        inst_id: str,
        *,
        inst_type: str = "SPOT",
        max_age_ms: Optional[int] = None,
    ) -> Optional[Ticker]:
        """读取指定交易对最新快照。"""
        query = """
            SELECT inst_id, last, last_sz, ask_px, ask_sz, bid_px, bid_sz,
                   open_24h, high_24h, low_24h, vol_24h, vol_ccy_24h, timestamp
            FROM market_ticker_snapshots
            WHERE inst_id = ? AND inst_type = ?
        """
        params: List[Any] = [inst_id, self._coerce_inst_type(inst_type, inst_id)]

        if max_age_ms is not None:
            query += " AND timestamp >= ?"
            params.append(int(time.time() * 1000) - max_age_ms)

        query += " ORDER BY timestamp DESC, id DESC LIMIT 1"

        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            row = cursor.fetchone()
            return self._to_ticker_model(row) if row else None

    def get_latest_tickers(
        self,
        *,
        inst_type: str = "SPOT",
        max_age_ms: Optional[int] = None,
        limit: Optional[int] = None,
    ) -> List[Ticker]:
        """读取某交易类型下每个交易对的最新快照。"""
        query = """
            SELECT inst_id, last, last_sz, ask_px, ask_sz, bid_px, bid_sz,
                   open_24h, high_24h, low_24h, vol_24h, vol_ccy_24h, timestamp
            FROM market_ticker_snapshots
            WHERE inst_type = ?
        """
        params: List[Any] = [self._coerce_inst_type(inst_type)]

        if max_age_ms is not None:
            query += " AND timestamp >= ?"
            params.append(int(time.time() * 1000) - max_age_ms)

        query += " ORDER BY inst_id ASC, timestamp DESC, id DESC"

        tickers: List[Ticker] = []
        seen_inst_ids = set()
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                inst_id = row["inst_id"]
                if inst_id in seen_inst_ids:
                    continue
                seen_inst_ids.add(inst_id)
                tickers.append(self._to_ticker_model(row))
                if limit and len(tickers) >= limit:
                    break
        return tickers

    def save_recent_trades(
        self,
        trades: List[MarketTrade],
        *,
        inst_type: str = "SPOT",
        source: str = "rest",
    ) -> int:
        """批量保存最新逐笔成交。"""
        if not trades:
            return 0

        saved_count = 0
        with self._get_cursor() as cursor:
            for trade in trades:
                if not trade.inst_id:
                    continue
                if self._is_write_blocked_for_inst_id(trade.inst_id):
                    continue
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO market_recent_trades (
                        inst_id, inst_type, trade_id, price, size, side, timestamp, source
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        trade.inst_id,
                        self._coerce_inst_type(inst_type, trade.inst_id),
                        str(trade.trade_id or ""),
                        float(trade.price),
                        float(trade.size),
                        str(trade.side or ""),
                        int(trade.timestamp),
                        source,
                    ),
                )
                saved_count += 1
        return saved_count

    def get_recent_trades(
        self,
        inst_id: str,
        *,
        limit: int = 30,
        inst_type: str = "SPOT",
        max_age_ms: Optional[int] = None,
    ) -> List[MarketTrade]:
        """读取指定交易对的本地最新逐笔成交。"""
        query = """
            SELECT inst_id, trade_id, price, size, side, timestamp
            FROM market_recent_trades
            WHERE inst_id = ? AND inst_type = ?
        """
        params: List[Any] = [inst_id, self._coerce_inst_type(inst_type, inst_id)]

        if max_age_ms is not None:
            query += " AND timestamp >= ?"
            params.append(int(time.time() * 1000) - max_age_ms)

        query += " ORDER BY timestamp DESC, id DESC LIMIT ?"
        params.append(max(int(limit), 1))

        trades: List[MarketTrade] = []
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                trades.append(self._to_trade_model(row))
        return trades

    def purge_stale_market_streams(self, *, max_age_hours: int = 48) -> dict[str, int]:
        """清理过期的 ticker 快照和逐笔成交，防止表无限膨胀。

        Args:
            max_age_hours: 保留最近多少小时的数据，默认 48 小时

        Returns:
            {"ticker_snapshots": 删除条数, "recent_trades": 删除条数}
        """
        cutoff_ms = int(time.time() * 1000) - max_age_hours * 3600 * 1000
        deleted = {"ticker_snapshots": 0, "recent_trades": 0}

        with self._get_cursor() as cursor:
            cursor.execute(
                "DELETE FROM market_ticker_snapshots WHERE timestamp < ?",
                (cutoff_ms,),
            )
            deleted["ticker_snapshots"] = max(cursor.rowcount, 0)

            cursor.execute(
                "DELETE FROM market_recent_trades WHERE timestamp < ?",
                (cutoff_ms,),
            )
            deleted["recent_trades"] = max(cursor.rowcount, 0)

        return deleted
