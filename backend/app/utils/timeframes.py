# 时间周期工具
#
# 目标：
# - 统一 timeframe/bar 的换算口径，避免在 cache/backtest/metrics 等模块里重复维护映射表
# - 保持纯函数（不依赖 FastAPI/配置），便于在服务层/脚本/单测中复用
#
# 约定：
# - 1W/1M 的毫秒换算采用项目既有口径：1W=7天，1M=30天（近似）
# - 年化周期数沿用历史口径：1W=52，1M=12（避免指标口径突然变化）

from __future__ import annotations

from typing import Optional


TIMEFRAME_TO_MS: dict[str, int] = {
    "1m": 60 * 1000,
    "3m": 3 * 60 * 1000,
    "5m": 5 * 60 * 1000,
    "15m": 15 * 60 * 1000,
    "30m": 30 * 60 * 1000,
    "1H": 60 * 60 * 1000,
    "2H": 2 * 60 * 60 * 1000,
    "4H": 4 * 60 * 60 * 1000,
    "6H": 6 * 60 * 60 * 1000,
    "12H": 12 * 60 * 60 * 1000,
    "1D": 24 * 60 * 60 * 1000,
    "1W": 7 * 24 * 60 * 60 * 1000,
    "1M": 30 * 24 * 60 * 60 * 1000,
}

DEFAULT_TIMEFRAME = "1H"

_DAY_MS = 24 * 60 * 60 * 1000

_PERIODS_PER_YEAR: dict[str, float] = {
    "1m": 365 * 24 * 60,
    "3m": 365 * 24 * 20,
    "5m": 365 * 24 * 12,
    "15m": 365 * 24 * 4,
    "30m": 365 * 24 * 2,
    "1H": 365 * 24,
    "2H": 365 * 12,
    "4H": 365 * 6,
    "6H": 365 * 4,
    "12H": 365 * 2,
    "1D": 365,
    "1W": 52,
    "1M": 12,
}


def timeframe_to_ms(timeframe: str, *, default: Optional[int] = None) -> int:
    """把 timeframe 转为毫秒；未知值回退到 default 或 DEFAULT_TIMEFRAME。"""
    ms = TIMEFRAME_TO_MS.get(timeframe)
    if ms is not None:
        return ms
    if default is not None:
        return default
    return TIMEFRAME_TO_MS[DEFAULT_TIMEFRAME]


def candles_per_day(timeframe: str, *, default: Optional[float] = None) -> float:
    """估算某 timeframe 每天约有多少根 K 线（用于回测拉取数量等场景）。"""
    ms = TIMEFRAME_TO_MS.get(timeframe)
    if ms is None:
        if default is not None:
            return default
        ms = TIMEFRAME_TO_MS[DEFAULT_TIMEFRAME]
    return _DAY_MS / ms


def calculate_candle_count(*, timeframe: str, days: int, min_candles: int = 100) -> int:
    """
    根据 timeframe 和天数估算需要的 K 线数量。

    说明：
    - 保持项目既有默认：最少拉取 100 根，避免指标/策略“冷启动”样本不足。
    """
    d = max(int(days), 1)
    per_day = candles_per_day(timeframe)
    return max(int(d * per_day), int(min_candles))


def periods_per_year(timeframe: str, *, default: float = 365) -> float:
    """根据 timeframe 返回年化周期数（用于 Sharpe/Sortino 等年化计算）。"""
    return _PERIODS_PER_YEAR.get(timeframe, default)

