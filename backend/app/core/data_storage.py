# 数据存储模块
# 负责K线数据的本地持久化存储和查询

import sqlite3
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager
import threading
from decimal import Decimal, ROUND_DOWN

from .data_fetcher import Candle, InstType


class DataStorage:
    """
    数据存储器
    使用SQLite存储K线数据，支持多线程访问
    """

    def __init__(self, db_path: str | Path):
        """
        初始化数据存储器

        Args:
            db_path: 数据库文件路径
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._local = threading.local()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接"""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False
            )
            self._local.connection.row_factory = sqlite3.Row
        return self._local.connection

    @contextmanager
    def _get_cursor(self):
        """获取数据库游标的上下文管理器"""
        conn = self._get_connection()
        cursor = conn.cursor()
        try:
            yield cursor
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            cursor.close()

    def _init_db(self):
        """初始化数据库表结构"""
        with self._get_cursor() as cursor:
            # K线数据表
            # 唯一键包含 inst_type，避免不同交易类型（SPOT/SWAP等）的同名交易对数据互相覆盖
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS candles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inst_id TEXT NOT NULL,
                    inst_type TEXT NOT NULL DEFAULT 'SPOT',
                    timeframe TEXT NOT NULL,
                    timestamp INTEGER NOT NULL,
                    open REAL NOT NULL,
                    high REAL NOT NULL,
                    low REAL NOT NULL,
                    close REAL NOT NULL,
                    volume REAL NOT NULL,
                    volume_ccy REAL DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(inst_id, inst_type, timeframe, timestamp)
                )
            """)

            # 创建索引加速查询（包含 inst_type）
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_candles_query
                ON candles(inst_id, inst_type, timeframe, timestamp)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_candles_time
                ON candles(timestamp)
            """)

            # 数据同步记录表（记录每个交易对的数据同步状态）
            # 唯一键包含 inst_type，避免不同交易类型的同步记录互相覆盖
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sync_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    inst_id TEXT NOT NULL,
                    inst_type TEXT NOT NULL DEFAULT 'SPOT',
                    timeframe TEXT NOT NULL,
                    last_sync_time TIMESTAMP,
                    oldest_timestamp INTEGER,
                    newest_timestamp INTEGER,
                    candle_count INTEGER DEFAULT 0,
                    UNIQUE(inst_id, inst_type, timeframe)
                )
            """)

            # 本地成交记录表（用于计算成本基础）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS local_fills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT,
                    inst_id TEXT NOT NULL,
                    ccy TEXT NOT NULL,
                    side TEXT NOT NULL,
                    fill_px TEXT NOT NULL,
                    fill_sz TEXT NOT NULL,
                    fee TEXT DEFAULT '0',
                    fee_ccy TEXT,
                    ts INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    source TEXT DEFAULT 'api',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(trade_id, mode)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_fills_ccy_mode
                ON local_fills(ccy, mode)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_fills_ts
                ON local_fills(ts)
            """)

            # 成本基础表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cost_basis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ccy TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    avg_cost TEXT NOT NULL,
                    total_qty TEXT NOT NULL,
                    total_cost TEXT NOT NULL,
                    total_fee TEXT NOT NULL DEFAULT '0',
                    total_buy_cost TEXT NOT NULL DEFAULT '0',
                    total_sell_revenue TEXT NOT NULL DEFAULT '0',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ccy, mode)
                )
            """)

            # 数据库迁移：给已有的cost_basis表添加新列
            try:
                cursor.execute("ALTER TABLE cost_basis ADD COLUMN total_fee TEXT NOT NULL DEFAULT '0'")
            except Exception:
                pass  # 列已存在则忽略
            try:
                cursor.execute("ALTER TABLE cost_basis ADD COLUMN total_buy_cost TEXT NOT NULL DEFAULT '0'")
            except Exception:
                pass
            try:
                cursor.execute("ALTER TABLE cost_basis ADD COLUMN total_sell_revenue TEXT NOT NULL DEFAULT '0'")
            except Exception:
                pass

            # 回测结果表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backtest_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    timeframe TEXT NOT NULL,
                    days INTEGER NOT NULL,
                    start_time TEXT,
                    end_time TEXT,
                    initial_capital REAL NOT NULL,
                    final_capital REAL NOT NULL,
                    total_return REAL,
                    annual_return REAL,
                    max_drawdown REAL,
                    sharpe_ratio REAL,
                    sortino_ratio REAL,
                    calmar_ratio REAL,
                    win_rate REAL,
                    profit_factor REAL,
                    total_trades INTEGER,
                    winning_trades INTEGER,
                    losing_trades INTEGER,
                    avg_profit REAL,
                    avg_loss REAL,
                    largest_profit REAL,
                    largest_loss REAL,
                    total_commission REAL,
                    params_json TEXT,
                    detail_json TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_backtest_strategy
                ON backtest_results(strategy_id, symbol)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_backtest_time
                ON backtest_results(created_at)
            """)

            # 实时交易订单记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS live_order_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT,
                    inst_id TEXT NOT NULL,
                    side TEXT NOT NULL,
                    size TEXT NOT NULL,
                    price TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    success INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT DEFAULT '',
                    strategy_id TEXT,
                    strategy_name TEXT,
                    ts TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_live_orders_time
                ON live_order_records(ts)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_live_orders_strategy
                ON live_order_records(strategy_id)
            """)

    def save_candles(
        self,
        inst_id: str,
        timeframe: str,
        candles: List[Candle],
        inst_type: str = "SPOT"
    ) -> int:
        """
        保存K线数据

        Args:
            inst_id: 交易对
            timeframe: 时间周期
            candles: K线数据列表
            inst_type: 交易类型

        Returns:
            成功保存的数量
        """
        if not candles:
            return 0

        saved_count = 0
        with self._get_cursor() as cursor:
            for candle in candles:
                try:
                    cursor.execute("""
                        INSERT OR REPLACE INTO candles
                        (inst_id, inst_type, timeframe, timestamp, open, high, low, close, volume, volume_ccy)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """, (
                        inst_id,
                        inst_type,
                        timeframe,
                        candle.timestamp,
                        candle.open,
                        candle.high,
                        candle.low,
                        candle.close,
                        candle.volume,
                        candle.volume_ccy,
                    ))
                    saved_count += 1
                except sqlite3.Error as e:
                    print(f"保存K线数据失败: {e}")
                    continue

            # 更新同步记录
            if saved_count > 0:
                self._update_sync_record(cursor, inst_id, timeframe, inst_type)

        return saved_count

    def _update_sync_record(
        self,
        cursor: sqlite3.Cursor,
        inst_id: str,
        timeframe: str,
        inst_type: str
    ):
        """更新同步记录"""
        # 查询时也需要过滤 inst_type，确保统计数据准确
        cursor.execute("""
            INSERT OR REPLACE INTO sync_records
            (inst_id, inst_type, timeframe, last_sync_time, oldest_timestamp, newest_timestamp, candle_count)
            SELECT
                ?, ?, ?, CURRENT_TIMESTAMP,
                MIN(timestamp), MAX(timestamp), COUNT(*)
            FROM candles
            WHERE inst_id = ? AND inst_type = ? AND timeframe = ?
        """, (inst_id, inst_type, timeframe, inst_id, inst_type, timeframe))

    def get_candles(
        self,
        inst_id: str,
        timeframe: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: Optional[int] = None,
        inst_type: str = "SPOT",
    ) -> List[Candle]:
        """
        查询K线数据

        Args:
            inst_id: 交易对
            timeframe: 时间周期
            start_time: 开始时间
            end_time: 结束时间
            limit: 返回数量限制
            inst_type: 交易类型（SPOT/SWAP等）

        Returns:
            K线数据列表，按时间正序排列
        """
        query = """
            SELECT timestamp, open, high, low, close, volume, volume_ccy
            FROM candles
            WHERE inst_id = ? AND inst_type = ? AND timeframe = ?
        """
        params: List[Any] = [inst_id, inst_type, timeframe]

        if start_time:
            query += " AND timestamp >= ?"
            params.append(int(start_time.timestamp() * 1000))

        if end_time:
            query += " AND timestamp <= ?"
            params.append(int(end_time.timestamp() * 1000))

        # 约定：返回值按时间正序排列
        # - 指定 start_time（无 end_time）时，返回从 start_time 开始的正序数据
        # - 仅指定 end_time（无 start_time）且设置 limit 时，通常期望“取 end_time 之前最近 N 根”
        #   因此先按倒序取 limit，再在内存中反转为正序
        order_desc = bool(end_time and not start_time and limit)
        query += " ORDER BY timestamp DESC" if order_desc else " ORDER BY timestamp ASC"

        if limit:
            query += " LIMIT ?"
            params.append(limit)

        candles = []
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                candle = Candle(
                    timestamp=row["timestamp"],
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"],
                    volume_ccy=row["volume_ccy"],
                )
                candles.append(candle)

        # 如果按倒序取数，需要反转回正序
        if order_desc:
            candles.reverse()
        return candles

    def get_latest_candles(
        self,
        inst_id: str,
        timeframe: str,
        count: int = 100,
        inst_type: str = "SPOT"
    ) -> List[Candle]:
        """
        获取最新的N条K线数据

        Args:
            inst_id: 交易对
            timeframe: 时间周期
            count: 数量
            inst_type: 交易类型（SPOT/SWAP等）

        Returns:
            K线数据列表，按时间正序排列
        """
        query = """
            SELECT timestamp, open, high, low, close, volume, volume_ccy
            FROM candles
            WHERE inst_id = ? AND inst_type = ? AND timeframe = ?
            ORDER BY timestamp DESC
            LIMIT ?
        """

        candles = []
        with self._get_cursor() as cursor:
            cursor.execute(query, (inst_id, inst_type, timeframe, count))
            for row in cursor.fetchall():
                candle = Candle(
                    timestamp=row["timestamp"],
                    open=row["open"],
                    high=row["high"],
                    low=row["low"],
                    close=row["close"],
                    volume=row["volume"],
                    volume_ccy=row["volume_ccy"],
                )
                candles.append(candle)

        # 返回正序
        candles.reverse()
        return candles

    def get_candle_range(
        self,
        inst_id: str,
        timeframe: str,
        inst_type: str = "SPOT"
    ) -> Optional[Tuple[int, int, int]]:
        """
        获取K线数据的时间范围

        Args:
            inst_id: 交易对
            timeframe: 时间周期
            inst_type: 交易类型（SPOT/SWAP等）

        Returns:
            (最早时间戳, 最新时间戳, 数据条数) 或 None
        """
        query = """
            SELECT MIN(timestamp) as oldest, MAX(timestamp) as newest, COUNT(*) as count
            FROM candles
            WHERE inst_id = ? AND inst_type = ? AND timeframe = ?
        """

        with self._get_cursor() as cursor:
            cursor.execute(query, (inst_id, inst_type, timeframe))
            row = cursor.fetchone()
            if row and row["count"] > 0:
                return (row["oldest"], row["newest"], row["count"])
        return None

    def get_sync_status(self) -> List[Dict[str, Any]]:
        """
        获取所有交易对的同步状态

        Returns:
            同步状态列表
        """
        query = """
            SELECT inst_id, inst_type, timeframe, last_sync_time,
                   oldest_timestamp, newest_timestamp, candle_count
            FROM sync_records
            ORDER BY inst_id, timeframe
        """

        records = []
        with self._get_cursor() as cursor:
            cursor.execute(query)
            for row in cursor.fetchall():
                records.append({
                    "inst_id": row["inst_id"],
                    "inst_type": row["inst_type"],
                    "timeframe": row["timeframe"],
                    "last_sync_time": row["last_sync_time"],
                    "oldest_time": datetime.fromtimestamp(row["oldest_timestamp"] / 1000).isoformat() if row["oldest_timestamp"] else None,
                    "newest_time": datetime.fromtimestamp(row["newest_timestamp"] / 1000).isoformat() if row["newest_timestamp"] else None,
                    "candle_count": row["candle_count"],
                })
        return records

    def delete_candles(
        self,
        inst_id: str,
        timeframe: Optional[str] = None,
        before_time: Optional[datetime] = None,
        inst_type: str = "SPOT"
    ) -> int:
        """
        删除K线数据

        Args:
            inst_id: 交易对
            timeframe: 时间周期，不指定则删除所有周期
            before_time: 删除此时间之前的数据
            inst_type: 交易类型（SPOT/SWAP等）

        Returns:
            删除的数量
        """
        query = "DELETE FROM candles WHERE inst_id = ? AND inst_type = ?"
        params: List[Any] = [inst_id, inst_type]

        if timeframe:
            query += " AND timeframe = ?"
            params.append(timeframe)

        if before_time:
            query += " AND timestamp < ?"
            params.append(int(before_time.timestamp() * 1000))

        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            deleted_count = cursor.rowcount

            # 更新同步记录
            if timeframe:
                self._update_sync_record(cursor, inst_id, timeframe, inst_type)

        return deleted_count

    def get_available_symbols(self) -> List[Dict[str, Any]]:
        """
        获取已有数据的交易对列表

        Returns:
            交易对信息列表
        """
        query = """
            SELECT DISTINCT inst_id, inst_type,
                   GROUP_CONCAT(DISTINCT timeframe) as timeframes
            FROM candles
            GROUP BY inst_id, inst_type
            ORDER BY inst_id
        """

        symbols = []
        with self._get_cursor() as cursor:
            cursor.execute(query)
            for row in cursor.fetchall():
                symbols.append({
                    "inst_id": row["inst_id"],
                    "inst_type": row["inst_type"],
                    "timeframes": row["timeframes"].split(",") if row["timeframes"] else [],
                })
        return symbols

    # ==================== 成交记录和成本基础方法 ====================

    def save_fill(
        self,
        trade_id: str,
        inst_id: str,
        side: str,
        fill_px: float,
        fill_sz: float,
        ts: int,
        mode: str,
        fee: float = 0,
        fee_ccy: str = "",
        source: str = "api"
    ) -> bool:
        """
        保存单条成交记录

        Args:
            trade_id: 成交ID（用于去重）
            inst_id: 交易对，如 BTC-USDT
            side: buy/sell
            fill_px: 成交价格
            fill_sz: 成交数量
            ts: 成交时间戳（毫秒）
            mode: simulated/live
            fee: 手续费
            fee_ccy: 手续费币种
            source: 数据来源 api/manual

        Returns:
            是否成功保存（重复记录返回False）
        """
        # 从交易对中提取币种（如 BTC-USDT -> BTC）
        ccy = inst_id.split("-")[0] if "-" in inst_id else inst_id

        query = """
            INSERT OR IGNORE INTO local_fills
            (trade_id, inst_id, ccy, side, fill_px, fill_sz, fee, fee_ccy, ts, mode, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        with self._get_cursor() as cursor:
            cursor.execute(query, (
                trade_id, inst_id, ccy, side, fill_px, fill_sz,
                fee, fee_ccy, ts, mode, source
            ))
            return cursor.rowcount > 0

    def save_fills_batch(self, fills: List[Dict[str, Any]], mode: str) -> int:
        """
        批量保存成交记录

        Args:
            fills: 成交记录列表
            mode: simulated/live

        Returns:
            新增记录数量
        """
        query = """
            INSERT OR IGNORE INTO local_fills
            (trade_id, inst_id, ccy, side, fill_px, fill_sz, fee, fee_ccy, ts, mode, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        new_count = 0
        with self._get_cursor() as cursor:
            for fill in fills:
                inst_id = fill.get("instId", fill.get("inst_id", ""))
                ccy = inst_id.split("-")[0] if "-" in inst_id else inst_id

                # trade_id 去重键：优先使用 tradeId，若为空则使用 billId
                # 若都为空，使用 (inst_id, ts, side, fill_px, fill_sz) 生成合成 ID
                trade_id = fill.get("tradeId", fill.get("trade_id", ""))
                if not trade_id:
                    trade_id = fill.get("billId", fill.get("bill_id", ""))
                if not trade_id:
                    # 最后兜底：生成合成 ID
                    ts = fill.get("ts", 0)
                    side = fill.get("side", "")
                    fill_px = fill.get("fillPx", fill.get("fill_px", "0"))
                    fill_sz = fill.get("fillSz", fill.get("fill_sz", "0"))
                    trade_id = f"synth_{inst_id}_{ts}_{side}_{fill_px}_{fill_sz}"
                    print(f"[DataStorage] 成交记录缺少 tradeId/billId，使用合成 ID: {trade_id}")

                side = fill.get("side", "")

                # 保留原始字符串精度，不转成 float
                fill_px = fill.get("fillPx", fill.get("fill_px", "0"))
                fill_sz = fill.get("fillSz", fill.get("fill_sz", "0"))

                # 按交易所返回的原始数据保存手续费，不区分买卖方向
                # 让成本计算逻辑自己根据 fee_ccy 判断如何处理
                fee = fill.get("fee", "0") or "0"
                fee_ccy = fill.get("feeCcy", fill.get("fee_ccy", ""))

                cursor.execute(query, (
                    trade_id,
                    inst_id,
                    ccy,
                    side,
                    fill_px,  # 保留原始字符串
                    fill_sz,  # 保留原始字符串
                    fee,      # 保留原始字符串
                    fee_ccy,
                    int(fill.get("ts", 0)),
                    mode,
                    "api"
                ))
                if cursor.rowcount > 0:
                    new_count += 1

        return new_count

    def rebuild_fills_table(self) -> bool:
        """
        重建 local_fills 和 cost_basis 表（用于修复精度问题）

        会删除所有现有数据，需要重新同步

        Returns:
            是否成功
        """
        print("[DataStorage] 重建数据表...")
        with self._get_cursor() as cursor:
            # 删除旧表
            cursor.execute("DROP TABLE IF EXISTS local_fills")
            cursor.execute("DROP TABLE IF EXISTS cost_basis")

            # 重新创建 local_fills（使用 TEXT 类型保持精度）
            cursor.execute("""
                CREATE TABLE local_fills (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    trade_id TEXT,
                    inst_id TEXT NOT NULL,
                    ccy TEXT NOT NULL,
                    side TEXT NOT NULL,
                    fill_px TEXT NOT NULL,
                    fill_sz TEXT NOT NULL,
                    fee TEXT DEFAULT '0',
                    fee_ccy TEXT,
                    ts INTEGER NOT NULL,
                    mode TEXT NOT NULL,
                    source TEXT DEFAULT 'api',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(trade_id, mode)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_fills_ccy_mode
                ON local_fills(ccy, mode)
            """)

            # 重新创建 cost_basis（使用 TEXT 类型保持精度）
            cursor.execute("""
                CREATE TABLE cost_basis (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ccy TEXT NOT NULL,
                    mode TEXT NOT NULL,
                    avg_cost TEXT NOT NULL,
                    total_qty TEXT NOT NULL,
                    total_cost TEXT NOT NULL,
                    total_fee TEXT NOT NULL DEFAULT '0',
                    total_buy_cost TEXT NOT NULL DEFAULT '0',
                    total_sell_revenue TEXT NOT NULL DEFAULT '0',
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(ccy, mode)
                )
            """)

        print("[DataStorage] 数据表重建完成，请重新同步成交记录")
        return True

    def get_fills(
        self,
        mode: str,
        ccy: str = "",
        inst_id: str = "",
        limit: int = 1000
    ) -> List[Dict[str, Any]]:
        """
        获取本地成交记录

        Args:
            mode: simulated/live
            ccy: 币种过滤（可选）
            inst_id: 交易对过滤（可选，如 BTC-USDT）
            limit: 返回数量限制

        Returns:
            成交记录列表
        """
        # 构建动态查询条件
        conditions = ["mode = ?"]
        params = [mode]

        if inst_id:
            # inst_id 过滤优先级高于 ccy
            conditions.append("inst_id = ?")
            params.append(inst_id)
        elif ccy:
            conditions.append("ccy = ?")
            params.append(ccy)

        params.append(limit)

        query = f"""
            SELECT * FROM local_fills
            WHERE {" AND ".join(conditions)}
            ORDER BY ts DESC
            LIMIT ?
        """

        fills = []
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                fills.append({
                    "trade_id": row["trade_id"],
                    "inst_id": row["inst_id"],
                    "ccy": row["ccy"],
                    "side": row["side"],
                    "fill_px": row["fill_px"],
                    "fill_sz": row["fill_sz"],
                    "fee": row["fee"],
                    "fee_ccy": row["fee_ccy"],
                    "ts": row["ts"],
                    "source": row["source"],
                })
        return fills

    def get_fills_count(self, mode: str) -> int:
        """获取成交记录总数"""
        query = "SELECT COUNT(*) as cnt FROM local_fills WHERE mode = ?"
        with self._get_cursor() as cursor:
            cursor.execute(query, (mode,))
            row = cursor.fetchone()
            return row["cnt"] if row else 0

    def calculate_cost_basis(self, mode: str) -> Dict[str, Dict[str, float]]:
        """
        从成交记录计算每个币种的成本基础

        计算逻辑（净成本法）：
        - 净成本 = 总买入花费 - 总卖出收入
        - 当前持仓数量 = 总买入数量 - 总卖出数量
        - 盈亏 = 当前市值 - 净成本

        如果净成本为负，说明已经"回本有余"，剩余持仓是纯利润。

        OKX手续费规则：
        - 买入时：手续费从买到的币中扣（feeCcy=基础货币），实际得到数量减少
        - 卖出时：不收手续费

        Args:
            mode: simulated/live

        Returns:
            {ccy: {avg_cost, total_qty, total_cost, total_fee, total_buy_cost, total_sell_revenue}}
        """
        # 获取所有记录，按时间排序
        query = """
            SELECT ccy, side, fill_px, fill_sz, fee, fee_ccy
            FROM local_fills
            WHERE mode = ?
            ORDER BY ts ASC
        """

        # 用于累计每个币种的数据（使用 Decimal 精确计算）
        positions: Dict[str, Dict[str, Decimal]] = {}

        print(f"[DataStorage] 开始计算成本基础 mode={mode}，使用净成本法")

        with self._get_cursor() as cursor:
            cursor.execute(query, (mode,))
            for row in cursor.fetchall():
                ccy = row["ccy"]
                side = row["side"]
                # 从数据库读取时转为 Decimal，保持精度
                price = Decimal(str(row["fill_px"]))
                size = Decimal(str(row["fill_sz"]))
                fee = Decimal(str(row["fee"] or 0))
                fee_ccy = row["fee_ccy"] or ""

                if ccy not in positions:
                    positions[ccy] = {
                        "total_buy_cost": Decimal("0"),     # 总买入花费（USDT）
                        "total_buy_qty": Decimal("0"),      # 总买入数量
                        "total_sell_revenue": Decimal("0"), # 总卖出收入（USDT）
                        "total_sell_qty": Decimal("0"),     # 总卖出数量
                        "total_fee": Decimal("0"),          # 总手续费
                    }

                pos = positions[ccy]
                fee_abs = abs(fee)

                if side == "buy":
                    # 买入：花费 USDT 换取币
                    buy_cost = price * size  # 花费的 USDT（不含手续费）

                    # 根据手续费币种确定实际得到的数量和手续费 USDT 等值
                    if fee_ccy == ccy:
                        # 手续费以基础币计，从买到的币中扣，实际得到数量减少
                        actual_qty = size - fee_abs
                        fee_usdt = fee_abs * price
                        # 手续费不额外增加 USDT 支出
                        total_cost = buy_cost
                    elif fee_ccy == "USDT" or fee_ccy == "":
                        # 手续费以 USDT 计，额外的 USDT 支出
                        actual_qty = size
                        fee_usdt = fee_abs
                        # 总成本 = 买币花费 + USDT 手续费
                        total_cost = buy_cost + fee_usdt
                    else:
                        # 手续费以第三方币计（如 OKB），不影响 USDT 或基础币数量
                        actual_qty = size
                        fee_usdt = fee_abs  # 近似为 USDT（口径说明）
                        total_cost = buy_cost

                    pos["total_buy_cost"] += total_cost
                    pos["total_buy_qty"] += actual_qty
                    pos["total_fee"] += fee_usdt

                    print(f"  [BUY] {ccy}: {size} @ {price}, cost={total_cost} USDT, "
                          f"actual_qty={actual_qty}, fee={fee_usdt} (fee_ccy={fee_ccy})")

                elif side == "sell":
                    # 卖出：卖出币换取 USDT
                    sell_revenue = price * size  # 毛收入（不含手续费）

                    # 根据手续费币种计算净收入
                    if fee_ccy == "USDT" or fee_ccy == "":
                        # 手续费以 USDT 计，从卖出收入中扣除
                        fee_usdt = fee_abs
                        actual_revenue = sell_revenue - fee_usdt
                    elif fee_ccy == ccy:
                        # 手续费以基础币计（少见），折算为 USDT 并从收入扣除
                        fee_usdt = fee_abs * price
                        actual_revenue = sell_revenue - fee_usdt
                    else:
                        # 手续费以第三方币计，不影响 USDT 收入
                        fee_usdt = fee_abs  # 近似
                        actual_revenue = sell_revenue

                    pos["total_sell_revenue"] += actual_revenue
                    pos["total_sell_qty"] += size
                    pos["total_fee"] += fee_usdt

                    print(f"  [SELL] {ccy}: {size} @ {price}, gross={sell_revenue} USDT, "
                          f"fee={fee_usdt}, net_revenue={actual_revenue} USDT (fee_ccy={fee_ccy})")

        # 计算最终结果
        print(f"[DataStorage] 成本计算结果:")
        result: Dict[str, Dict[str, float]] = {}

        for ccy, data in positions.items():
            # 当前持仓数量
            current_qty = data["total_buy_qty"] - data["total_sell_qty"]
            current_qty = max(current_qty, Decimal("0"))

            # 净成本 = 总买入 - 总卖出
            net_cost = data["total_buy_cost"] - data["total_sell_revenue"]

            # 平均买入价（参考值）
            if data["total_buy_qty"] > 0:
                avg_buy_price = data["total_buy_cost"] / data["total_buy_qty"]
            else:
                avg_buy_price = Decimal("0")

            print(f"  {ccy}: buy={data['total_buy_cost']} USDT for {data['total_buy_qty']}, "
                  f"sell={data['total_sell_revenue']} USDT for {data['total_sell_qty']}, "
                  f"current_qty={current_qty}, net_cost={net_cost}, avg_buy={avg_buy_price}")

            result[ccy] = {
                "total_qty": float(current_qty),                    # 当前持仓数量
                "total_cost": float(net_cost),                      # 净成本（可能为负）
                "avg_cost": float(avg_buy_price),                   # 平均买入价
                "total_fee": float(data["total_fee"]),              # 总手续费
                "total_buy_cost": float(data["total_buy_cost"]),    # 总买入花费
                "total_sell_revenue": float(data["total_sell_revenue"]),  # 总卖出收入
            }

        return result

    def get_cost_basis(self, mode: str, ccy: str = "") -> Dict[str, Dict[str, float]]:
        """
        获取成本基础

        Args:
            mode: simulated/live
            ccy: 指定币种（可选）

        Returns:
            成本基础数据
        """
        if ccy:
            query = """
                SELECT ccy, avg_cost, total_qty, total_cost, total_fee, total_buy_cost, total_sell_revenue
                FROM cost_basis
                WHERE mode = ? AND ccy = ?
            """
            params = (mode, ccy)
        else:
            query = """
                SELECT ccy, avg_cost, total_qty, total_cost, total_fee, total_buy_cost, total_sell_revenue
                FROM cost_basis
                WHERE mode = ?
            """
            params = (mode,)

        result = {}
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                result[row["ccy"]] = {
                    "avg_cost": float(row["avg_cost"]),
                    "total_qty": float(row["total_qty"]),
                    "total_cost": float(row["total_cost"]),
                    "total_fee": float(row["total_fee"]) if row["total_fee"] else 0,
                    "total_buy_cost": float(row["total_buy_cost"]) if row["total_buy_cost"] else 0,
                    "total_sell_revenue": float(row["total_sell_revenue"]) if row["total_sell_revenue"] else 0,
                }
        return result

    def save_cost_basis(
        self,
        ccy: str,
        mode: str,
        avg_cost: float,
        total_qty: float = 0,
        total_cost: float = 0,
        total_fee: float = 0,
        total_buy_cost: float = 0,
        total_sell_revenue: float = 0
    ) -> bool:
        """
        保存或更新成本基础

        Args:
            ccy: 币种
            mode: simulated/live
            avg_cost: 平均买入价
            total_qty: 当前持仓数量
            total_cost: 净成本
            total_fee: 总手续费
            total_buy_cost: 总买入花费
            total_sell_revenue: 总卖出收入

        Returns:
            是否成功
        """
        query = """
            INSERT INTO cost_basis (ccy, mode, avg_cost, total_qty, total_cost, total_fee,
                                    total_buy_cost, total_sell_revenue, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(ccy, mode) DO UPDATE SET
                avg_cost = excluded.avg_cost,
                total_qty = excluded.total_qty,
                total_cost = excluded.total_cost,
                total_fee = excluded.total_fee,
                total_buy_cost = excluded.total_buy_cost,
                total_sell_revenue = excluded.total_sell_revenue,
                last_updated = CURRENT_TIMESTAMP
        """

        with self._get_cursor() as cursor:
            cursor.execute(query, (ccy, mode, avg_cost, total_qty, total_cost, total_fee,
                                   total_buy_cost, total_sell_revenue))
            return True

    def update_cost_basis_from_fills(self, mode: str) -> Dict[str, Dict[str, float]]:
        """
        从成交记录重新计算并更新成本基础

        Args:
            mode: simulated/live

        Returns:
            更新后的成本基础数据
        """
        # 计算成本基础
        positions = self.calculate_cost_basis(mode)

        # 保存到数据库
        for ccy, data in positions.items():
            if data["total_qty"] > 0 or data.get("total_buy_cost", 0) > 0:
                self.save_cost_basis(
                    ccy=ccy,
                    mode=mode,
                    avg_cost=data["avg_cost"],
                    total_qty=data["total_qty"],
                    total_cost=data["total_cost"],
                    total_fee=data.get("total_fee", 0),
                    total_buy_cost=data.get("total_buy_cost", 0),
                    total_sell_revenue=data.get("total_sell_revenue", 0)
                )

        return positions

    # ==================== 回测结果持久化方法 ====================

    def save_backtest_result(self, result_dict: Dict[str, Any], strategy_id: str = "", params: Dict[str, Any] = None) -> int:
        """
        保存回测结果到数据库

        Args:
            result_dict: BacktestResult.to_dict() 的返回值
            strategy_id: 策略ID
            params: 策略参数

        Returns:
            新记录的ID
        """
        import json

        # 提取详细数据（equity_curve和trades）单独存储为JSON
        detail_data = {
            "equity_curve": result_dict.get("equity_curve", []),
            "trades": result_dict.get("trades", []),
        }
        detail_json = json.dumps(detail_data, ensure_ascii=False)
        params_json = json.dumps(params or {}, ensure_ascii=False)

        # 计算回测天数
        days = result_dict.get("duration_days", 0)

        query = """
            INSERT INTO backtest_results (
                strategy_name, strategy_id, symbol, timeframe, days,
                start_time, end_time,
                initial_capital, final_capital,
                total_return, annual_return, max_drawdown,
                sharpe_ratio, sortino_ratio, calmar_ratio,
                win_rate, profit_factor,
                total_trades, winning_trades, losing_trades,
                avg_profit, avg_loss, largest_profit, largest_loss,
                total_commission,
                params_json, detail_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        with self._get_cursor() as cursor:
            cursor.execute(query, (
                result_dict.get("strategy_name", ""),
                strategy_id,
                result_dict.get("symbol", ""),
                result_dict.get("timeframe", ""),
                days,
                result_dict.get("start_time", ""),
                result_dict.get("end_time", ""),
                result_dict.get("initial_capital", 0),
                result_dict.get("final_capital", 0),
                result_dict.get("total_return", 0),
                result_dict.get("annual_return", 0),
                result_dict.get("max_drawdown", 0),
                result_dict.get("sharpe_ratio", 0),
                result_dict.get("sortino_ratio", 0),
                result_dict.get("calmar_ratio", 0),
                result_dict.get("win_rate", 0),
                result_dict.get("profit_factor", 0),
                result_dict.get("total_trades", 0),
                result_dict.get("winning_trades", 0),
                result_dict.get("losing_trades", 0),
                result_dict.get("avg_profit", 0),
                result_dict.get("avg_loss", 0),
                result_dict.get("largest_profit", 0),
                result_dict.get("largest_loss", 0),
                result_dict.get("total_commission", 0),
                params_json,
                detail_json,
            ))
            return cursor.lastrowid

    def get_backtest_results(
        self,
        limit: int = 50,
        strategy_id: str = "",
        symbol: str = ""
    ) -> List[Dict[str, Any]]:
        """
        获取回测历史记录列表（不含详细数据）

        Args:
            limit: 返回数量限制
            strategy_id: 按策略ID过滤
            symbol: 按交易对过滤

        Returns:
            回测记录列表
        """
        query = """
            SELECT id, strategy_name, strategy_id, symbol, timeframe, days,
                   start_time, end_time, initial_capital, final_capital,
                   total_return, annual_return, max_drawdown,
                   sharpe_ratio, sortino_ratio, calmar_ratio,
                   win_rate, profit_factor,
                   total_trades, winning_trades, losing_trades,
                   avg_profit, avg_loss, largest_profit, largest_loss,
                   total_commission, params_json, created_at
            FROM backtest_results
            WHERE 1=1
        """
        params: List[Any] = []

        if strategy_id:
            query += " AND strategy_id = ?"
            params.append(strategy_id)
        if symbol:
            query += " AND symbol = ?"
            params.append(symbol)

        query += " ORDER BY created_at DESC LIMIT ?"
        params.append(limit)

        results = []
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                results.append({
                    "id": row["id"],
                    "strategy_name": row["strategy_name"],
                    "strategy_id": row["strategy_id"],
                    "symbol": row["symbol"],
                    "timeframe": row["timeframe"],
                    "days": row["days"],
                    "start_time": row["start_time"],
                    "end_time": row["end_time"],
                    "initial_capital": row["initial_capital"],
                    "final_capital": row["final_capital"],
                    "total_return": row["total_return"],
                    "annual_return": row["annual_return"],
                    "max_drawdown": row["max_drawdown"],
                    "sharpe_ratio": row["sharpe_ratio"],
                    "sortino_ratio": row["sortino_ratio"],
                    "calmar_ratio": row["calmar_ratio"],
                    "win_rate": row["win_rate"],
                    "profit_factor": row["profit_factor"],
                    "total_trades": row["total_trades"],
                    "winning_trades": row["winning_trades"],
                    "losing_trades": row["losing_trades"],
                    "avg_profit": row["avg_profit"],
                    "avg_loss": row["avg_loss"],
                    "largest_profit": row["largest_profit"],
                    "largest_loss": row["largest_loss"],
                    "total_commission": row["total_commission"],
                    "params_json": row["params_json"],
                    "created_at": row["created_at"],
                })
        return results

    def get_backtest_result_detail(self, result_id: int) -> Optional[Dict[str, Any]]:
        """
        获取单条回测结果的完整数据（含equity_curve和trades）

        Args:
            result_id: 记录ID

        Returns:
            完整回测结果，或None
        """
        import json

        query = """
            SELECT id, strategy_name, strategy_id, symbol, timeframe, days,
                   start_time, end_time, initial_capital, final_capital,
                   total_return, annual_return, max_drawdown,
                   sharpe_ratio, sortino_ratio, calmar_ratio,
                   win_rate, profit_factor,
                   total_trades, winning_trades, losing_trades,
                   avg_profit, avg_loss, largest_profit, largest_loss,
                   total_commission, params_json, detail_json, created_at
            FROM backtest_results
            WHERE id = ?
        """

        with self._get_cursor() as cursor:
            cursor.execute(query, (result_id,))
            row = cursor.fetchone()
            if not row:
                return None

            result = {
                "id": row["id"],
                "strategy_name": row["strategy_name"],
                "strategy_id": row["strategy_id"],
                "symbol": row["symbol"],
                "timeframe": row["timeframe"],
                "days": row["days"],
                "start_time": row["start_time"],
                "end_time": row["end_time"],
                "initial_capital": row["initial_capital"],
                "final_capital": row["final_capital"],
                "total_return": row["total_return"],
                "annual_return": row["annual_return"],
                "max_drawdown": row["max_drawdown"],
                "sharpe_ratio": row["sharpe_ratio"],
                "sortino_ratio": row["sortino_ratio"],
                "calmar_ratio": row["calmar_ratio"],
                "win_rate": row["win_rate"],
                "profit_factor": row["profit_factor"],
                "total_trades": row["total_trades"],
                "winning_trades": row["winning_trades"],
                "losing_trades": row["losing_trades"],
                "avg_profit": row["avg_profit"],
                "avg_loss": row["avg_loss"],
                "largest_profit": row["largest_profit"],
                "largest_loss": row["largest_loss"],
                "total_commission": row["total_commission"],
                "created_at": row["created_at"],
            }

            # 解析JSON详细数据
            if row["detail_json"]:
                detail = json.loads(row["detail_json"])
                result["equity_curve"] = detail.get("equity_curve", [])
                result["trades"] = detail.get("trades", [])

            if row["params_json"]:
                result["params"] = json.loads(row["params_json"])

            return result

    def delete_backtest_result(self, result_id: int) -> bool:
        """
        删除回测记录

        Args:
            result_id: 记录ID

        Returns:
            是否成功删除
        """
        query = "DELETE FROM backtest_results WHERE id = ?"
        with self._get_cursor() as cursor:
            cursor.execute(query, (result_id,))
            return cursor.rowcount > 0

    # ==================== 实时交易订单记录方法 ====================

    def save_live_order(
        self,
        order_id: str,
        inst_id: str,
        side: str,
        size: str,
        price: str,
        signal_type: str,
        success: bool,
        ts: str,
        strategy_id: str = "",
        strategy_name: str = "",
        error_message: str = ""
    ) -> bool:
        """
        保存实时交易订单记录

        Args:
            order_id: 订单ID
            inst_id: 交易对
            side: 方向
            size: 数量
            price: 价格
            signal_type: 信号类型
            success: 是否成功
            ts: 时间戳
            strategy_id: 策略ID
            strategy_name: 策略名称
            error_message: 错误信息

        Returns:
            是否成功保存
        """
        query = """
            INSERT INTO live_order_records
            (order_id, inst_id, side, size, price, signal_type, success,
             error_message, strategy_id, strategy_name, ts)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        with self._get_cursor() as cursor:
            cursor.execute(query, (
                order_id, inst_id, side, size, price, signal_type,
                1 if success else 0, error_message,
                strategy_id, strategy_name, ts
            ))
            return cursor.rowcount > 0

    def get_live_orders(
        self,
        limit: int = 50,
        strategy_id: str = ""
    ) -> List[Dict[str, Any]]:
        """
        获取实时交易订单记录

        Args:
            limit: 返回数量限制
            strategy_id: 按策略ID过滤

        Returns:
            订单记录列表
        """
        if strategy_id:
            query = """
                SELECT * FROM live_order_records
                WHERE strategy_id = ?
                ORDER BY ts DESC LIMIT ?
            """
            params = (strategy_id, limit)
        else:
            query = """
                SELECT * FROM live_order_records
                ORDER BY ts DESC LIMIT ?
            """
            params = (limit,)

        orders = []
        with self._get_cursor() as cursor:
            cursor.execute(query, params)
            for row in cursor.fetchall():
                orders.append({
                    "id": row["id"],
                    "order_id": row["order_id"],
                    "inst_id": row["inst_id"],
                    "side": row["side"],
                    "size": row["size"],
                    "price": row["price"],
                    "signal_type": row["signal_type"],
                    "success": bool(row["success"]),
                    "error_message": row["error_message"],
                    "strategy_id": row["strategy_id"],
                    "strategy_name": row["strategy_name"],
                    "timestamp": row["ts"],
                })
        return orders

    def close(self):
        """关闭数据库连接"""
        if hasattr(self._local, "connection") and self._local.connection:
            self._local.connection.close()
            self._local.connection = None


class DataManager:
    """
    数据管理器
    整合数据获取和存储功能
    """

    def __init__(self, storage: DataStorage, fetcher=None):
        """
        初始化数据管理器

        Args:
            storage: 数据存储器
            fetcher: 数据获取器（可选）
        """
        self.storage = storage
        self.fetcher = fetcher

    def sync_candles(
        self,
        inst_id: str,
        timeframe: str,
        days: int = 30,
        inst_type: str = "SPOT"
    ) -> int:
        """
        同步K线数据（从交易所获取并保存到本地）

        Args:
            inst_id: 交易对
            timeframe: 时间周期
            days: 同步最近多少天的数据
            inst_type: 交易类型

        Returns:
            同步的K线数量
        """
        if not self.fetcher:
            raise ValueError("未配置数据获取器")

        from datetime import timedelta
        start_time = datetime.now() - timedelta(days=days)

        print(f"开始同步 {inst_id} {timeframe} 最近{days}天数据...")

        candles = self.fetcher.get_history_candles(
            inst_id=inst_id,
            timeframe=timeframe,
            start_time=start_time,
            max_candles=days * 24 * 60  # 估算最大数量
        )

        if candles:
            saved = self.storage.save_candles(inst_id, timeframe, candles, inst_type)
            print(f"同步完成: 获取{len(candles)}条，保存{saved}条")
            return saved
        else:
            print("未获取到数据")
            return 0

    def get_candles_with_sync(
        self,
        inst_id: str,
        timeframe: str,
        count: int = 100,
        auto_sync: bool = True,
        inst_type: str = "SPOT",
    ) -> List[Candle]:
        """
        获取K线数据，本地不足时自动同步

        Args:
            inst_id: 交易对
            timeframe: 时间周期
            count: 需要的数量
            auto_sync: 是否自动同步
            inst_type: 交易类型

        Returns:
            K线数据列表
        """
        # 先从本地获取
        candles = self.storage.get_latest_candles(inst_id, timeframe, count, inst_type=inst_type)

        # 如果数量不足且允许自动同步
        if len(candles) < count and auto_sync and self.fetcher:
            self.sync_candles(inst_id, timeframe, days=7, inst_type=inst_type)
            candles = self.storage.get_latest_candles(inst_id, timeframe, count, inst_type=inst_type)

        return candles
