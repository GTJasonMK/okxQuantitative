# 蒙特卡洛模拟模块
# 通过重采样交易序列评估策略鲁棒性
# 核心模拟已向量化为 numpy 矩阵操作

import math
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import numpy as np


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
    equity_percentiles: Dict[str, float]
    drawdown_percentiles: Dict[str, float]
    mean_final_equity: float
    std_final_equity: float
    median_final_equity: float
    prob_profit: float
    prob_original_beat: float
    worst_case_equity: float
    best_case_equity: float


class MonteCarloSimulator:
    """
    蒙特卡洛模拟器 — numpy 向量化。

    将 N 次模拟的有放回抽样、权益曲线构建、最大回撤计算
    全部改为矩阵操作，避免 Python for 循环。
    """

    def run(
        self,
        trade_pnls: List[float],
        initial_capital: float,
        config: MonteCarloConfig,
    ) -> MonteCarloResult:
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

        pnl_arr = np.array(trade_pnls, dtype=np.float64)
        n_trades = pnl_arr.size
        n_sims = config.num_simulations
        rng = np.random.default_rng(config.seed)

        # 原始结果
        original_equity = initial_capital + np.cumsum(pnl_arr)
        original_final = float(original_equity[-1])
        original_dd = self._max_drawdown_np(
            np.concatenate([[initial_capital], initial_capital + np.cumsum(pnl_arr)])
        )

        # 批量模拟 — (n_sims, n_trades) 矩阵一次性抽样
        sample_indices = rng.integers(0, n_trades, size=(n_sims, n_trades))
        sampled_pnls = pnl_arr[sample_indices]  # (n_sims, n_trades)

        # 批量构建权益曲线 — cumsum 沿 axis=1
        equity_curves = initial_capital + np.cumsum(sampled_pnls, axis=1)  # (n_sims, n_trades)
        # 在前面补上 initial_capital 列
        equity_with_init = np.concatenate(
            [np.full((n_sims, 1), initial_capital), equity_curves],
            axis=1,
        )  # (n_sims, n_trades+1)

        # 批量最终权益
        final_equities = equity_curves[:, -1]  # (n_sims,)

        # 批量最大回撤 — 向量化 cummax
        running_max = np.maximum.accumulate(equity_with_init, axis=1)
        dd_pct = np.where(running_max > 0, (running_max - equity_with_init) / running_max * 100, 0.0)
        max_drawdowns = np.max(dd_pct, axis=1)  # (n_sims,)

        # 排序
        sorted_equities = np.sort(final_equities)
        sorted_drawdowns = np.sort(max_drawdowns)

        # 百分位数
        equity_pcts = {}
        dd_pcts = {}
        for level in config.confidence_levels:
            idx = max(0, min(int(level * n_sims), n_sims - 1))
            key = f"{int(level * 100)}%"
            equity_pcts[key] = round(float(sorted_equities[idx]), 2)
            dd_pcts[key] = round(float(sorted_drawdowns[idx]), 4)

        mean_eq = float(np.mean(final_equities))
        std_eq = float(np.std(final_equities, ddof=0))
        median_eq = float(np.median(final_equities))
        prob_profit = float(np.mean(final_equities > initial_capital))
        prob_beat = float(np.mean(final_equities >= original_final))

        return MonteCarloResult(
            num_simulations=n_sims,
            original_final_equity=round(original_final, 2),
            original_max_drawdown=round(original_dd, 4),
            equity_percentiles=equity_pcts,
            drawdown_percentiles=dd_pcts,
            mean_final_equity=round(mean_eq, 2),
            std_final_equity=round(std_eq, 2),
            median_final_equity=round(median_eq, 2),
            prob_profit=round(prob_profit, 4),
            prob_original_beat=round(prob_beat, 4),
            worst_case_equity=round(float(sorted_equities[0]), 2),
            best_case_equity=round(float(sorted_equities[-1]), 2),
        )

    @staticmethod
    def _max_drawdown_np(equity: np.ndarray) -> float:
        """numpy 向量化最大回撤"""
        if equity.size == 0:
            return 0.0
        running_max = np.maximum.accumulate(equity)
        dd = np.where(running_max > 0, (running_max - equity) / running_max * 100, 0.0)
        return float(np.max(dd))
