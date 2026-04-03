# Walk-Forward 分析模块
# 滑动窗口：样本内优化参数 → 样本外验证

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Type

from ..strategies.base import BaseStrategy, StrategyConfig
from .engine import BacktestConfig, BacktestEngine


@dataclass(frozen=True)
class WalkForwardConfig:
    """Walk-Forward 配置"""
    num_windows: int = 5           # 滑动窗口数量
    in_sample_ratio: float = 0.7   # 样本内占比
    anchored: bool = False         # True=锚定（样本内窗口递增），False=滚动


@dataclass
class WindowResult:
    """单个窗口的结果"""
    window_index: int
    is_start: int         # 样本内起始 K 线索引
    is_end: int           # 样本内结束索引
    oos_start: int        # 样本外起始索引
    oos_end: int          # 样本外结束索引
    best_params: Dict[str, Any]
    is_return: float      # 样本内收益率 %
    is_sharpe: float
    oos_return: float     # 样本外收益率 %
    oos_sharpe: float
    oos_max_drawdown: float
    oos_trades: int


@dataclass
class WalkForwardResult:
    """Walk-Forward 分析结果"""
    windows: List[WindowResult]
    total_oos_return: float        # 样本外累计收益率
    avg_oos_return: float
    avg_oos_sharpe: float
    efficiency_ratio: float        # 样本外/样本内收益比
    robustness_score: float        # 0-100


class WalkForwardAnalyzer:
    """
    Walk-Forward 分析器。

    将历史数据分为 N 个窗口，每个窗口内：
    1. 在样本内（IS）数据上遍历参数网格，选出最优参数
    2. 在样本外（OOS）数据上验证该参数的表现
    """

    def __init__(self, strategy_class: Type[BaseStrategy]):
        self._strategy_class = strategy_class

    def run(
        self,
        candles: list,
        param_grid: List[Dict[str, Any]],
        base_config: Dict[str, Any],
        wf_config: WalkForwardConfig,
    ) -> WalkForwardResult:
        """
        执行 Walk-Forward 分析。

        Args:
            candles: 完整 K 线数据
            param_grid: 参数网格（每个元素是一组参数字典）
            base_config: 策略基础配置（symbol, timeframe, initial_capital 等）
            wf_config: WF 配置

        Returns:
            WalkForwardResult
        """
        n = len(candles)
        num_windows = wf_config.num_windows
        if num_windows < 2:
            num_windows = 2

        # 计算窗口边界
        window_size = n // num_windows
        if window_size < 20:
            raise ValueError(f"数据量不足：{n} 根 K 线无法划分 {num_windows} 个有效窗口")

        windows: List[WindowResult] = []

        for w in range(num_windows):
            if wf_config.anchored:
                # 锚定模式：样本内从头开始，逐步扩大
                is_start = 0
                is_end = (w + 1) * window_size
            else:
                # 滚动模式：固定窗口大小
                is_start = w * window_size
                is_end = is_start + int(window_size * wf_config.in_sample_ratio)

            oos_start = is_end
            oos_end = min(is_start + window_size, n) if not wf_config.anchored else min(is_end + int(window_size * (1 - wf_config.in_sample_ratio)), n)

            if oos_start >= oos_end or oos_end - oos_start < 5:
                continue

            is_candles = candles[is_start:is_end]
            oos_candles = candles[oos_start:oos_end]

            # 样本内优化
            best_params, best_is_return, best_is_sharpe = self._optimize_in_sample(
                is_candles, param_grid, base_config
            )

            # 样本外验证
            oos_metrics = self._validate_out_of_sample(
                oos_candles, best_params, base_config
            )

            windows.append(WindowResult(
                window_index=w,
                is_start=is_start,
                is_end=is_end,
                oos_start=oos_start,
                oos_end=oos_end,
                best_params=best_params,
                is_return=round(best_is_return, 4),
                is_sharpe=round(best_is_sharpe, 4),
                oos_return=round(oos_metrics["total_return"], 4),
                oos_sharpe=round(oos_metrics["sharpe_ratio"], 4),
                oos_max_drawdown=round(oos_metrics["max_drawdown"], 4),
                oos_trades=oos_metrics["total_trades"],
            ))

        # 汇总统计
        if not windows:
            return WalkForwardResult(
                windows=[], total_oos_return=0, avg_oos_return=0,
                avg_oos_sharpe=0, efficiency_ratio=0, robustness_score=0,
            )

        total_oos = sum(w.oos_return for w in windows)
        avg_oos = total_oos / len(windows)
        avg_is = sum(w.is_return for w in windows) / len(windows)
        avg_oos_sharpe = sum(w.oos_sharpe for w in windows) / len(windows)
        efficiency = avg_oos / avg_is if avg_is != 0 else 0

        # 鲁棒性评分：OOS 正收益窗口占比 * 效率比
        positive_windows = sum(1 for w in windows if w.oos_return > 0)
        positive_ratio = positive_windows / len(windows)
        robustness = min(positive_ratio * min(abs(efficiency), 1.0) * 100, 100)

        return WalkForwardResult(
            windows=windows,
            total_oos_return=round(total_oos, 4),
            avg_oos_return=round(avg_oos, 4),
            avg_oos_sharpe=round(avg_oos_sharpe, 4),
            efficiency_ratio=round(efficiency, 4),
            robustness_score=round(robustness, 2),
        )

    def _optimize_in_sample(
        self,
        candles: list,
        param_grid: List[Dict[str, Any]],
        base_config: Dict[str, Any],
    ) -> tuple:
        """样本内参数优化，返回 (最优参数, 收益率, 夏普)"""
        best_params = param_grid[0] if param_grid else {}
        best_return = float("-inf")
        best_sharpe = 0.0

        for params in param_grid:
            try:
                result = self._run_single(candles, params, base_config)
                ret = result.get("total_return", 0)
                if ret > best_return:
                    best_return = ret
                    best_sharpe = result.get("sharpe_ratio", 0)
                    best_params = params
            except Exception:
                continue

        return best_params, best_return, best_sharpe

    def _validate_out_of_sample(
        self,
        candles: list,
        params: Dict[str, Any],
        base_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """样本外验证"""
        try:
            return self._run_single(candles, params, base_config)
        except Exception:
            return {"total_return": 0, "sharpe_ratio": 0, "max_drawdown": 0, "total_trades": 0}

    def _run_single(
        self,
        candles: list,
        params: Dict[str, Any],
        base_config: Dict[str, Any],
    ) -> Dict[str, Any]:
        """执行单次回测"""
        strategy = self._strategy_class.create_instance(
            symbol=base_config.get("symbol", "BTC-USDT"),
            timeframe=base_config.get("timeframe", "1H"),
            initial_capital=base_config.get("initial_capital", 10000),
            position_size=base_config.get("position_size", 0.5),
            stop_loss=base_config.get("stop_loss", 0.05),
            take_profit=base_config.get("take_profit", 0.10),
            inst_type=base_config.get("inst_type", "SPOT"),
            **params,
        )
        engine = BacktestEngine(BacktestConfig(
            slippage=base_config.get("slippage", 0.0005),
            commission_rate=base_config.get("commission_rate", 0.001),
        ))
        result = engine.run(strategy, candles)
        return {
            "total_return": result.total_return,
            "sharpe_ratio": result.sharpe_ratio,
            "max_drawdown": result.max_drawdown,
            "total_trades": result.total_trades,
        }
