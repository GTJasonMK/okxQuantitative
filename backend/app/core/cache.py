# 缓存模块
# 提供单例模式和内存缓存功能

import time
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from threading import Lock
from collections import deque

from .data_fetcher import DataFetcher, Candle, MarketTrade, Ticker, create_fetcher
from .data_storage import DataStorage, DataManager
from ..config import config
from ..utils.timeframes import estimate_days_for_candle_count, timeframe_to_ms


def _is_data_stale(candles: List[Candle], timeframe: str, tolerance_factor: float = 2.0) -> bool:
    """
    检查数据是否过时

    Args:
        candles: K线数据列表
        timeframe: 时间周期
        tolerance_factor: 容忍倍数（默认2倍周期内认为是新鲜的）

    Returns:
        True 表示数据过时需要同步，False 表示数据新鲜
    """
    if not candles:
        return True

    timeframe_ms = timeframe_to_ms(timeframe)
    tolerance_ms = timeframe_ms * tolerance_factor

    newest_ts = candles[-1].timestamp
    now_ms = int(time.time() * 1000)

    # 如果最新K线的时间戳 + 容忍时间 < 当前时间，说明数据过时
    return (newest_ts + tolerance_ms) < now_ms


class APIRateLimiter:
    """API调用频率限制器"""
    _instance: Optional['APIRateLimiter'] = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._lock = Lock()
        # 使用deque记录每次调用的时间戳
        self._call_times: deque = deque()
        # 总调用次数
        self._total_calls = 0
        # 每分钟限制
        self._rate_limit = config.cache.okx_rate_limit
        # 启动时间
        self._start_time = time.time()

    def record_call(self, count: int = 1):
        """记录API调用"""
        now = time.time()
        with self._lock:
            for _ in range(count):
                self._call_times.append(now)
            self._total_calls += count
            # 清理超过1分钟的记录
            self._cleanup(now)

    def _cleanup(self, now: float):
        """清理过期记录"""
        cutoff = now - 60
        while self._call_times and self._call_times[0] < cutoff:
            self._call_times.popleft()

    def get_calls_per_minute(self) -> int:
        """获取当前分钟内的调用次数"""
        now = time.time()
        with self._lock:
            self._cleanup(now)
            return len(self._call_times)

    def get_remaining_quota(self) -> int:
        """获取剩余配额"""
        return max(0, self._rate_limit - self.get_calls_per_minute())

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        now = time.time()
        with self._lock:
            self._cleanup(now)
            calls_per_minute = len(self._call_times)
            return {
                "total_calls": self._total_calls,
                "calls_per_minute": calls_per_minute,
                "rate_limit": self._rate_limit,
                "remaining_quota": max(0, self._rate_limit - calls_per_minute),
                "usage_percent": round(calls_per_minute / self._rate_limit * 100, 1),
                "uptime_minutes": round((now - self._start_time) / 60, 1),
            }

    def can_call(self) -> bool:
        """检查是否可以调用（未超过限制）"""
        return self.get_calls_per_minute() < self._rate_limit


def get_rate_limiter() -> APIRateLimiter:
    """获取单例限流器"""
    return APIRateLimiter()


class SingletonMeta(type):
    """单例元类"""
    _instances: Dict[type, Any] = {}
    _lock = Lock()

    def __call__(cls, *args, **kwargs):
        with cls._lock:
            if cls not in cls._instances:
                cls._instances[cls] = super().__call__(*args, **kwargs)
        return cls._instances[cls]


class CachedDataStorage(DataStorage, metaclass=SingletonMeta):
    """单例数据存储器"""

    def __init__(self):
        # 使用配置文件中的数据库路径
        super().__init__(config.database.path)


class CachedDataFetcher:
    """带缓存的数据获取器（单例）"""
    _instance: Optional['CachedDataFetcher'] = None
    _lock = Lock()
    _init_lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        # 使用双重检查锁定模式确保线程安全
        if self._initialized:
            return
        with CachedDataFetcher._init_lock:
            if self._initialized:
                return
            try:
                # 行情数据属于公共接口，不应随“实盘/模拟盘”切换而改变。
                # 否则在 OKX Demo 环境下可能出现“部分交易对无K线/无行情”的现象，导致行情页刷新异常。
                self._fetcher = create_fetcher(is_simulated=False)
                self._storage = CachedDataStorage()
                # Ticker缓存: {inst_id: (data, timestamp)}
                self._ticker_cache: Dict[str, Tuple[Any, float]] = {}
                # 同步时间记录: {(inst_id, inst_type, timeframe): timestamp}
                self._sync_times: Dict[Tuple[str, str, str], float] = {}
                self._cache_lock = Lock()
                # 获取限流器
                self._rate_limiter = get_rate_limiter()
                self._initialized = True
            except Exception as e:
                print(f"[CachedDataFetcher] 初始化失败: {e}")
                self._fetcher = None
                self._storage = None
                self._ticker_cache = {}
                self._sync_times = {}
                self._cache_lock = Lock()
                self._rate_limiter = get_rate_limiter()
                self._initialized = True

    @property
    def fetcher(self) -> Optional[DataFetcher]:
        return self._fetcher

    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计信息（用于 /status 等诊断接口，避免直接访问私有字段）。"""
        with self._cache_lock:
            return {
                "ticker_entries": len(self._ticker_cache),
                "sync_cooldowns": len(self._sync_times),
            }

    def _record_api_call(self, count: int = 1):
        """记录API调用"""
        self._rate_limiter.record_call(count)

    def _get_storage(self) -> Optional[DataStorage]:
        """获取本地存储实例，测试场景允许注入临时存储。"""
        storage = getattr(self, "_storage", None)
        if storage is not None:
            return storage
        try:
            storage = CachedDataStorage()
            self._storage = storage
            return storage
        except Exception as e:
            print(f"[CachedDataFetcher] 获取本地存储失败: {e}")
            self._storage = None
            return None

    def _normalize_inst_type(self, inst_type: Any = None, *, inst_id: str = "") -> str:
        """规范化交易类型，缺省时从交易对后缀做兜底推断。"""
        if hasattr(inst_type, "value"):
            normalized = str(inst_type.value).upper().strip()
        else:
            normalized = str(inst_type or "").upper().strip()

        if normalized in {"SPOT", "SWAP", "FUTURES", "OPTION"}:
            return normalized
        if inst_id.endswith("-SWAP"):
            return "SWAP"
        return "SPOT"

    def _coerce_ticker_model(self, ticker: Any) -> Optional[Ticker]:
        """把不同来源的 ticker 统一成 DataFetcher.Ticker。"""
        if ticker is None:
            return None
        if isinstance(ticker, Ticker):
            return ticker

        try:
            return Ticker(
                inst_id=getattr(ticker, "inst_id"),
                last=float(getattr(ticker, "last", 0) or 0),
                last_sz=float(getattr(ticker, "last_sz", 0) or 0),
                ask_px=float(getattr(ticker, "ask_px", 0) or 0),
                ask_sz=float(getattr(ticker, "ask_sz", 0) or 0),
                bid_px=float(getattr(ticker, "bid_px", 0) or 0),
                bid_sz=float(getattr(ticker, "bid_sz", 0) or 0),
                open_24h=float(getattr(ticker, "open_24h", 0) or 0),
                high_24h=float(getattr(ticker, "high_24h", 0) or 0),
                low_24h=float(getattr(ticker, "low_24h", 0) or 0),
                vol_24h=float(getattr(ticker, "vol_24h", 0) or 0),
                vol_ccy_24h=float(getattr(ticker, "vol_ccy_24h", 0) or 0),
                timestamp=int(getattr(ticker, "timestamp", 0) or 0),
            )
        except Exception:
            return None

    def _cache_ticker_entry(self, inst_id: str, ticker: Any, now: Optional[float] = None):
        """更新单个 ticker 的内存缓存。"""
        model = self._coerce_ticker_model(ticker)
        if not model:
            return
        cache_ts = now if now is not None else time.time()
        with self._cache_lock:
            self._ticker_cache[inst_id] = (model, cache_ts)

    def prime_ticker_cache(self, ticker: Any, *, inst_type: Optional[str] = None):
        """供 WS 回调快速刷新内存缓存，减少页面轮询时的数据库读取。"""
        model = self._coerce_ticker_model(ticker)
        if not model:
            return

        now = time.time()
        normalized_inst_type = self._normalize_inst_type(inst_type, inst_id=model.inst_id)
        with self._cache_lock:
            self._ticker_cache[model.inst_id] = (model, now)
            cache_key = f"all_tickers_{normalized_inst_type}"
            if cache_key in self._ticker_cache:
                cached_dict, _ = self._ticker_cache[cache_key]
                if isinstance(cached_dict, dict):
                    updated = dict(cached_dict)
                    updated[model.inst_id] = model
                    self._ticker_cache[cache_key] = (updated, now)

    def get_ticker_cached(self, inst_id: str, inst_type: Optional[str] = None):
        """本地优先获取单个交易对行情，缺失时再调用远端并落库。"""
        now = time.time()
        normalized_inst_type = self._normalize_inst_type(inst_type, inst_id=inst_id)

        with self._cache_lock:
            if inst_id in self._ticker_cache:
                data, ts = self._ticker_cache[inst_id]
                if now - ts < config.cache.ticker_cache_ttl:
                    return data

        storage = self._get_storage()
        max_age_ms = int(config.cache.ticker_cache_ttl * 1000)
        if storage:
            local_ticker = storage.get_latest_ticker(
                inst_id,
                inst_type=normalized_inst_type,
                max_age_ms=max_age_ms,
            )
            if local_ticker:
                self._cache_ticker_entry(inst_id, local_ticker, now)
                return local_ticker

        if self._fetcher:
            try:
                self._record_api_call()
                ticker = self._fetcher.get_ticker(inst_id)
                if ticker:
                    if storage:
                        storage.save_ticker_snapshot(
                            ticker,
                            inst_type=normalized_inst_type,
                            source="rest",
                        )
                    self._cache_ticker_entry(inst_id, ticker, now)
                    return self._coerce_ticker_model(ticker)
            except Exception as e:
                print(f"[CachedDataFetcher] 获取ticker缓存失败 {inst_id}: {e}")

        if storage:
            fallback_ticker = storage.get_latest_ticker(inst_id, inst_type=normalized_inst_type)
            if fallback_ticker:
                self._cache_ticker_entry(inst_id, fallback_ticker, now)
                return fallback_ticker
        return None

    def get_tickers_cached(self, inst_type: str = "SPOT") -> dict:
        """
        获取某交易类型最新行情并缓存。

        策略：
        - 先读内存缓存；
        - 再读本地数据库中的最新快照；
        - 如本地无数据或远端需要初始化，则拉一次 OKX 批量接口并落库；
        - 远端失败时回退到本地已有数据。
        """
        normalized_inst_type = self._normalize_inst_type(inst_type)
        cache_key = f"all_tickers_{normalized_inst_type}"
        now = time.time()

        with self._cache_lock:
            if cache_key in self._ticker_cache:
                data, ts = self._ticker_cache[cache_key]
                if now - ts < config.cache.ticker_cache_ttl:
                    return data

        storage = self._get_storage()
        max_age_ms = int(config.cache.ticker_cache_ttl * 1000)
        if storage:
            local_tickers = storage.get_latest_tickers(
                inst_type=normalized_inst_type,
                max_age_ms=max_age_ms,
            )
            if local_tickers:
                ticker_dict = {ticker.inst_id: ticker for ticker in local_tickers}
                with self._cache_lock:
                    self._ticker_cache[cache_key] = (ticker_dict, now)
                    for inst_id, ticker in ticker_dict.items():
                        self._ticker_cache[inst_id] = (ticker, now)
                return ticker_dict

        if self._fetcher:
            try:
                self._record_api_call()
                from .data_fetcher import InstType

                inst_type_enum = InstType(normalized_inst_type)
                tickers = self._fetcher.get_tickers(inst_type_enum)
                ticker_dict = {ticker.inst_id: ticker for ticker in tickers}
                if ticker_dict and storage:
                    storage.save_ticker_snapshots(
                        list(ticker_dict.values()),
                        inst_type=normalized_inst_type,
                        source="rest",
                    )
                if ticker_dict:
                    with self._cache_lock:
                        self._ticker_cache[cache_key] = (ticker_dict, now)
                        for inst_id, ticker in ticker_dict.items():
                            self._ticker_cache[inst_id] = (ticker, now)
                    return ticker_dict
            except Exception as e:
                print(f"[CachedDataFetcher] 批量获取tickers失败: {e}")

        if storage:
            fallback_tickers = storage.get_latest_tickers(inst_type=normalized_inst_type)
            if fallback_tickers:
                ticker_dict = {ticker.inst_id: ticker for ticker in fallback_tickers}
                with self._cache_lock:
                    self._ticker_cache[cache_key] = (ticker_dict, now)
                    for inst_id, ticker in ticker_dict.items():
                        self._ticker_cache[inst_id] = (ticker, now)
                return ticker_dict
        return {}

    def get_recent_trades_local_first(
        self,
        inst_id: str,
        limit: int = 50,
        *,
        inst_type: Optional[str] = None,
    ) -> List[MarketTrade]:
        """本地优先获取最新逐笔成交。"""
        normalized_inst_type = self._normalize_inst_type(inst_type, inst_id=inst_id)
        storage = self._get_storage()
        max_age_ms = int(config.cache.ticker_cache_ttl * 1000)

        if storage:
            local_trades = storage.get_recent_trades(
                inst_id,
                limit=limit,
                inst_type=normalized_inst_type,
                max_age_ms=max_age_ms,
            )
            if len(local_trades) >= limit:
                return local_trades

        if self._fetcher:
            try:
                self._record_api_call()
                remote_trades = self._fetcher.get_recent_trades(inst_id, limit)
                if remote_trades:
                    if storage:
                        storage.save_recent_trades(
                            remote_trades,
                            inst_type=normalized_inst_type,
                            source="rest",
                        )
                    return remote_trades[:limit]
            except Exception as e:
                print(f"[CachedDataFetcher] 获取最新成交失败 {inst_id}: {e}")

        if storage:
            return storage.get_recent_trades(
                inst_id,
                limit=limit,
                inst_type=normalized_inst_type,
            )
        return []

    def get_orderbook(self, inst_id: str, size: int = 20) -> Optional[Dict[str, Any]]:
        """获取实时盘口深度。"""
        if self._fetcher:
            try:
                self._record_api_call()
                return self._fetcher.get_orderbook(inst_id, size)
            except Exception as e:
                print(f"[CachedDataFetcher] 获取盘口失败 {inst_id}: {e}")
                return None
        return None

    def get_candles(self, inst_id: str, timeframe: str, limit: int = 100):
        """获取K线（带计数）"""
        if self._fetcher:
            try:
                self._record_api_call()
                return self._fetcher.get_candles(inst_id, timeframe, limit)
            except Exception as e:
                print(f"[CachedDataFetcher] 获取K线失败 {inst_id}: {e}")
                return []
        return []

    def get_instruments(self, inst_type):
        """获取交易产品列表（带计数）"""
        if self._fetcher:
            try:
                self._record_api_call()
                return self._fetcher.get_instruments(inst_type)
            except Exception as e:
                print(f"[CachedDataFetcher] 获取交易产品失败: {e}")
                return []
        return []

    def can_sync(self, inst_id: str, timeframe: str, *, inst_type: str = "SPOT") -> bool:
        """
        检查是否可以同步（冷却时间检查，带并发预占位）

        说明：
        - 旧实现是 can_sync() -> 同步 -> mark_synced()，并发下可能重复触发同步
        - 这里在通过检查时“预占位”写入时间戳，降低并发重复同步概率
        """
        now = time.time()
        key = (inst_id, inst_type, timeframe)
        with self._cache_lock:
            last_sync = self._sync_times.get(key, 0)
            if now - last_sync >= config.cache.sync_cooldown:
                # 预占位，避免并发请求同时通过检查
                self._sync_times[key] = now
                return True
            return False

    def mark_synced(self, inst_id: str, timeframe: str, *, inst_type: str = "SPOT"):
        """标记已同步"""
        key = (inst_id, inst_type, timeframe)
        with self._cache_lock:
            self._sync_times[key] = time.time()

    def clear_sync_time(self, inst_id: str, timeframe: str, *, inst_type: str = "SPOT"):
        """
        清理同步冷却记录

        用途：
        - can_sync() 会在通过检查时预占位写入时间戳，用于降低并发重复同步概率
        - 若随后同步失败（网络/依赖/写库异常），需要清理预占位，否则会被错误冷却一段时间
        """
        key = (inst_id, inst_type, timeframe)
        with self._cache_lock:
            self._sync_times.pop(key, None)


class CachedDataManager:
    """带缓存的数据管理器（单例）"""
    _instance: Optional['CachedDataManager'] = None
    _lock = Lock()
    _init_lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        # 使用双重检查锁定模式确保线程安全
        if self._initialized:
            return
        with CachedDataManager._init_lock:
            if self._initialized:
                return
            try:
                self._storage = CachedDataStorage()
                self._cached_fetcher = CachedDataFetcher()
                # K线内存缓存: {(inst_id, inst_type, timeframe): (candles, timestamp)}
                self._candle_cache: Dict[Tuple[str, str, str], Tuple[List[Candle], float]] = {}
                self._cache_lock = Lock()
                self._initialized = True
            except Exception as e:
                print(f"[CachedDataManager] 初始化失败: {e}")
                self._storage = None
                self._cached_fetcher = None
                self._candle_cache = {}
                self._cache_lock = Lock()
                self._initialized = True

    @property
    def storage(self) -> DataStorage:
        return self._storage

    @property
    def fetcher(self) -> Optional[DataFetcher]:
        if self._cached_fetcher:
            return self._cached_fetcher.fetcher
        return None

    def get_cache_stats(self) -> Dict[str, int]:
        """获取缓存统计信息（用于 /status 等诊断接口，避免直接访问私有字段）。"""
        with self._cache_lock:
            return {
                "candle_entries": len(self._candle_cache),
            }

    def _invalidate_candle_cache(self, inst_id: str, timeframe: str, *, inst_type: str = "SPOT"):
        """同步完成后清理指定交易对的内存缓存。"""
        cache_key = (inst_id, inst_type, timeframe)
        with self._cache_lock:
            self._candle_cache.pop(cache_key, None)

    def _execute_sync(
        self,
        inst_id: str,
        timeframe: str,
        *,
        inst_type: str,
        action,
        use_cooldown: bool,
    ) -> Dict[str, Any]:
        if not self.fetcher or not self._storage:
            if self._cached_fetcher:
                self._cached_fetcher.clear_sync_time(inst_id, timeframe, inst_type=inst_type)
            raise ValueError("Fetcher or Storage not available")

        reserved = False
        if use_cooldown and self._cached_fetcher:
            reserved = self._cached_fetcher.can_sync(inst_id, timeframe, inst_type=inst_type)
            if not reserved:
                sync_record = self._storage.get_sync_record(inst_id, timeframe, inst_type)
                return {
                    "mode": "cooldown",
                    "fetched_count": 0,
                    "saved_count": 0,
                    "batches": 0,
                    "api_calls": 0,
                    "history_complete": bool(sync_record.get("history_complete", False)) if sync_record else False,
                    "candle_count": int(sync_record.get("candle_count", 0) or 0) if sync_record else 0,
                    "oldest_timestamp": sync_record.get("oldest_timestamp") if sync_record else None,
                    "newest_timestamp": sync_record.get("newest_timestamp") if sync_record else None,
                    "last_sync_mode": sync_record.get("last_sync_mode", "window") if sync_record else "window",
                    "last_sync_time": sync_record.get("last_sync_time") if sync_record else None,
                }

        manager = DataManager(self._storage, self.fetcher)
        try:
            result = action(manager)
            api_calls = max(int(result.get("api_calls", 0)), 0)
            if api_calls > 0:
                get_rate_limiter().record_call(api_calls)
            if self._cached_fetcher:
                self._cached_fetcher.mark_synced(inst_id, timeframe, inst_type=inst_type)
            self._invalidate_candle_cache(inst_id, timeframe, inst_type=inst_type)
            return result
        except Exception:
            if self._cached_fetcher and reserved:
                self._cached_fetcher.clear_sync_time(inst_id, timeframe, inst_type=inst_type)
            raise

    def get_candles_cached(
        self,
        inst_id: str,
        timeframe: str,
        count: int = 100,
        max_cache_age: int = 60,
        *,
        inst_type: str = "SPOT",
    ) -> List[Candle]:
        """
        获取K线数据（带内存缓存）

        Args:
            inst_id: 交易对
            timeframe: 时间周期
            count: 数量
            max_cache_age: 缓存最大有效期（秒）
            inst_type: 交易类型（SPOT/SWAP等）

        Returns:
            K线数据列表
        """
        # 检查存储是否可用
        if not self._storage:
            return []

        now = time.time()
        cache_key = (inst_id, inst_type, timeframe)

        # 检查内存缓存
        with self._cache_lock:
            if cache_key in self._candle_cache:
                candles, ts = self._candle_cache[cache_key]
                if now - ts < max_cache_age and len(candles) >= count:
                    return candles[-count:]

        self._ensure_local_candles_ready(
            inst_id,
            timeframe,
            count=count,
            inst_type=inst_type,
            use_cooldown=True,
        )

        # 从SQLite获取
        candles = self._storage.get_latest_candles(inst_id, timeframe, count, inst_type=inst_type)

        # 更新内存缓存
        if candles:
            with self._cache_lock:
                self._candle_cache[cache_key] = (candles, now)
                # 限制缓存大小
                if len(self._candle_cache) > config.cache.candle_cache_size:
                    oldest_key = min(
                        self._candle_cache.keys(),
                        key=lambda k: self._candle_cache[k][1]
                    )
                    del self._candle_cache[oldest_key]

        return candles

    def _ensure_local_candles_ready(
        self,
        inst_id: str,
        timeframe: str,
        *,
        count: int = 0,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        inst_type: str = "SPOT",
        use_cooldown: bool = False,
    ) -> Optional[Dict[str, Any]]:
        """确保本地数据库已具备当前请求所需的覆盖。"""
        if not self._storage or not self.fetcher:
            return None

        manager = DataManager(self._storage, self.fetcher)
        plan = manager.determine_sync_strategy(
            inst_id,
            timeframe,
            count=count,
            start_time=start_time,
            end_time=end_time,
            inst_type=inst_type,
        )
        if not plan:
            return None

        if plan["mode"] == "full":
            return self._sync_full_candles(
                inst_id,
                timeframe,
                days=plan["days"],
                inst_type=inst_type,
                use_cooldown=use_cooldown,
            )
        return self._sync_incremental_candles(
            inst_id,
            timeframe,
            days=plan["days"],
            inst_type=inst_type,
            use_cooldown=use_cooldown,
        )

    def _sync_window_candles(
        self,
        inst_id: str,
        timeframe: str,
        days: int = 7,
        *,
        inst_type: str = "SPOT",
        use_cooldown: bool = False,
        progress_callback=None,
    ):
        """同步最近窗口历史。"""
        return self._execute_sync(
            inst_id,
            timeframe,
            inst_type=inst_type,
            use_cooldown=use_cooldown,
            action=lambda manager: manager.sync_candles_window(
                inst_id,
                timeframe,
                days=days,
                inst_type=inst_type,
                progress_callback=progress_callback,
            ),
        )

    def _sync_incremental_candles(
        self,
        inst_id: str,
        timeframe: str,
        days: int = 30,
        *,
        inst_type: str = "SPOT",
        use_cooldown: bool = False,
        progress_callback=None,
    ):
        """同步本地最新 K 线之后的缺口。"""
        return self._execute_sync(
            inst_id,
            timeframe,
            inst_type=inst_type,
            use_cooldown=use_cooldown,
            action=lambda manager: manager.sync_candles_incremental(
                inst_id,
                timeframe,
                days=days,
                inst_type=inst_type,
                progress_callback=progress_callback,
            ),
        )

    def _sync_full_candles(
        self,
        inst_id: str,
        timeframe: str,
        days: int = 30,
        *,
        inst_type: str = "SPOT",
        use_cooldown: bool = False,
        progress_callback=None,
    ):
        """执行全量历史回补。"""
        return self._execute_sync(
            inst_id,
            timeframe,
            inst_type=inst_type,
            use_cooldown=use_cooldown,
            action=lambda manager: manager.sync_candles_full(
                inst_id,
                timeframe,
                days=days,
                inst_type=inst_type,
                progress_callback=progress_callback,
            ),
        )

    def get_candles_with_sync(
        self,
        inst_id: str,
        timeframe: str,
        count: int = 100,
        auto_sync: bool = True,
        *,
        inst_type: str = "SPOT",
    ) -> List[Candle]:
        """
        获取K线数据，可选自动同步

        Args:
            inst_id: 交易对
            timeframe: 时间周期
            count: 数量
            auto_sync: 是否自动同步（为False时只读本地数据，不触发网络同步）
            inst_type: 交易类型（SPOT/SWAP等）

        Returns:
            K线数据列表
        """
        if not auto_sync:
            # 只读本地数据，不同步
            if not self._storage:
                return []
            return self._storage.get_latest_candles(inst_id, timeframe, count, inst_type=inst_type)

        # 允许自动同步，使用带缓存和同步逻辑的方法
        return self.get_candles_cached(inst_id, timeframe, count, inst_type=inst_type)

    def get_local_candles(
        self,
        inst_id: str,
        timeframe: str,
        *,
        limit: int = 100,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        auto_sync: bool = True,
        inst_type: str = "SPOT",
    ) -> List[Candle]:
        """统一走本地数据库读取；必要时先做全量初始化或增量刷新。"""
        if not self._storage:
            return []

        if auto_sync:
            self._ensure_local_candles_ready(
                inst_id,
                timeframe,
                count=limit,
                start_time=start_time,
                end_time=end_time,
                inst_type=inst_type,
                use_cooldown=True,
            )

        if start_time or end_time:
            return self._storage.get_candles(
                inst_id=inst_id,
                timeframe=timeframe,
                start_time=start_time,
                end_time=end_time,
                limit=limit,
                inst_type=inst_type,
            )
        return self._storage.get_latest_candles(inst_id, timeframe, limit, inst_type=inst_type)

    def sync_candles(
        self,
        inst_id: str,
        timeframe: str,
        days: int = 30,
        inst_type: str = "SPOT"
    ) -> int:
        """强制同步K线数据"""
        result = self.sync_candles_window(
            inst_id,
            timeframe,
            days=days,
            inst_type=inst_type,
        )
        return result["saved_count"]

    def sync_candles_window(
        self,
        inst_id: str,
        timeframe: str,
        days: int = 30,
        inst_type: str = "SPOT",
        progress_callback=None,
    ) -> Dict[str, Any]:
        """手动触发窗口同步。"""
        return self._sync_window_candles(
            inst_id,
            timeframe,
            days=days,
            inst_type=inst_type,
            use_cooldown=False,
            progress_callback=progress_callback,
        )

    def sync_candles_incremental(
        self,
        inst_id: str,
        timeframe: str,
        days: int = 30,
        inst_type: str = "SPOT",
        progress_callback=None,
    ) -> Dict[str, Any]:
        """手动触发增量同步。"""
        return self._sync_incremental_candles(
            inst_id,
            timeframe,
            days=days,
            inst_type=inst_type,
            use_cooldown=False,
            progress_callback=progress_callback,
        )

    def sync_candles_full(
        self,
        inst_id: str,
        timeframe: str,
        days: int = 30,
        inst_type: str = "SPOT",
        progress_callback=None,
    ) -> Dict[str, Any]:
        """手动触发全量回补。"""
        return self._sync_full_candles(
            inst_id,
            timeframe,
            days=days,
            inst_type=inst_type,
            use_cooldown=False,
            progress_callback=progress_callback,
        )

    def clear_cache(self):
        """清除所有内存缓存"""
        with self._cache_lock:
            self._candle_cache.clear()


# 便捷函数
def get_cached_storage() -> CachedDataStorage:
    """获取单例存储器"""
    return CachedDataStorage()


def get_cached_fetcher() -> CachedDataFetcher:
    """获取单例获取器"""
    return CachedDataFetcher()


def get_cached_manager() -> CachedDataManager:
    """获取单例数据管理器"""
    return CachedDataManager()
