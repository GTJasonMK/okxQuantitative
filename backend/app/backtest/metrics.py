# 回测评估指标计算
# 计算各种绩效指标：收益率、夏普比率、最大回撤等

from typing import List, Optional
import math

from .engine import BacktestResult, AccountState
from ..strategies.base import Trade, OrderSide
from ..utils.timeframes import periods_per_year as get_periods_per_year


def _safe_float(value: float) -> float:
    """将inf/nan转换为安全的有限浮点数，防止JSON序列化崩溃"""
    if math.isinf(value):
        return 9999.99 if value > 0 else -9999.99
    if math.isnan(value):
        return 0.0
    return value


def calculate_metrics(result: BacktestResult) -> None:
    """
    计算回测绩效指标（原地修改result对象）

    Args:
        result: 回测结果对象
    """
    if not result.equity_curve:
        return

    # 提取权益曲线
    equities = [s.total_equity for s in result.equity_curve]

    # 计算实际天数（从时间戳范围推算，而非K线数量）
    actual_days = result.duration_days
    if len(result.equity_curve) >= 2:
        first_ts = result.equity_curve[0].timestamp
        last_ts = result.equity_curve[-1].timestamp
        actual_days = max(1, (last_ts - first_ts) / (1000 * 86400))

    # 基础指标
    result.final_capital = equities[-1] if equities else result.initial_capital
    result.total_return = _calculate_total_return(result.initial_capital, result.final_capital)
    result.annual_return = _calculate_annual_return(result.total_return, actual_days)

    # 风险指标
    result.max_drawdown, result.max_drawdown_duration = _calculate_max_drawdown(equities)

    # 根据时间周期计算正确的年化周期数
    periods_per_year = get_periods_per_year(result.timeframe)

    # 收益风险比指标
    returns = _calculate_returns(equities)
    result.sharpe_ratio = _safe_float(_calculate_sharpe_ratio(returns, periods_per_year=periods_per_year))
    result.sortino_ratio = _safe_float(_calculate_sortino_ratio(returns, periods_per_year=periods_per_year))
    result.calmar_ratio = _safe_float(_calculate_calmar_ratio(result.annual_return, result.max_drawdown))

    # 交易统计
    _calculate_trade_stats(result)


def _calculate_total_return(initial: float, final: float) -> float:
    """计算总收益率 (%)"""
    if initial <= 0:
        return 0.0
    return (final - initial) / initial * 100


def _calculate_annual_return(total_return: float, days: int) -> float:
    """计算年化收益率 (%)"""
    if days <= 0:
        return 0.0

    # 假设每天一根K线（可根据timeframe调整）
    years = days / 365
    if years <= 0:
        return total_return

    # 年化公式: (1 + r)^(1/years) - 1
    total_ratio = 1 + total_return / 100
    if total_ratio <= 0:
        return -100.0

    annual_ratio = total_ratio ** (1 / years) - 1
    return annual_ratio * 100


def _calculate_returns(equities: List[float]) -> List[float]:
    """计算收益率序列"""
    if len(equities) < 2:
        return []

    returns = []
    for i in range(1, len(equities)):
        if equities[i-1] > 0:
            ret = (equities[i] - equities[i-1]) / equities[i-1]
            returns.append(ret)
    return returns


def _calculate_max_drawdown(equities: List[float]) -> tuple:
    """
    计算最大回撤

    Returns:
        (最大回撤百分比, 最大回撤持续K线数)
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
                if duration > max_dd_duration:
                    max_dd_duration = duration
                in_drawdown = False
        else:
            if not in_drawdown:
                current_dd_start = i
                in_drawdown = True

            drawdown = (peak - equity) / peak * 100
            if drawdown > max_dd:
                max_dd = drawdown

    # 检查最后一段回撤
    if in_drawdown:
        duration = len(equities) - current_dd_start
        if duration > max_dd_duration:
            max_dd_duration = duration

    return max_dd, max_dd_duration


def _calculate_sharpe_ratio(
    returns: List[float],
    risk_free_rate: float = 0.0,
    periods_per_year: float = 365
) -> float:
    """
    计算夏普比率

    Args:
        returns: 收益率序列
        risk_free_rate: 无风险利率（年化）
        periods_per_year: 每年的周期数

    Returns:
        夏普比率
    """
    if len(returns) < 2:
        return 0.0

    # 计算平均收益和标准差
    mean_return = sum(returns) / len(returns)
    variance = sum((r - mean_return) ** 2 for r in returns) / len(returns)
    std_return = math.sqrt(variance)

    if std_return == 0:
        return 0.0

    # 年化
    annualized_return = mean_return * periods_per_year
    annualized_std = std_return * math.sqrt(periods_per_year)

    sharpe = (annualized_return - risk_free_rate) / annualized_std
    return sharpe


def _calculate_sortino_ratio(
    returns: List[float],
    risk_free_rate: float = 0.0,
    periods_per_year: float = 365
) -> float:
    """
    计算索提诺比率（只考虑下行风险）

    Args:
        returns: 收益率序列
        risk_free_rate: 无风险利率
        periods_per_year: 每年的周期数

    Returns:
        索提诺比率
    """
    if len(returns) < 2:
        return 0.0

    mean_return = sum(returns) / len(returns)

    # 计算下行标准差（只考虑负收益）
    negative_returns = [r for r in returns if r < 0]
    if not negative_returns:
        return float('inf') if mean_return > 0 else 0.0

    downside_variance = sum(r ** 2 for r in negative_returns) / len(returns)
    downside_std = math.sqrt(downside_variance)

    if downside_std == 0:
        return 0.0

    # 年化
    annualized_return = mean_return * periods_per_year
    annualized_downside_std = downside_std * math.sqrt(periods_per_year)

    sortino = (annualized_return - risk_free_rate) / annualized_downside_std
    return sortino


def _calculate_calmar_ratio(annual_return: float, max_drawdown: float) -> float:
    """
    计算卡尔玛比率

    Args:
        annual_return: 年化收益率 (%)
        max_drawdown: 最大回撤 (%)

    Returns:
        卡尔玛比率
    """
    if max_drawdown == 0:
        return 0.0

    return annual_return / max_drawdown


def _calculate_trade_stats(result: BacktestResult) -> None:
    """计算交易统计指标"""
    trades = result.trades
    if not trades:
        return

    # 筛选卖出交易（有盈亏的交易）
    sell_trades = [t for t in trades if t.side == OrderSide.SELL]

    result.total_trades = len(sell_trades)
    if result.total_trades == 0:
        return

    # 盈利和亏损交易
    winning = [t for t in sell_trades if t.pnl > 0]
    losing = [t for t in sell_trades if t.pnl < 0]

    result.winning_trades = len(winning)
    result.losing_trades = len(losing)

    # 胜率
    result.win_rate = result.winning_trades / result.total_trades * 100

    # 平均盈亏
    if winning:
        result.avg_profit = sum(t.pnl for t in winning) / len(winning)
        result.largest_profit = max(t.pnl for t in winning)

    if losing:
        result.avg_loss = abs(sum(t.pnl for t in losing) / len(losing))
        result.largest_loss = abs(min(t.pnl for t in losing))

    # 盈亏比 (Profit Factor)
    total_profit = sum(t.pnl for t in winning) if winning else 0
    total_loss = abs(sum(t.pnl for t in losing)) if losing else 0
    result.profit_factor = _safe_float(total_profit / total_loss if total_loss > 0 else float('inf'))

    # 总手续费
    result.total_commission = sum(t.commission for t in trades)

    # 平均持仓周期（简化计算：总K线数 / 交易次数）
    if result.total_trades > 0:
        result.avg_holding_period = len(result.equity_curve) / result.total_trades


def calculate_single_metric(
    metric_name: str,
    equities: List[float] = None,
    returns: List[float] = None,
    trades: List[Trade] = None,
) -> float:
    """
    计算单个指标

    Args:
        metric_name: 指标名称
        equities: 权益曲线
        returns: 收益率序列
        trades: 交易列表

    Returns:
        指标值
    """
    metric_name = metric_name.lower()

    if metric_name == "sharpe" and returns:
        return _calculate_sharpe_ratio(returns)

    if metric_name == "sortino" and returns:
        return _calculate_sortino_ratio(returns)

    if metric_name == "max_drawdown" and equities:
        dd, _ = _calculate_max_drawdown(equities)
        return dd

    if metric_name == "win_rate" and trades:
        sell_trades = [t for t in trades if t.side == OrderSide.SELL]
        if not sell_trades:
            return 0.0
        winning = len([t for t in sell_trades if t.pnl > 0])
        return winning / len(sell_trades) * 100

    return 0.0
