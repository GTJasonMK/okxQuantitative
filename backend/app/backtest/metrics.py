# 回测评估指标计算
# 计算各种绩效指标：收益率、夏普比率、最大回撤等
# 核心计算已向量化为 numpy 操作，避免纯 Python 循环

from typing import List, Optional
import math
import numpy as np

from .engine import BacktestResult, AccountState
from ..strategies.base import Trade, OrderSide
from ..utils.timeframes import periods_per_year as get_periods_per_year
from ..utils.numbers import safe_float_finite as _safe_float


def calculate_metrics(result: BacktestResult) -> None:
    """计算回测绩效指标（原地修改result对象）"""
    if not result.equity_curve:
        return

    equities = np.array([s.total_equity for s in result.equity_curve], dtype=np.float64)

    actual_days = result.duration_days
    if len(result.equity_curve) >= 2:
        first_ts = result.equity_curve[0].timestamp
        last_ts = result.equity_curve[-1].timestamp
        actual_days = max(1, (last_ts - first_ts) / (1000 * 86400))

    result.final_capital = float(equities[-1]) if equities.size > 0 else result.initial_capital
    result.total_return = _calculate_total_return(result.initial_capital, result.final_capital)
    result.annual_return = _calculate_annual_return(result.total_return, actual_days)

    result.max_drawdown, result.max_drawdown_duration = _calculate_max_drawdown(equities)

    periods_per_year = get_periods_per_year(result.timeframe)

    returns = _calculate_returns(equities)
    result.sharpe_ratio = _safe_float(_calculate_sharpe_ratio(returns, periods_per_year=periods_per_year))
    result.sortino_ratio = _safe_float(_calculate_sortino_ratio(returns, periods_per_year=periods_per_year))
    result.calmar_ratio = _safe_float(_calculate_calmar_ratio(result.annual_return, result.max_drawdown))

    _calculate_trade_stats(result)


def _calculate_total_return(initial: float, final: float) -> float:
    if initial <= 0:
        return 0.0
    return (final - initial) / initial * 100


def _calculate_annual_return(total_return: float, days: float) -> float:
    if days <= 0:
        return 0.0
    years = days / 365
    if years <= 0:
        return total_return
    total_ratio = 1 + total_return / 100
    if total_ratio <= 0:
        return -100.0
    return (total_ratio ** (1 / years) - 1) * 100


def _calculate_returns(equities: np.ndarray) -> np.ndarray:
    """numpy 向量化收益率计算 — O(n) 单次数组操作替代 Python 循环"""
    if equities.size < 2:
        return np.array([], dtype=np.float64)
    prev = equities[:-1]
    mask = prev > 0
    returns = np.zeros(prev.size, dtype=np.float64)
    returns[mask] = (equities[1:][mask] - prev[mask]) / prev[mask]
    return returns


def _calculate_max_drawdown(equities: np.ndarray) -> tuple:
    """numpy 向量化最大回撤 — cummax 避免逐元素 Python 循环"""
    if equities.size == 0:
        return 0.0, 0

    running_max = np.maximum.accumulate(equities)
    drawdown_pct = np.where(running_max > 0, (running_max - equities) / running_max * 100, 0.0)
    max_dd = float(np.max(drawdown_pct))

    # 回撤持续时间：找最长的连续回撤段
    in_drawdown = equities < running_max
    max_dd_duration = 0
    current_duration = 0
    for flag in in_drawdown:
        if flag:
            current_duration += 1
            max_dd_duration = max(max_dd_duration, current_duration)
        else:
            current_duration = 0

    return max_dd, max_dd_duration


def _calculate_sharpe_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.0,
    periods_per_year: float = 365
) -> float:
    """numpy 向量化夏普比率"""
    if returns.size < 2:
        return 0.0

    mean_return = float(np.mean(returns))
    std_return = float(np.std(returns, ddof=0))

    if std_return == 0:
        return 0.0

    annualized_return = mean_return * periods_per_year
    annualized_std = std_return * math.sqrt(periods_per_year)
    return (annualized_return - risk_free_rate) / annualized_std


def _calculate_sortino_ratio(
    returns: np.ndarray,
    risk_free_rate: float = 0.0,
    periods_per_year: float = 365
) -> float:
    """numpy 向量化索提诺比率"""
    if returns.size < 2:
        return 0.0

    mean_return = float(np.mean(returns))
    negative_returns = returns[returns < 0]

    if negative_returns.size == 0:
        return float('inf') if mean_return > 0 else 0.0

    downside_variance = float(np.sum(negative_returns ** 2)) / returns.size
    downside_std = math.sqrt(downside_variance)

    if downside_std == 0:
        return 0.0

    annualized_return = mean_return * periods_per_year
    annualized_downside_std = downside_std * math.sqrt(periods_per_year)
    return (annualized_return - risk_free_rate) / annualized_downside_std


def _calculate_calmar_ratio(annual_return: float, max_drawdown: float) -> float:
    if max_drawdown == 0:
        return 0.0
    return annual_return / max_drawdown


def _calculate_trade_stats(result: BacktestResult) -> None:
    """计算交易统计指标"""
    trades = result.trades
    if not trades:
        return

    sell_trades = [t for t in trades if t.side == OrderSide.SELL]
    result.total_trades = len(sell_trades)
    if result.total_trades == 0:
        return

    pnl_array = np.array([t.pnl for t in sell_trades], dtype=np.float64)
    winning_mask = pnl_array > 0
    losing_mask = pnl_array < 0

    result.winning_trades = int(np.count_nonzero(winning_mask))
    result.losing_trades = int(np.count_nonzero(losing_mask))
    result.win_rate = result.winning_trades / result.total_trades * 100

    if result.winning_trades > 0:
        winning_pnl = pnl_array[winning_mask]
        result.avg_profit = float(np.mean(winning_pnl))
        result.largest_profit = float(np.max(winning_pnl))

    if result.losing_trades > 0:
        losing_pnl = pnl_array[losing_mask]
        result.avg_loss = float(np.mean(np.abs(losing_pnl)))
        result.largest_loss = float(np.max(np.abs(losing_pnl)))

    total_profit = float(np.sum(pnl_array[winning_mask])) if result.winning_trades > 0 else 0
    total_loss = float(np.sum(np.abs(pnl_array[losing_mask]))) if result.losing_trades > 0 else 0
    result.profit_factor = _safe_float(total_profit / total_loss if total_loss > 0 else float('inf'))

    commission_array = np.array([t.commission for t in trades], dtype=np.float64)
    result.total_commission = float(np.sum(commission_array))

    if result.total_trades > 0:
        result.avg_holding_period = len(result.equity_curve) / result.total_trades


def calculate_single_metric(
    metric_name: str,
    equities: List[float] = None,
    returns: List[float] = None,
    trades: List[Trade] = None,
) -> float:
    metric_name = metric_name.lower()

    if metric_name == "sharpe" and returns:
        return _calculate_sharpe_ratio(np.array(returns, dtype=np.float64))

    if metric_name == "sortino" and returns:
        return _calculate_sortino_ratio(np.array(returns, dtype=np.float64))

    if metric_name == "max_drawdown" and equities:
        dd, _ = _calculate_max_drawdown(np.array(equities, dtype=np.float64))
        return dd

    if metric_name == "win_rate" and trades:
        sell_trades = [t for t in trades if t.side == OrderSide.SELL]
        if not sell_trades:
            return 0.0
        winning = len([t for t in sell_trades if t.pnl > 0])
        return winning / len(sell_trades) * 100

    return 0.0
