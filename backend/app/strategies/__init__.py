# 策略模块
# 支持插件化架构：策略自动发现和注册

from .base import (
    BaseStrategy,
    StrategyConfig,
    Signal,
    SignalType,
    Order,
    OrderSide,
    OrderType,
    Trade,
    Position,
)
from .dual_ma import DualMAStrategy, DualMAConfig, DualMAParams, create_dual_ma_strategy
from .grid import GridStrategy, GridConfig, GridParams, create_grid_strategy
from .rsi_strategy import RSIStrategy, RSIConfig, RSIParams, create_rsi_strategy
from .bollinger_strategy import BollingerStrategy, BollingerConfig, BollingerParams, create_bollinger_strategy
from .macd_strategy import MACDStrategy, MACDConfig, MACDParams, create_macd_strategy
from .kdj_strategy import KDJStrategy, KDJConfig, KDJParams, create_kdj_strategy
from .hybrid_strategy import HybridStrategy, HybridConfig, HybridParams, create_hybrid_strategy
from .registry import (
    discover_strategies,
    reload_strategies,
    get_strategy,
    get_strategy_source,
    list_strategies,
    get_all_strategies,
    get_strategy_count,
    is_strategy_registered,
    load_external_strategies,
)

__all__ = [
    # 基础类型
    "BaseStrategy",
    "StrategyConfig",
    "Signal",
    "SignalType",
    "Order",
    "OrderSide",
    "OrderType",
    "Trade",
    "Position",
    # 双均线策略
    "DualMAStrategy",
    "DualMAConfig",
    "DualMAParams",
    "create_dual_ma_strategy",
    # 网格策略
    "GridStrategy",
    "GridConfig",
    "GridParams",
    "create_grid_strategy",
    # RSI策略
    "RSIStrategy",
    "RSIConfig",
    "RSIParams",
    "create_rsi_strategy",
    # 布林带策略
    "BollingerStrategy",
    "BollingerConfig",
    "BollingerParams",
    "create_bollinger_strategy",
    # MACD策略
    "MACDStrategy",
    "MACDConfig",
    "MACDParams",
    "create_macd_strategy",
    # KDJ策略
    "KDJStrategy",
    "KDJConfig",
    "KDJParams",
    "create_kdj_strategy",
    # 多指标混合策略
    "HybridStrategy",
    "HybridConfig",
    "HybridParams",
    "create_hybrid_strategy",
    # 策略注册表
    "discover_strategies",
    "reload_strategies",
    "get_strategy",
    "get_strategy_source",
    "list_strategies",
    "get_all_strategies",
    "get_strategy_count",
    "is_strategy_registered",
    "load_external_strategies",
]
