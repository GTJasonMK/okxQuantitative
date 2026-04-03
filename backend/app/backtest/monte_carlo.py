# 蒙特卡洛模拟模块
# 通过重采样交易序列评估策略鲁棒性

import math
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class MonteCarloConfig:
    """蒙特卡洛配置"""
    num_simulations: int = 1000
    confidence_levels: tuple = (0.05, 0.25, 0.50, 0.75, 0.95)
    seed: Optional[int] = None


@dataclass
class MonteCarloResult:
    """蒙特卡洛模拟结果"""
    num_simulations: int
    original_final_equity: float
    original_max_drawdown: float
    # 置信区间
    equity_percentiles: Dict[str, float]     # {"5%": ..., "25%": ..., etc.}
    drawdown_percentiles: Dict[str, float]
    # 统计
    mean_final_equity: float
    std_final_equity: float
    median_final_equity: float
    prob_profit: float           # 正收益概率
    prob_original_beat: float    # 超越原始收益的概率
    worst_case_equity: float
    best_case_equity: float


class MonteCarloSimulator:
    """
    蒙特卡洛模拟器。

    方法：交易序列重采样（Bootstrap）
    - 从原始回测的交易盈亏序列中有放回抽样
    - 重新计算权益曲线和最大回撤
    - 输出分布统计和置信区间
    """

    def run(
        self,
        trade_pnls: List[float],
        initial_capital: float,
        config: MonteCarloConfig,
    ) -> MonteCarloResult:
        """
        执行蒙特卡洛模拟。

        Args:
            trade_pnls: 原始回测的每笔交易盈亏列表
            initial_capital: 初始资金
            config: 模拟配置

        Returns:
            MonteCarloResult
        """
        if not trade_pnls:
            return MonteCarloResult(
                num_simulations=0,
                original_final_equity=initial_capital,
                original_max_drawdown=0,
                equity_percentiles={},
                drawdown_percentiles={},
                mean_final_equity=initial_capital,
                std_final_equity=0,
                median_final_equity=initial_capital,
                prob_profit=0,
                prob_original_beat=0,
                worst_case_equity=initial_capital,
                best_case_equity=initial_capital,
            )

        rng = random.Random(config.seed)
        n_trades = len(trade_pnls)

        # 原始结果
        original_equity = self._build_equity(trade_pnls, initial_capital)
        original_final = original_equity[-1]
        original_dd = self._max_drawdown(original_equity)

        # 模拟
        final_equities: List[float] = []
        max_drawdowns: List[float] = []

        for _ in range(config.num_simulations):
            # 有放回抽样
            sampled = [rng.choice(trade_pnls) for _ in range(n_trades)]
            equity = self._build_equity(sampled, initial_capital)
            final_equities.append(equity[-1])
            max_drawdowns.append(self._max_drawdown(equity))

        final_equities.sort()
        max_drawdowns.sort()

        # 百分位数
        equity_pcts = {}
        dd_pcts = {}
        for level in config.confidence_levels:
            idx = max(0, min(int(level * len(final_equities)), len(final_equities) - 1))
            key = f"{int(level * 100)}%"
            equity_pcts[key] = round(final_equities[idx], 2)
            dd_pcts[key] = round(max_drawdowns[idx], 4)

        mean_eq = sum(final_equities) / len(final_equities)
        variance = sum((e - mean_eq) ** 2 for e in final_equities) / len(final_equities)
        std_eq = math.sqrt(variance)
        median_idx = len(final_equities) // 2
        median_eq = final_equities[median_idx]
        prob_profit = sum(1 for e in final_equities if e > initial_capital) / len(final_equities)
        prob_beat = sum(1 for e in final_equities if e >= original_final) / len(final_equities)

        return MonteCarloResult(
            num_simulations=config.num_simulations,
            original_final_equity=round(original_final, 2),
            original_max_drawdown=round(original_dd, 4),
            equity_percentiles=equity_pcts,
            drawdown_percentiles=dd_pcts,
            mean_final_equity=round(mean_eq, 2),
            std_final_equity=round(std_eq, 2),
            median_final_equity=round(median_eq, 2),
            prob_profit=round(prob_profit, 4),
            prob_original_beat=round(prob_beat, 4),
            worst_case_equity=round(final_equities[0], 2),
            best_case_equity=round(final_equities[-1], 2),
        )

    @staticmethod
    def _build_equity(pnls: List[float], initial_capital: float) -> List[float]:
        """从盈亏序列构建权益曲线"""
        equity = [initial_capital]
        current = initial_capital
        for pnl in pnls:
            current += pnl
            equity.append(current)
        return equity

    @staticmethod
    def _max_drawdown(equity: List[float]) -> float:
        """计算最大回撤百分比"""
        if not equity:
            return 0.0
        peak = equity[0]
        max_dd = 0.0
        for val in equity:
            if val > peak:
                peak = val
            if peak > 0:
                dd = (peak - val) / peak * 100
                max_dd = max(max_dd, dd)
        return max_dd
