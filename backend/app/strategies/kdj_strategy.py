# KDJ随机指标策略
# 基于KDJ(随机指标)的超买超卖和金叉死叉交易策略
# 参考资料: https://market-bulls.com/kdj-indicator/

from typing import List, Dict, Any
from dataclasses import dataclass
import math

from pydantic import BaseModel, Field

from .base import BaseStrategy, StrategyConfig, Signal, SignalType
from ..core.indicators import kdj, sma


class KDJParams(BaseModel):
    """KDJ策略参数 Schema"""
    n_period: int = Field(
        default=9, ge=3, le=30,
        json_schema_extra={"label": "RSV周期", "order": 1}
    )
    m1: int = Field(
        default=3, ge=2, le=10,
        json_schema_extra={"label": "K平滑周期", "order": 2}
    )
    m2: int = Field(
        default=3, ge=2, le=10,
        json_schema_extra={"label": "D平滑周期", "order": 3}
    )
    overbought: int = Field(
        default=80, ge=60, le=100,
        json_schema_extra={"label": "超买阈值", "order": 4}
    )
    oversold: int = Field(
        default=20, ge=0, le=40,
        json_schema_extra={"label": "超卖阈值", "order": 5}
    )
    use_j_line: bool = Field(
        default=True,
        json_schema_extra={"label": "使用J线确认", "order": 6}
    )
    j_overbought: int = Field(
        default=100, ge=80, le=150,
        json_schema_extra={"label": "J线超买阈值", "order": 7}
    )
    j_oversold: int = Field(
        default=0, ge=-50, le=20,
        json_schema_extra={"label": "J线超卖阈值", "order": 8}
    )


@dataclass
class KDJConfig(StrategyConfig):
    """KDJ策略配置"""
    name: str = "KDJ策略"
    # KDJ参数
    n_period: int = 9              # RSV计算周期
    m1: int = 3                     # K值平滑周期
    m2: int = 3                     # D值平滑周期
    # 超买超卖阈值
    overbought: int = 80            # K/D超买阈值
    oversold: int = 20              # K/D超卖阈值
    # J线参数
    use_j_line: bool = True         # 是否使用J线确认
    j_overbought: int = 100         # J线超买阈值
    j_oversold: int = 0             # J线超卖阈值


class KDJStrategy(BaseStrategy):
    """
    KDJ随机指标策略

    交易逻辑：
    - 买入：K线在超卖区域上穿D线（金叉），或K/D均在超卖区域
    - 卖出：K线在超买区域下穿D线（死叉），或K/D均在超买区域

    J线确认（可选）：
    - J线 < 0 时的金叉信号更强
    - J线 > 100 时的死叉信号更强

    信号强度评估：
    - 超卖区域金叉（K,D < 20）：强买入信号
    - 超买区域死叉（K,D > 80）：强卖出信号
    - 中性区域交叉：弱信号

    适用场景：短线交易，震荡行情中的超买超卖机会
    """

    strategy_id = "kdj"
    strategy_name = "KDJ策略"
    strategy_description = "基于KDJ随机指标的短线超买超卖策略，适合震荡行情"
    params_schema = KDJParams

    def __init__(self, config: KDJConfig):
        super().__init__(config)
        self.kdj_config = config

    @classmethod
    def create_instance(
        cls,
        symbol: str = "BTC-USDT",
        timeframe: str = "1H",
        initial_capital: float = 10000,
        position_size: float = 0.5,
        stop_loss: float = 0.05,
        take_profit: float = 0.10,
        inst_type: str = "SPOT",
        **strategy_params
    ) -> "KDJStrategy":
        """工厂方法：创建策略实例"""
        params = KDJParams(**strategy_params)

        config = KDJConfig(
            symbol=symbol,
            timeframe=timeframe,
            inst_type=inst_type,
            initial_capital=initial_capital,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            n_period=params.n_period,
            m1=params.m1,
            m2=params.m2,
            overbought=params.overbought,
            oversold=params.oversold,
            use_j_line=params.use_j_line,
            j_overbought=params.j_overbought,
            j_oversold=params.j_oversold,
        )
        return cls(config)

    @classmethod
    def validate_params(cls, params: Dict[str, Any]) -> None:
        """验证策略参数"""
        validated = KDJParams(**params)
        if validated.overbought <= validated.oversold:
            raise ValueError("超买阈值必须大于超卖阈值")

    def calculate_indicators(self, candles: List) -> Dict[str, List[float]]:
        """计算KDJ指标"""
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]
        closes = [c.close for c in candles]

        k, d, j = kdj(
            highs,
            lows,
            closes,
            self.kdj_config.n_period,
            self.kdj_config.m1,
            self.kdj_config.m2,
        )

        indicators = {
            "k": k,
            "d": d,
            "j": j,
        }

        return indicators

    def _get_signal_strength(self, k: float, d: float, j: float, is_buy: bool) -> float:
        """
        计算信号强度

        Args:
            k: K值
            d: D值
            j: J值
            is_buy: 是否为买入信号

        Returns:
            信号强度 (0-1)
        """
        strength = 0.5

        if is_buy:
            # 买入信号强度
            # K/D越低，信号越强
            if k < self.kdj_config.oversold and d < self.kdj_config.oversold:
                strength = 0.85
            elif k < 30 or d < 30:
                strength = 0.7
            else:
                strength = 0.5

            # J线确认
            if self.kdj_config.use_j_line and j is not None:
                if j < self.kdj_config.j_oversold:
                    strength = min(strength + 0.1, 1.0)
        else:
            # 卖出信号强度
            # K/D越高，信号越强
            if k > self.kdj_config.overbought and d > self.kdj_config.overbought:
                strength = 0.85
            elif k > 70 or d > 70:
                strength = 0.7
            else:
                strength = 0.5

            # J线确认
            if self.kdj_config.use_j_line and j is not None:
                if j > self.kdj_config.j_overbought:
                    strength = min(strength + 0.1, 1.0)

        return strength

    def generate_signal(self, index: int) -> Signal:
        """生成交易信号"""
        candle = self.get_candle(index)
        if not candle:
            return Signal(type=SignalType.HOLD, price=0, timestamp=0)

        k = self.get_indicator("k", index)
        k_prev = self.get_indicator("k", index - 1)
        d = self.get_indicator("d", index)
        d_prev = self.get_indicator("d", index - 1)
        j = self.get_indicator("j", index)

        # 数据不足
        if None in [k, k_prev, d, d_prev]:
            return Signal(
                type=SignalType.HOLD,
                price=candle.close,
                timestamp=candle.timestamp,
                reason="KDJ数据不足"
            )

        # 金叉信号：K线上穿D线
        if k_prev <= d_prev and k > d:
            if self.position.is_empty:
                strength = self._get_signal_strength(k, d, j, is_buy=True)
                reason = f"KDJ金叉: K({k:.2f}) > D({d:.2f})"

                # 超卖区域金叉
                if k < self.kdj_config.oversold or d < self.kdj_config.oversold:
                    reason += " [超卖区域]"

                # J线确认
                if self.kdj_config.use_j_line and j is not None and j < self.kdj_config.j_oversold:
                    reason += f" [J线超卖: {j:.2f}]"

                return Signal(
                    type=SignalType.BUY,
                    price=candle.close,
                    timestamp=candle.timestamp,
                    reason=reason,
                    strength=strength,
                    metadata={
                        "k": k,
                        "d": d,
                        "j": j,
                        "cross_type": "golden",
                    }
                )

        # 死叉信号：K线下穿D线
        if k_prev >= d_prev and k < d:
            if not self.position.is_empty:
                strength = self._get_signal_strength(k, d, j, is_buy=False)
                reason = f"KDJ死叉: K({k:.2f}) < D({d:.2f})"

                # 超买区域死叉
                if k > self.kdj_config.overbought or d > self.kdj_config.overbought:
                    reason += " [超买区域]"

                # J线确认
                if self.kdj_config.use_j_line and j is not None and j > self.kdj_config.j_overbought:
                    reason += f" [J线超买: {j:.2f}]"

                return Signal(
                    type=SignalType.SELL,
                    price=candle.close,
                    timestamp=candle.timestamp,
                    reason=reason,
                    strength=strength,
                    metadata={
                        "k": k,
                        "d": d,
                        "j": j,
                        "cross_type": "death",
                    }
                )

        # J线极端值信号（可选）
        if self.kdj_config.use_j_line and j is not None:
            # J线极端超卖
            if j < self.kdj_config.j_oversold and self.position.is_empty:
                if k > k_prev:  # K线开始上升
                    return Signal(
                        type=SignalType.BUY,
                        price=candle.close,
                        timestamp=candle.timestamp,
                        reason=f"J线极端超卖反转: J={j:.2f}",
                        strength=0.6,
                        metadata={"k": k, "d": d, "j": j, "signal_type": "j_oversold"}
                    )

            # J线极端超买
            if j > self.kdj_config.j_overbought and not self.position.is_empty:
                if k < k_prev:  # K线开始下降
                    return Signal(
                        type=SignalType.SELL,
                        price=candle.close,
                        timestamp=candle.timestamp,
                        reason=f"J线极端超买反转: J={j:.2f}",
                        strength=0.6,
                        metadata={"k": k, "d": d, "j": j, "signal_type": "j_overbought"}
                    )

        return Signal(
            type=SignalType.HOLD,
            price=candle.close,
            timestamp=candle.timestamp,
            reason=f"等待信号 (K: {k:.2f}, D: {d:.2f}, J: {j:.2f})"
        )

    def get_params(self) -> Dict[str, Any]:
        """获取策略参数"""
        params = super().get_params()
        params.update({
            "n_period": self.kdj_config.n_period,
            "m1": self.kdj_config.m1,
            "m2": self.kdj_config.m2,
            "overbought": self.kdj_config.overbought,
            "oversold": self.kdj_config.oversold,
            "use_j_line": self.kdj_config.use_j_line,
        })
        return params


def create_kdj_strategy(
    symbol: str = "BTC-USDT",
    timeframe: str = "1H",
    initial_capital: float = 10000,
    n_period: int = 9,
    m1: int = 3,
    m2: int = 3,
    stop_loss: float = 0.05,
    take_profit: float = 0.10,
    position_size: float = 0.5,
    overbought: int = 80,
    oversold: int = 20,
) -> KDJStrategy:
    """
    创建KDJ策略实例

    Args:
        symbol: 交易对
        timeframe: 时间周期
        initial_capital: 初始资金
        n_period: RSV周期
        m1: K值平滑周期
        m2: D值平滑周期
        stop_loss: 止损比例
        take_profit: 止盈比例
        position_size: 仓位比例
        overbought: 超买阈值
        oversold: 超卖阈值

    Returns:
        KDJ策略实例
    """
    config = KDJConfig(
        symbol=symbol,
        timeframe=timeframe,
        initial_capital=initial_capital,
        n_period=n_period,
        m1=m1,
        m2=m2,
        overbought=overbought,
        oversold=oversold,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_size=position_size,
    )
    return KDJStrategy(config)
