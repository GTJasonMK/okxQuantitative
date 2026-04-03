import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .data_fetcher import Candle


class StorageCoreMixin:
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
        self._blocked_symbol_lock = threading.Lock()
        self._blocked_symbols: set[str] = set()
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """获取当前线程的数据库连接"""
        if not hasattr(self._local, "connection") or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=30,
            )
            self._local.connection.row_factory = sqlite3.Row
            # WAL 模式：允许读写并发，显著减少多线程下 "database is locked" 错误
            self._local.connection.execute("PRAGMA journal_mode=WAL")
            # busy_timeout：写冲突时等待而非立即报错（毫秒）
            self._local.connection.execute("PRAGMA busy_timeout=15000")
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
                    history_complete INTEGER NOT NULL DEFAULT 0,
                    last_sync_mode TEXT NOT NULL DEFAULT 'window',
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

            # 数据库迁移：给已有的 sync_records 表补字段
            sync_record_columns = set()
            try:
                cursor.execute("PRAGMA table_info(sync_records)")
                columns = cursor.fetchall()
                sync_record_columns = {
                    row["name"] if isinstance(row, sqlite3.Row) else row[1]
                    for row in columns
                }
            except Exception:
                sync_record_columns = set()

            if "history_complete" not in sync_record_columns:
                try:
                    cursor.execute("ALTER TABLE sync_records ADD COLUMN history_complete INTEGER NOT NULL DEFAULT 0")
                except Exception:
                    pass

            if "last_sync_mode" not in sync_record_columns:
                try:
                    cursor.execute("ALTER TABLE sync_records ADD COLUMN last_sync_mode TEXT NOT NULL DEFAULT 'window'")
                except Exception:
                    pass

            # 回测结果表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS backtest_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    strategy_name TEXT NOT NULL,
                    strategy_id TEXT NOT NULL,
                    symbol TEXT NOT NULL,
                    inst_type TEXT NOT NULL DEFAULT 'SPOT',
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

            # 数据库迁移：给已有的 backtest_results 表补字段
            backtest_columns = set()
            try:
                cursor.execute("PRAGMA table_info(backtest_results)")
                columns = cursor.fetchall()
                backtest_columns = {
                    row["name"] if isinstance(row, sqlite3.Row) else row[1]
                    for row in columns
                }
            except Exception:
                backtest_columns = set()

            if "inst_type" not in backtest_columns:
                try:
                    cursor.execute(
                        "ALTER TABLE backtest_results ADD COLUMN inst_type TEXT NOT NULL DEFAULT 'SPOT'"
                    )
                except Exception:
                    pass

            # 实时交易订单记录表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS live_order_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_id TEXT,
                    client_order_id TEXT DEFAULT '',
                    inst_id TEXT NOT NULL,
                    side TEXT NOT NULL,
                    size TEXT NOT NULL,
                    price TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    success INTEGER NOT NULL DEFAULT 0,
                    error_message TEXT DEFAULT '',
                    mode TEXT NOT NULL DEFAULT 'simulated',
                    strategy_id TEXT,
                    strategy_name TEXT,
                    ts TIMESTAMP NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # AI 助手会话表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS assistant_sessions (
                    session_id TEXT PRIMARY KEY,
                    title TEXT DEFAULT '',
                    kind TEXT NOT NULL DEFAULT 'agent',
                    mode TEXT NOT NULL DEFAULT 'simulated',
                    inst_id TEXT DEFAULT '',
                    inst_type TEXT NOT NULL DEFAULT 'SPOT',
                    status TEXT NOT NULL DEFAULT 'active',
                    last_error TEXT DEFAULT '',
                    metadata_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_assistant_sessions_kind_updated
                ON assistant_sessions(kind, updated_at)
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS assistant_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT DEFAULT '',
                    tool_name TEXT DEFAULT '',
                    tool_call_id TEXT DEFAULT '',
                    metadata_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_assistant_messages_session
                ON assistant_messages(session_id, id)
            """)

            cursor.execute("""
                CREATE TABLE IF NOT EXISTS assistant_steps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    step_index INTEGER NOT NULL DEFAULT 1,
                    step_type TEXT NOT NULL DEFAULT 'tool',
                    title TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'completed',
                    tool_name TEXT DEFAULT '',
                    input_json TEXT DEFAULT '{}',
                    output_json TEXT DEFAULT '{}',
                    error_text TEXT DEFAULT '',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_assistant_steps_session
                ON assistant_steps(session_id, step_index, id)
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS assistant_order_drafts (
                    draft_id TEXT PRIMARY KEY,
                    session_id TEXT DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'assistant',
                    title TEXT DEFAULT '',
                    status TEXT NOT NULL DEFAULT 'draft',
                    mode TEXT NOT NULL DEFAULT 'simulated',
                    inst_id TEXT NOT NULL,
                    inst_type TEXT NOT NULL DEFAULT 'SPOT',
                    side TEXT NOT NULL,
                    order_type TEXT NOT NULL DEFAULT 'limit',
                    td_mode TEXT DEFAULT 'cash',
                    pos_side TEXT DEFAULT '',
                    reduce_only INTEGER NOT NULL DEFAULT 0,
                    size TEXT NOT NULL,
                    price TEXT DEFAULT '',
                    stop_loss_price TEXT DEFAULT '',
                    take_profit_prices_json TEXT DEFAULT '[]',
                    risk_json TEXT DEFAULT '{}',
                    plan_json TEXT DEFAULT '{}',
                    annotations_json TEXT DEFAULT '[]',
                    summary TEXT DEFAULT '',
                    metadata_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    confirmed_at TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_assistant_order_drafts_session
                ON assistant_order_drafts(session_id, created_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_assistant_order_drafts_inst
                ON assistant_order_drafts(inst_id, status, created_at DESC)
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS assistant_level_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    session_id TEXT DEFAULT '',
                    source TEXT NOT NULL DEFAULT 'assistant',
                    title TEXT DEFAULT '',
                    inst_id TEXT NOT NULL,
                    inst_type TEXT NOT NULL DEFAULT 'SPOT',
                    timeframes_json TEXT DEFAULT '[]',
                    current_price REAL DEFAULT 0,
                    supports_json TEXT DEFAULT '[]',
                    resistances_json TEXT DEFAULT '[]',
                    invalidation_levels_json TEXT DEFAULT '[]',
                    chart_annotations_json TEXT DEFAULT '[]',
                    summary_json TEXT DEFAULT '{}',
                    metadata_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_assistant_level_snapshots_inst
                ON assistant_level_snapshots(inst_id, inst_type, created_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_assistant_level_snapshots_session
                ON assistant_level_snapshots(session_id, created_at DESC)
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS assistant_patrol_runs (
                    run_id TEXT PRIMARY KEY,
                    trigger TEXT NOT NULL DEFAULT 'scheduled',
                    inst_type TEXT NOT NULL DEFAULT 'SWAP',
                    mode TEXT NOT NULL DEFAULT 'simulated',
                    summary_json TEXT DEFAULT '{}',
                    candidates_json TEXT DEFAULT '[]',
                    result_json TEXT DEFAULT '{}',
                    event_json TEXT DEFAULT '{}',
                    settings_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_assistant_patrol_runs_time
                ON assistant_patrol_runs(created_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_assistant_patrol_runs_mode
                ON assistant_patrol_runs(inst_type, mode, trigger, created_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_live_orders_time
                ON live_order_records(ts)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_live_orders_strategy
                ON live_order_records(strategy_id)
            """)

            # 数据库迁移：给已有表补字段
            # 必须先补列，再建依赖该列的索引；否则旧库缺列时会在建索引阶段直接报错。
            column_names = set()
            try:
                cursor.execute("PRAGMA table_info(live_order_records)")
                columns = cursor.fetchall()
                column_names = {
                    row["name"] if isinstance(row, sqlite3.Row) else row[1]
                    for row in columns
                }
            except Exception:
                column_names = set()

            if "client_order_id" not in column_names:
                try:
                    cursor.execute("ALTER TABLE live_order_records ADD COLUMN client_order_id TEXT DEFAULT ''")
                except Exception:
                    pass

            if "mode" not in column_names:
                try:
                    cursor.execute("ALTER TABLE live_order_records ADD COLUMN mode TEXT NOT NULL DEFAULT 'simulated'")
                except Exception:
                    pass

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_live_orders_mode
                ON live_order_records(mode)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_live_orders_client_id
                ON live_order_records(client_order_id)
            """)

            # 交易日志表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS journal_entries (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    entry_id TEXT NOT NULL UNIQUE,
                    title TEXT DEFAULT '',
                    content TEXT DEFAULT '',
                    mode TEXT NOT NULL DEFAULT 'simulated',
                    inst_id TEXT DEFAULT '',
                    inst_type TEXT NOT NULL DEFAULT 'SPOT',
                    trade_ids_json TEXT DEFAULT '[]',
                    order_ids_json TEXT DEFAULT '[]',
                    tags_json TEXT DEFAULT '[]',
                    strategy_id TEXT DEFAULT '',
                    strategy_name TEXT DEFAULT '',
                    rating INTEGER DEFAULT 0,
                    emotion TEXT DEFAULT '',
                    screenshots_json TEXT DEFAULT '[]',
                    pnl_snapshot REAL DEFAULT 0,
                    metadata_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_journal_mode_time
                ON journal_entries(mode, created_at DESC)
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_journal_inst
                ON journal_entries(inst_id, created_at DESC)
            """)

            # 日志标签表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS journal_tags (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    tag TEXT NOT NULL UNIQUE,
                    color TEXT DEFAULT '',
                    usage_count INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 投资组合每日快照表（用于 VaR、Sharpe 等风险指标计算）
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS portfolio_snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mode TEXT NOT NULL,
                    date TEXT NOT NULL,
                    total_equity REAL NOT NULL,
                    spot_value REAL DEFAULT 0,
                    contract_value REAL DEFAULT 0,
                    cash_value REAL DEFAULT 0,
                    positions_json TEXT DEFAULT '{}',
                    metadata_json TEXT DEFAULT '{}',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE(mode, date)
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_portfolio_snapshots_mode_date
                ON portfolio_snapshots(mode, date DESC)
            """)

            # 扫描方案表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scanner_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id TEXT NOT NULL UNIQUE,
                    name TEXT NOT NULL,
                    conditions_json TEXT NOT NULL DEFAULT '[]',
                    logic TEXT DEFAULT 'and',
                    symbols_json TEXT DEFAULT '[]',
                    timeframe TEXT DEFAULT '1H',
                    inst_type TEXT DEFAULT 'SPOT',
                    enabled INTEGER DEFAULT 1,
                    interval_seconds INTEGER DEFAULT 300,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # 扫描结果表
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS scanner_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id TEXT NOT NULL,
                    inst_id TEXT NOT NULL,
                    inst_type TEXT DEFAULT 'SPOT',
                    timeframe TEXT NOT NULL,
                    matched_conditions_json TEXT DEFAULT '[]',
                    indicator_values_json TEXT DEFAULT '{}',
                    price REAL DEFAULT 0,
                    scan_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_scanner_results_time
                ON scanner_results(profile_id, scan_time DESC)
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
        if self._is_write_blocked_for_inst_id(inst_id):
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
        inst_type: str,
        *,
        history_complete: Optional[bool] = None,
        last_sync_mode: Optional[str] = None,
    ):
        """更新同步记录"""
        if self._is_write_blocked_for_inst_id(inst_id):
            return

        cursor.execute("""
            SELECT history_complete, last_sync_mode
            FROM sync_records
            WHERE inst_id = ? AND inst_type = ? AND timeframe = ?
        """, (inst_id, inst_type, timeframe))
        existing = cursor.fetchone()

        cursor.execute("""
            SELECT MIN(timestamp) AS oldest_timestamp,
                   MAX(timestamp) AS newest_timestamp,
                   COUNT(*) AS candle_count
            FROM candles
            WHERE inst_id = ? AND inst_type = ? AND timeframe = ?
        """, (inst_id, inst_type, timeframe))
        stats = cursor.fetchone()

        history_complete_value = int(existing["history_complete"]) if existing else 0
        if history_complete is not None:
            history_complete_value = 1 if history_complete else 0

        last_sync_mode_value = existing["last_sync_mode"] if existing and existing["last_sync_mode"] else "window"
        if last_sync_mode is not None:
            last_sync_mode_value = last_sync_mode

        cursor.execute("""
            INSERT OR REPLACE INTO sync_records
            (
                inst_id, inst_type, timeframe, last_sync_time,
                oldest_timestamp, newest_timestamp, candle_count,
                history_complete, last_sync_mode
            )
            VALUES (?, ?, ?, CURRENT_TIMESTAMP, ?, ?, ?, ?, ?)
        """, (
            inst_id,
            inst_type,
            timeframe,
            stats["oldest_timestamp"] if stats else None,
            stats["newest_timestamp"] if stats else None,
            stats["candle_count"] if stats else 0,
            history_complete_value,
            last_sync_mode_value,
        ))

    def update_sync_record(
        self,
        inst_id: str,
        timeframe: str,
        inst_type: str = "SPOT",
        *,
        history_complete: Optional[bool] = None,
        last_sync_mode: Optional[str] = None,
    ) -> None:
        """公开的同步记录更新入口。"""
        with self._get_cursor() as cursor:
            self._update_sync_record(
                cursor,
                inst_id,
                timeframe,
                inst_type,
                history_complete=history_complete,
                last_sync_mode=last_sync_mode,
            )

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
                   oldest_timestamp, newest_timestamp, candle_count,
                   history_complete, last_sync_mode
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
                    "history_complete": bool(row["history_complete"]) if "history_complete" in row.keys() else False,
                    "last_sync_mode": row["last_sync_mode"] if "last_sync_mode" in row.keys() else "window",
                })
        return records

    def get_sync_record(
        self,
        inst_id: str,
        timeframe: str,
        inst_type: str = "SPOT",
    ) -> Optional[Dict[str, Any]]:
        """获取单个交易对/周期的同步状态。"""
        query = """
            SELECT inst_id, inst_type, timeframe, last_sync_time,
                   oldest_timestamp, newest_timestamp, candle_count,
                   history_complete, last_sync_mode
            FROM sync_records
            WHERE inst_id = ? AND inst_type = ? AND timeframe = ?
        """

        with self._get_cursor() as cursor:
            cursor.execute(query, (inst_id, inst_type, timeframe))
            row = cursor.fetchone()
            if not row:
                return None
            return {
                "inst_id": row["inst_id"],
                "inst_type": row["inst_type"],
                "timeframe": row["timeframe"],
                "last_sync_time": row["last_sync_time"],
                "oldest_timestamp": row["oldest_timestamp"],
                "newest_timestamp": row["newest_timestamp"],
                "candle_count": row["candle_count"],
                "history_complete": bool(row["history_complete"]) if "history_complete" in row.keys() else False,
                "last_sync_mode": row["last_sync_mode"] if "last_sync_mode" in row.keys() else "window",
            }

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

    @staticmethod
    def _normalize_symbol_variants(symbol: str) -> Tuple[str, str, str, str]:
        normalized_symbol = str(symbol or "").strip().upper()
        if normalized_symbol.endswith("-SWAP"):
            normalized_symbol = normalized_symbol[:-5]
        if not normalized_symbol:
            return "", "", "", ""

        base_ccy = normalized_symbol.split("-")[0] if "-" in normalized_symbol else normalized_symbol
        spot_inst_id = normalized_symbol
        swap_inst_id = f"{normalized_symbol}-SWAP"
        return normalized_symbol, spot_inst_id, swap_inst_id, base_ccy

    def block_symbol_writes(self, symbol: str) -> str:
        """封锁指定基础交易对的后续行情写入，防止删除后旧任务回写。"""
        normalized_symbol, _, _, _ = self._normalize_symbol_variants(symbol)
        if not normalized_symbol:
            return ""
        with self._blocked_symbol_lock:
            self._blocked_symbols.add(normalized_symbol)
        return normalized_symbol

    def unblock_symbol_writes(self, symbol: str) -> str:
        """解除指定基础交易对的写入封锁。"""
        normalized_symbol, _, _, _ = self._normalize_symbol_variants(symbol)
        if not normalized_symbol:
            return ""
        with self._blocked_symbol_lock:
            self._blocked_symbols.discard(normalized_symbol)
        return normalized_symbol

    def is_symbol_write_blocked(self, symbol: str) -> bool:
        normalized_symbol, _, _, _ = self._normalize_symbol_variants(symbol)
        if not normalized_symbol:
            return False
        with self._blocked_symbol_lock:
            return normalized_symbol in self._blocked_symbols

    def _is_write_blocked_for_inst_id(self, inst_id: str) -> bool:
        normalized_symbol, _, _, _ = self._normalize_symbol_variants(inst_id)
        if not normalized_symbol:
            return False
        with self._blocked_symbol_lock:
            return normalized_symbol in self._blocked_symbols

    @staticmethod
    def _inventory_symbol_expr(field_name: str) -> str:
        return (
            f"CASE "
            f"WHEN {field_name} LIKE '%-SWAP' THEN substr({field_name}, 1, length({field_name}) - 5) "
            f"ELSE {field_name} "
            f"END"
        )

    @staticmethod
    def _safe_iso_to_timestamp(value: Optional[str]) -> float:
        if not value:
            return 0.0
        try:
            return datetime.fromisoformat(value).timestamp()
        except Exception:
            return 0.0

    def get_symbol_data_inventory(self) -> List[Dict[str, Any]]:
        """按基础交易对汇总当前本地数据库库存。"""
        timeframe_order = {
            "1m": 1,
            "3m": 2,
            "5m": 3,
            "15m": 4,
            "30m": 5,
            "1H": 6,
            "2H": 7,
            "4H": 8,
            "6H": 9,
            "12H": 10,
            "1D": 11,
            "1W": 12,
            "1M": 13,
        }

        def ensure_entry(symbol: str) -> Optional[Dict[str, Any]]:
            normalized_symbol, spot_inst_id, swap_inst_id, base_ccy = self._normalize_symbol_variants(symbol)
            if not normalized_symbol:
                return None
            if normalized_symbol not in inventory:
                inventory[normalized_symbol] = {
                    "symbol": normalized_symbol,
                    "base_ccy": base_ccy,
                    "spot_inst_id": spot_inst_id,
                    "swap_inst_id": swap_inst_id,
                    "timeframe_record_count": 0,
                    "candle_count": 0,
                    "markets": {},
                    "storage_counts": {
                        "candles": 0,
                        "sync_records": 0,
                        "market_ticker_snapshots": 0,
                        "market_recent_trades": 0,
                        "local_fills": 0,
                        "live_order_records": 0,
                        "backtest_results": 0,
                        "cost_basis": 0,
                        "total": 0,
                    },
                }
            return inventory[normalized_symbol]

        def update_time_bounds(container: Dict[str, Any], oldest_time: Optional[str], newest_time: Optional[str], last_sync_time: Optional[str]) -> None:
            if oldest_time:
                current_oldest = container.get("oldest_time")
                if not current_oldest or self._safe_iso_to_timestamp(oldest_time) < self._safe_iso_to_timestamp(current_oldest):
                    container["oldest_time"] = oldest_time
            if newest_time:
                current_newest = container.get("newest_time")
                if not current_newest or self._safe_iso_to_timestamp(newest_time) > self._safe_iso_to_timestamp(current_newest):
                    container["newest_time"] = newest_time
            if last_sync_time:
                current_last_sync = container.get("last_sync_time")
                if not current_last_sync or self._safe_iso_to_timestamp(last_sync_time) > self._safe_iso_to_timestamp(current_last_sync):
                    container["last_sync_time"] = last_sync_time

        inventory: Dict[str, Dict[str, Any]] = {}

        for row in self.get_sync_status():
            entry = ensure_entry(row.get("inst_id", ""))
            if not entry:
                continue

            inst_type = str(row.get("inst_type") or "SPOT").upper()
            market = entry["markets"].setdefault(
                inst_type,
                {
                    "inst_id": str(row.get("inst_id") or ""),
                    "inst_type": inst_type,
                    "timeframe_count": 0,
                    "candle_count": 0,
                    "history_complete_count": 0,
                    "oldest_time": None,
                    "newest_time": None,
                    "last_sync_time": None,
                    "timeframes": [],
                },
            )

            candle_count = int(row.get("candle_count", 0) or 0)
            timeframe_item = {
                "timeframe": row.get("timeframe") or "",
                "candle_count": candle_count,
                "history_complete": bool(row.get("history_complete", False)),
                "last_sync_mode": row.get("last_sync_mode") or "window",
                "last_sync_time": row.get("last_sync_time"),
                "oldest_time": row.get("oldest_time"),
                "newest_time": row.get("newest_time"),
            }

            market["timeframes"].append(timeframe_item)
            market["timeframe_count"] += 1
            market["candle_count"] += candle_count
            if timeframe_item["history_complete"]:
                market["history_complete_count"] += 1
            update_time_bounds(
                market,
                timeframe_item["oldest_time"],
                timeframe_item["newest_time"],
                timeframe_item["last_sync_time"],
            )

            entry["timeframe_record_count"] += 1
            entry["candle_count"] += candle_count

        with self._get_cursor() as cursor:
            table_queries = [
                ("candles", "candles", self._inventory_symbol_expr("inst_id")),
                ("sync_records", "sync_records", self._inventory_symbol_expr("inst_id")),
                ("market_ticker_snapshots", "market_ticker_snapshots", self._inventory_symbol_expr("inst_id")),
                ("market_recent_trades", "market_recent_trades", self._inventory_symbol_expr("inst_id")),
                (
                    "local_fills",
                    "local_fills",
                    "CASE "
                    "WHEN inst_id IS NULL OR inst_id = '' THEN ccy || '-USDT' "
                    "WHEN inst_id LIKE '%-SWAP' THEN substr(inst_id, 1, length(inst_id) - 5) "
                    "ELSE inst_id END",
                ),
                ("live_order_records", "live_order_records", self._inventory_symbol_expr("inst_id")),
                ("backtest_results", "backtest_results", self._inventory_symbol_expr("symbol")),
                ("cost_basis", "cost_basis", "ccy || '-USDT'"),
            ]

            for field_name, table_name, symbol_expr in table_queries:
                cursor.execute(
                    f"""
                    SELECT {symbol_expr} AS symbol, COUNT(*) AS cnt
                    FROM {table_name}
                    GROUP BY symbol
                    """
                )
                for row in cursor.fetchall():
                    entry = ensure_entry(row["symbol"])
                    if not entry:
                        continue
                    entry["storage_counts"][field_name] = int(row["cnt"] or 0)

        rows: List[Dict[str, Any]] = []
        for symbol, entry in inventory.items():
            for market in entry["markets"].values():
                market["timeframes"] = sorted(
                    market["timeframes"],
                    key=lambda item: timeframe_order.get(item["timeframe"], 999),
                )

            entry["storage_counts"]["total"] = sum(
                value for key, value in entry["storage_counts"].items() if key != "total"
            )
            if entry["candle_count"] <= 0:
                entry["candle_count"] = int(entry["storage_counts"].get("candles", 0) or 0)
            if entry["timeframe_record_count"] <= 0:
                entry["timeframe_record_count"] = int(entry["storage_counts"].get("sync_records", 0) or 0)

            rows.append(entry)

        rows.sort(
            key=lambda item: (
                -int(item["storage_counts"].get("total", 0) or 0),
                -int(item.get("candle_count", 0) or 0),
                item["symbol"],
            )
        )
        return rows

    def delete_symbol_related_data(self, symbol: str) -> Dict[str, int]:
        """按基础交易对删除该币本地所有相关数据。"""
        normalized_symbol, spot_inst_id, swap_inst_id, base_ccy = self._normalize_symbol_variants(symbol)
        if not normalized_symbol:
            return {
                "candles": 0,
                "sync_records": 0,
                "market_ticker_snapshots": 0,
                "market_recent_trades": 0,
                "local_fills": 0,
                "live_order_records": 0,
                "backtest_results": 0,
                "cost_basis": 0,
                "total": 0,
            }

        inst_ids = [spot_inst_id, swap_inst_id]
        placeholders = ",".join(["?"] * len(inst_ids))
        deleted_counts: Dict[str, int] = {}
        affected_cost_modes: set[str] = set()

        with self._get_cursor() as cursor:
            cursor.execute(
                f"""
                SELECT DISTINCT mode
                FROM local_fills
                WHERE inst_id IN ({placeholders})
                   OR (ccy = ? AND (inst_id IS NULL OR inst_id = ''))
                """,
                [*inst_ids, base_ccy],
            )
            affected_cost_modes.update(
                str(row["mode"] or "").strip()
                for row in cursor.fetchall()
                if str(row["mode"] or "").strip()
            )
            cursor.execute(
                "SELECT DISTINCT mode FROM cost_basis WHERE ccy = ?",
                (base_ccy,),
            )
            affected_cost_modes.update(
                str(row["mode"] or "").strip()
                for row in cursor.fetchall()
                if str(row["mode"] or "").strip()
            )

            cursor.execute(
                f"DELETE FROM candles WHERE inst_id IN ({placeholders})",
                inst_ids,
            )
            deleted_counts["candles"] = max(cursor.rowcount, 0)

            cursor.execute(
                f"DELETE FROM sync_records WHERE inst_id IN ({placeholders})",
                inst_ids,
            )
            deleted_counts["sync_records"] = max(cursor.rowcount, 0)

            cursor.execute(
                f"DELETE FROM market_ticker_snapshots WHERE inst_id IN ({placeholders})",
                inst_ids,
            )
            deleted_counts["market_ticker_snapshots"] = max(cursor.rowcount, 0)

            cursor.execute(
                f"DELETE FROM market_recent_trades WHERE inst_id IN ({placeholders})",
                inst_ids,
            )
            deleted_counts["market_recent_trades"] = max(cursor.rowcount, 0)

            cursor.execute(
                f"""
                DELETE FROM local_fills
                WHERE inst_id IN ({placeholders})
                   OR (ccy = ? AND (inst_id IS NULL OR inst_id = ''))
                """,
                [*inst_ids, base_ccy],
            )
            deleted_counts["local_fills"] = max(cursor.rowcount, 0)

            cursor.execute(
                f"DELETE FROM live_order_records WHERE inst_id IN ({placeholders})",
                inst_ids,
            )
            deleted_counts["live_order_records"] = max(cursor.rowcount, 0)

            cursor.execute(
                f"DELETE FROM backtest_results WHERE symbol IN ({placeholders}) OR symbol = ?",
                [*inst_ids, normalized_symbol],
            )
            deleted_counts["backtest_results"] = max(cursor.rowcount, 0)

            cursor.execute(
                "DELETE FROM cost_basis WHERE ccy = ?",
                (base_ccy,),
            )
            deleted_counts["cost_basis"] = max(cursor.rowcount, 0)

        for mode in sorted(affected_cost_modes):
            try:
                positions = self.calculate_cost_basis(mode)
            except Exception:
                continue

            base_position = positions.get(base_ccy)
            if not base_position:
                continue

            total_qty = float(base_position.get("total_qty", 0) or 0)
            total_buy_cost = float(base_position.get("total_buy_cost", 0) or 0)
            if total_qty <= 0 and total_buy_cost <= 0:
                continue

            self.save_cost_basis(
                ccy=base_ccy,
                mode=mode,
                avg_cost=float(base_position.get("avg_cost", 0) or 0),
                total_qty=total_qty,
                total_cost=float(base_position.get("total_cost", 0) or 0),
                total_fee=float(base_position.get("total_fee", 0) or 0),
                total_buy_cost=total_buy_cost,
                total_sell_revenue=float(base_position.get("total_sell_revenue", 0) or 0),
            )

        deleted_counts["total"] = sum(deleted_counts.values())
        return deleted_counts

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
