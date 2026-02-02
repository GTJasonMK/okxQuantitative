# 应用上下文（依赖装配/服务定位器）
#
# 目标：
# - 降低 API 层/业务层对底层实现与全局单例的“散落式”依赖
# - 把“实例获取/生命周期控制/模式选择”等装配逻辑集中到一个入口，便于替换与测试
#
# 说明：
# - 这里不引入额外框架，保持最小依赖；仅做轻量的集中装配。
# - 依赖本身仍可能是单例（Cached* / TradingManager / WS manager），但引用点被收敛。

from __future__ import annotations

from dataclasses import dataclass
from threading import Lock
from typing import Optional

from ..config import AppConfig, config
from .cache import (
    APIRateLimiter,
    CachedDataFetcher,
    CachedDataManager,
    CachedDataStorage,
    get_cached_fetcher,
    get_cached_manager,
    get_cached_storage,
    get_rate_limiter,
)
from .trader import OKXAccount, OKXTrader, TradingManager, get_trading_manager
from .websocket_manager import (
    OKXWebSocketManager,
    add_ws_restart_listener,
    get_ws_manager,
    restart_ws_manager,
    start_private_ws_manager,
    start_ws_manager,
    stop_ws_manager,
)
from ..utils.mode import mode_from_bool


@dataclass(frozen=True)
class AppContext:
    """应用上下文：集中提供项目运行所需的核心服务入口。"""

    cfg: AppConfig

    # ========== 基础 ==========
    def default_mode(self) -> str:
        """当前默认模式（由配置决定）"""
        return mode_from_bool(self.cfg.okx.is_simulated)

    # ========== 交易 ==========
    def trading_manager(self) -> TradingManager:
        return get_trading_manager()

    def trader(self, mode: str) -> OKXTrader:
        return self.trading_manager().get_trader(mode)

    def account(self, mode: str) -> OKXAccount:
        return self.trading_manager().get_account(mode)

    # ========== 数据/缓存 ==========
    def storage(self) -> CachedDataStorage:
        return get_cached_storage()

    def fetcher(self) -> CachedDataFetcher:
        return get_cached_fetcher()

    def manager(self) -> CachedDataManager:
        return get_cached_manager()

    def rate_limiter(self) -> APIRateLimiter:
        return get_rate_limiter()

    # ========== WebSocket ==========
    def ws_manager(self, mode: Optional[str] = None) -> OKXWebSocketManager:
        return get_ws_manager(mode)

    async def start_ws(self, mode: Optional[str] = None):
        return await start_ws_manager(mode)

    async def start_private_ws(self, mode: str):
        return await start_private_ws_manager(mode)

    async def stop_ws(self, mode: Optional[str] = None):
        return await stop_ws_manager(mode)

    async def restart_ws(self):
        return await restart_ws_manager()

    def add_ws_restart_listener(self, listener):
        add_ws_restart_listener(listener)


_ctx: Optional[AppContext] = None
_ctx_lock = Lock()


def get_app_context() -> AppContext:
    """获取全局 AppContext（懒加载单例）"""
    global _ctx
    if _ctx is None:
        with _ctx_lock:
            if _ctx is None:
                _ctx = AppContext(cfg=config)
    return _ctx
