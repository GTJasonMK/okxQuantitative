# 风险指标计算模块
# 提供 VaR、Sharpe/Sortino、最大回撤、滚动指标等量化风险计算
# 从 backtest/metrics.py 提取共享计算逻辑，避免重复

import math
from typing import Any, Dict, List, Optional, Tuple


def safe_float(value: float) -> float:
    """将 inf/nan 转换为安全的有限浮点数"""
    if math.isinf(value):
        return 9999.99 if value > 0 else -9999.99
    if math.isnan(value):
        return 0.0
    return value


def calculate_returns(equities: List[float]) -> List[float]:
    """
    从权益序列计算收益率序列。

    Args:
        equities: 权益曲线（如每日净值）

    Returns:
        收益率列表（长度 = len(equities) - 1）
    """
    if len(equities) < 2:
        return []
    return [
        (equities[i] - equities[i - 1]) / equities[i - 1]
        for i in range(1, len(equities))
        if equities[i - 1] != 0
    ]


def calculate_sharpe_ratio(
    returns: List[float],
    risk_free_rate: float = 0.0,
    periods_per_year: float = 365,
) -> float:
    """
    计算夏普比率。

    Args:
        returns: 收益率序列
        risk_free_rate: 无风险利率（年化）
        periods_per_year: 每年的周期数
    """
    if len(returns) < 2:
        return 0.0

    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_return = math.sqrt(variance)

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
    """
    计算索提诺比率（仅考虑下行风险）。
    """
    if len(returns) < 2:
        return 0.0

    mean_return = sum(returns) / len(returns)
    negative_returns = [r for r in returns if r < 0]
    if not negative_returns:
        return safe_float(float("inf") if mean_return > 0 else 0.0)

    downside_variance = sum(r ** 2 for r in negative_returns) / len(returns)
    downside_std = math.sqrt(downside_variance)

    if downside_std == 0:
        return 0.0

    annualized_return = mean_return * periods_per_year
    annualized_downside_std = downside_std * math.sqrt(periods_per_year)

    return safe_float((annualized_return - risk_free_rate) / annualized_downside_std)


def calculate_max_drawdown(equities: List[float]) -> Tuple[float, int]:
    """
    计算最大回撤。

    Returns:
        (最大回撤百分比, 最大回撤持续周期数)
    """
    if not equities:
        return 0.0, 0

    peak = equities[0]
    max_dd = 0.0
    max_dd_duration = 0
    current_dd_start = 0
    in_drawdown = False

    for i, equity in enumerate(equities):
        if equity > peak:
            peak = equity
            if in_drawdown:
                duration = i - current_dd_start
                max_dd_duration = max(max_dd_duration, duration)
                in_drawdown = False
        else:
            if not in_drawdown:
                current_dd_start = i
                in_drawdown = True
            drawdown = (peak - equity) / peak * 100 if peak > 0 else 0
            max_dd = max(max_dd, drawdown)

    if in_drawdown:
        duration = len(equities) - current_dd_start
        max_dd_duration = max(max_dd_duration, duration)

    return max_dd, max_dd_duration


def calculate_max_drawdown_series(equities: List[float]) -> Dict[str, Any]:
    """
    计算回撤时序数据，用于可视化。

    Returns:
        {
            "drawdown_series": 每期回撤百分比列表,
            "max_drawdown": 最大回撤百分比,
            "max_drawdown_duration": 最大回撤持续期数,
            "current_drawdown": 当前回撤百分比,
            "peak": 历史最高值,
        }
    """
    if not equities:
        return {
            "drawdown_series": [],
            "max_drawdown": 0.0,
            "max_drawdown_duration": 0,
            "current_drawdown": 0.0,
            "peak": 0.0,
        }

    peak = equities[0]
    drawdown_series: List[float] = []

    for equity in equities:
        if equity > peak:
            peak = equity
        dd = (peak - equity) / peak * 100 if peak > 0 else 0
        drawdown_series.append(round(dd, 4))

    max_dd, max_dd_dur = calculate_max_drawdown(equities)
    current_dd = drawdown_series[-1] if drawdown_series else 0.0

    return {
        "drawdown_series": drawdown_series,
        "max_drawdown": round(max_dd, 4),
        "max_drawdown_duration": max_dd_dur,
        "current_drawdown": round(current_dd, 4),
        "peak": peak,
    }


def calculate_historical_var(
    returns: List[float],
    confidence: float = 0.95,
    holding_period: int = 1,
) -> float:
    """
    历史模拟法计算 VaR（Value at Risk）。

    Args:
        returns: 收益率序列
        confidence: 置信水平（如 0.95 表示 95%）
        holding_period: 持有期（天数）

    Returns:
        VaR 值（正数，表示最大预期损失百分比）
    """
    if len(returns) < 10:
        return 0.0

    sorted_returns = sorted(returns)
    index = int(len(sorted_returns) * (1 - confidence))
    index = max(0, min(index, len(sorted_returns) - 1))

    var_1d = abs(sorted_returns[index])
    # 多日 VaR 按根号时间缩放
    return round(var_1d * math.sqrt(holding_period) * 100, 4)


def calculate_parametric_var(
    returns: List[float],
    confidence: float = 0.95,
) -> float:
    """
    参数法（正态假设）计算 VaR。
    """
    if len(returns) < 10:
        return 0.0

    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_return = math.sqrt(variance)

    # 正态分布分位数映射
    z_scores = {0.90: 1.282, 0.95: 1.645, 0.99: 2.326}
    z = z_scores.get(confidence, 1.645)

    var_value = abs(mean_return - z * std_return)
    return round(var_value * 100, 4)


def calculate_rolling_metrics(
    returns: List[float],
    window: int = 30,
    periods_per_year: float = 365,
) -> Dict[str, List[Optional[float]]]:
    """
    计算滚动风险指标。

    Returns:
        {
            "rolling_sharpe": 滚动夏普比率,
            "rolling_volatility": 滚动波动率（年化），
            "rolling_var_95": 滚动 95% VaR,
        }
    """
    n = len(returns)
    rolling_sharpe: List[Optional[float]] = [None] * n
    rolling_vol: List[Optional[float]] = [None] * n
    rolling_var: List[Optional[float]] = [None] * n

    for i in range(window - 1, n):
        window_returns = returns[i - window + 1: i + 1]
        rolling_sharpe[i] = round(
            calculate_sharpe_ratio(window_returns, periods_per_year=periods_per_year), 4
        )

        mean_r = sum(window_returns) / len(window_returns)
        var_r = sum((r - mean_r) ** 2 for r in window_returns) / len(window_returns)
        annual_vol = math.sqrt(var_r) * math.sqrt(periods_per_year) * 100
        rolling_vol[i] = round(annual_vol, 4)

        rolling_var[i] = round(
            calculate_historical_var(window_returns, confidence=0.95), 4
        )

    return {
        "rolling_sharpe": rolling_sharpe,
        "rolling_volatility": rolling_vol,
        "rolling_var_95": rolling_var,
    }


def calculate_calmar_ratio(annual_return: float, max_drawdown: float) -> float:
    """计算卡尔玛比率。"""
    if max_drawdown == 0:
        return 0.0
    return safe_float(annual_return / max_drawdown)
