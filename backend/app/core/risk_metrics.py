# 风险指标计算模块
# 提供 VaR、Sharpe/Sortino、最大回撤、滚动指标等量化风险计算
# 核心计算已向量化为 numpy 操作

import math
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

from ..utils.numbers import safe_float_finite as safe_float


def calculate_returns(equities: List[float]) -> List[float]:
    """numpy 向量化收益率计算"""
    if len(equities) < 2:
        return []
    arr = np.array(equities, dtype=np.float64)
    prev = arr[:-1]
    mask = prev != 0
    returns = np.zeros(prev.size, dtype=np.float64)
    returns[mask] = (arr[1:][mask] - prev[mask]) / prev[mask]
    return returns.tolist()


def calculate_sharpe_ratio(
    returns: List[float],
    risk_free_rate: float = 0.0,
    periods_per_year: float = 365,
) -> float:
    """numpy 向量化夏普比率"""
    arr = np.array(returns, dtype=np.float64) if not isinstance(returns, np.ndarray) else returns
    if arr.size < 2:
        return 0.0

    mean_return = float(np.mean(arr))
    std_return = float(np.std(arr, ddof=0))

    if std_return == 0:
        return 0.0

    annualized_return = mean_return * periods_per_year
    annualized_std = std_return * math.sqrt(periods_per_year)
    return safe_float((annualized_return - risk_free_rate) / annualized_std)


def calculate_sortino_ratio(
    returns: List[float],
    risk_free_rate: float = 0.0,
    periods_per_year: float = 365,
) -> float:
    """numpy 向量化索提诺比率"""
    arr = np.array(returns, dtype=np.float64) if not isinstance(returns, np.ndarray) else returns
    if arr.size < 2:
        return 0.0

    mean_return = float(np.mean(arr))
    negative = arr[arr < 0]
    if negative.size == 0:
        return safe_float(float("inf") if mean_return > 0 else 0.0)

    downside_variance = float(np.sum(negative ** 2)) / arr.size
    downside_std = math.sqrt(downside_variance)

    if downside_std == 0:
        return 0.0

    annualized_return = mean_return * periods_per_year
    annualized_downside_std = downside_std * math.sqrt(periods_per_year)
    return safe_float((annualized_return - risk_free_rate) / annualized_downside_std)


def calculate_max_drawdown(equities: List[float]) -> Tuple[float, int]:
    """numpy 向量化最大回撤"""
    arr = np.array(equities, dtype=np.float64) if not isinstance(equities, np.ndarray) else equities
    if arr.size == 0:
        return 0.0, 0

    running_max = np.maximum.accumulate(arr)
    dd_pct = np.where(running_max > 0, (running_max - arr) / running_max * 100, 0.0)
    max_dd = float(np.max(dd_pct))

    # 回撤持续时间
    in_drawdown = arr < running_max
    max_dd_duration = 0
    current_duration = 0
    for flag in in_drawdown:
        if flag:
            current_duration += 1
            max_dd_duration = max(max_dd_duration, current_duration)
        else:
            current_duration = 0

    return max_dd, max_dd_duration


def calculate_max_drawdown_series(equities: List[float]) -> Dict[str, Any]:
    """numpy 向量化回撤时序"""
    arr = np.array(equities, dtype=np.float64) if not isinstance(equities, np.ndarray) else equities
    if arr.size == 0:
        return {
            "drawdown_series": [],
            "max_drawdown": 0.0,
            "max_drawdown_duration": 0,
            "current_drawdown": 0.0,
            "peak": 0.0,
        }

    running_max = np.maximum.accumulate(arr)
    dd_series = np.where(running_max > 0, (running_max - arr) / running_max * 100, 0.0)

    max_dd, max_dd_dur = calculate_max_drawdown(arr)

    return {
        "drawdown_series": np.round(dd_series, 4).tolist(),
        "max_drawdown": round(max_dd, 4),
        "max_drawdown_duration": max_dd_dur,
        "current_drawdown": round(float(dd_series[-1]), 4),
        "peak": float(running_max[-1]),
    }


def calculate_historical_var(
    returns: List[float],
    confidence: float = 0.95,
    holding_period: int = 1,
) -> float:
    """numpy 向量化历史 VaR"""
    arr = np.array(returns, dtype=np.float64) if not isinstance(returns, np.ndarray) else returns
    if arr.size < 10:
        return 0.0

    sorted_returns = np.sort(arr)
    index = max(0, min(int(arr.size * (1 - confidence)), arr.size - 1))
    var_1d = abs(float(sorted_returns[index]))
    return round(var_1d * math.sqrt(holding_period) * 100, 4)


def calculate_parametric_var(
    returns: List[float],
    confidence: float = 0.95,
) -> float:
    """numpy 向量化参数法 VaR"""
    arr = np.array(returns, dtype=np.float64) if not isinstance(returns, np.ndarray) else returns
    if arr.size < 10:
        return 0.0

    mean_return = float(np.mean(arr))
    std_return = float(np.std(arr, ddof=0))

    z_scores = {0.90: 1.282, 0.95: 1.645, 0.99: 2.326}
    z = z_scores.get(confidence, 1.645)

    var_value = abs(mean_return - z * std_return)
    return round(var_value * 100, 4)


def calculate_rolling_metrics(
    returns: List[float],
    window: int = 30,
    periods_per_year: float = 365,
) -> Dict[str, List[Optional[float]]]:
    """numpy 向量化滚动风险指标"""
    arr = np.array(returns, dtype=np.float64) if not isinstance(returns, np.ndarray) else returns
    n = arr.size
    rolling_sharpe: List[Optional[float]] = [None] * n
    rolling_vol: List[Optional[float]] = [None] * n
    rolling_var: List[Optional[float]] = [None] * n

    if n < window:
        return {
            "rolling_sharpe": rolling_sharpe,
            "rolling_volatility": rolling_vol,
            "rolling_var_95": rolling_var,
        }

    # 滑动窗口预计算 — 避免每步重新切片
    # 用 cumsum 实现 O(1) 窗口均值和方差
    cumsum = np.concatenate([[0.0], np.cumsum(arr)])
    cumsq = np.concatenate([[0.0], np.cumsum(arr ** 2)])

    for i in range(window - 1, n):
        start = i - window + 1
        w_sum = cumsum[i + 1] - cumsum[start]
        w_sq_sum = cumsq[i + 1] - cumsq[start]
        w_mean = w_sum / window
        w_var = max(w_sq_sum / window - w_mean * w_mean, 0.0)
        w_std = math.sqrt(w_var)

        # Sharpe
        if w_std > 0:
            ann_ret = w_mean * periods_per_year
            ann_std = w_std * math.sqrt(periods_per_year)
            rolling_sharpe[i] = round(safe_float(ann_ret / ann_std), 4)
        else:
            rolling_sharpe[i] = 0.0

        # Volatility
        rolling_vol[i] = round(w_std * math.sqrt(periods_per_year) * 100, 4)

        # VaR — 窗口内排序
        w_slice = arr[start:i + 1]
        rolling_var[i] = round(calculate_historical_var(w_slice, confidence=0.95), 4)

    return {
        "rolling_sharpe": rolling_sharpe,
        "rolling_volatility": rolling_vol,
        "rolling_var_95": rolling_var,
    }


def calculate_calmar_ratio(annual_return: float, max_drawdown: float) -> float:
    if max_drawdown == 0:
        return 0.0
    return safe_float(annual_return / max_drawdown)
