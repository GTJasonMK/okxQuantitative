# 缓存模块
# 提供单例模式和内存缓存功能

import time
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
from functools import lru_cache
from threading import Lock
from collections import deque

from .data_fetcher import DataFetcher, Candle, create_fetcher
from .data_storage import DataStorage, DataManager
from ..config import DATA_DIR, config
from ..utils.timeframes import timeframe_to_ms


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

    def get_ticker_cached(self, inst_id: str):
        """获取缓存的Ticker数据"""
        now = time.time()
        with self._cache_lock:
            if inst_id in self._ticker_cache:
                data, ts = self._ticker_cache[inst_id]
                if now - ts < config.cache.ticker_cache_ttl:
                    return data

        # 缓存过期或不存在，重新获取
        if self._fetcher:
            try:
                self._record_api_call()
                ticker = self._fetcher.get_ticker(inst_id)
                if ticker:
                    with self._cache_lock:
                        self._ticker_cache[inst_id] = (ticker, now)
                    return ticker
            except Exception as e:
                print(f"[CachedDataFetcher] 获取ticker缓存失败 {inst_id}: {e}")
        return None

    def get_ticker(self, inst_id: str):
        """获取Ticker（带计数）"""
        if self._fetcher:
            try:
                self._record_api_call()
                return self._fetcher.get_ticker(inst_id)
            except Exception as e:
                print(f"[CachedDataFetcher] 获取ticker失败 {inst_id}: {e}")
                return None
        return None

    def get_tickers(self, inst_type):
        """获取所有Ticker（带计数）"""
        if self._fetcher:
            try:
                self._record_api_call()
                return self._fetcher.get_tickers(inst_type)
            except Exception as e:
                print(f"[CachedDataFetcher] 获取tickers失败: {e}")
                return []
        return []

    def get_tickers_cached(self, inst_type: str = "SPOT") -> dict:
        """
        获取所有Ticker并缓存，返回 inst_id -> Ticker 的字典

        一次 API 调用获取所有行情，避免逐个查询
        """
        cache_key = f"all_tickers_{inst_type}"
        now = time.time()

        with self._cache_lock:
            if cache_key in self._ticker_cache:
                data, ts = self._ticker_cache[cache_key]
                if now - ts < config.cache.ticker_cache_ttl:
                    return data

        # 缓存过期或不存在，重新获取
        if self._fetcher:
            try:
                self._record_api_call()
                # 将字符串转换为 InstType 枚举
                from .data_fetcher import InstType
                inst_type_enum = InstType(inst_type)
                tickers = self._fetcher.get_tickers(inst_type_enum)
                # 转换为字典便于快速查找
                ticker_dict = {t.inst_id: t for t in tickers}
                with self._cache_lock:
                    self._ticker_cache[cache_key] = (ticker_dict, now)
                    # 同时更新单个 ticker 缓存
                    for inst_id, ticker in ticker_dict.items():
                        self._ticker_cache[inst_id] = (ticker, now)
                return ticker_dict
            except Exception as e:
                print(f"[CachedDataFetcher] 批量获取tickers失败: {e}")
        return {}

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

        # 从SQLite获取
        candles = self._storage.get_latest_candles(inst_id, timeframe, count, inst_type=inst_type)

        # 如果数据不足或数据过时，尝试同步
        needs_sync = len(candles) < count or _is_data_stale(candles, timeframe)
        if (
            needs_sync
            and self._cached_fetcher
            and self._cached_fetcher.can_sync(inst_id, timeframe, inst_type=inst_type)
        ):
            self._sync_candles(inst_id, timeframe, inst_type=inst_type)
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

    def _sync_candles(self, inst_id: str, timeframe: str, days: int = 7, *, inst_type: str = "SPOT"):
        """同步K线数据"""
        if not self.fetcher or not self._storage:
            # fetcher/storage 不可用时，清理预占位，避免进入错误冷却期
            if self._cached_fetcher:
                self._cached_fetcher.clear_sync_time(inst_id, timeframe, inst_type=inst_type)
            return

        from datetime import timedelta
        start_time = datetime.now() - timedelta(days=days)

        print(f"[Cache] Syncing {inst_id} {timeframe} ({inst_type})...")

        # 记录API调用（估算分页次数：每次最多300条）
        estimated_calls = max(1, (days * 24) // 300 + 1)
        get_rate_limiter().record_call(estimated_calls)

        try:
            candles = self.fetcher.get_history_candles(
                inst_id=inst_id,
                timeframe=timeframe,
                start_time=start_time,
                max_candles=days * 24 * 60
            )

            if candles:
                saved = self._storage.save_candles(inst_id, timeframe, candles, inst_type)
                print(f"[Cache] Synced {saved} candles for {inst_id}")
                if self._cached_fetcher:
                    # 仅在成功完成同步流程时更新冷却时间
                    self._cached_fetcher.mark_synced(inst_id, timeframe, inst_type=inst_type)
            else:
                # 获取不到数据属于失败场景：清理预占位允许后续请求重试
                if self._cached_fetcher:
                    self._cached_fetcher.clear_sync_time(inst_id, timeframe, inst_type=inst_type)
        except Exception as e:
            print(f"[Cache] 同步失败 {inst_id} {timeframe} ({inst_type}): {e}")
            if self._cached_fetcher:
                self._cached_fetcher.clear_sync_time(inst_id, timeframe, inst_type=inst_type)

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

    def sync_candles(
        self,
        inst_id: str,
        timeframe: str,
        days: int = 30,
        inst_type: str = "SPOT"
    ) -> int:
        """强制同步K线数据"""
        if not self.fetcher or not self._storage:
            raise ValueError("Fetcher or Storage not available")

        from datetime import timedelta
        start_time = datetime.now() - timedelta(days=days)

        # 记录API调用（估算分页次数）
        estimated_calls = max(1, (days * 24) // 300 + 1)
        get_rate_limiter().record_call(estimated_calls)

        candles = self.fetcher.get_history_candles(
            inst_id=inst_id,
            timeframe=timeframe,
            start_time=start_time,
            max_candles=days * 24 * 60
        )

        if candles:
            saved = self._storage.save_candles(inst_id, timeframe, candles, inst_type)
            if self._cached_fetcher:
                self._cached_fetcher.mark_synced(inst_id, timeframe, inst_type=inst_type)
            # 清除该交易对的内存缓存
            cache_key = (inst_id, inst_type, timeframe)
            with self._cache_lock:
                if cache_key in self._candle_cache:
                    del self._candle_cache[cache_key]
            return saved
        return 0

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
