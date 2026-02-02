# MACD交叉策略
# 基于MACD(移动平均收敛散度)指标的趋势跟踪策略
# 参考资料: https://changelly.com/blog/macd-moving-average-convergence-divergence-in-crypto/

from typing import List, Dict, Any
from dataclasses import dataclass
import math

from pydantic import BaseModel, Field

from .base import BaseStrategy, StrategyConfig, Signal, SignalType
from ..core.indicators import macd, ema, sma


class MACDParams(BaseModel):
    """MACD策略参数 Schema"""
    fast_period: int = Field(
        default=12, ge=2, le=50,
        json_schema_extra={"label": "快线周期", "order": 1}
    )
    slow_period: int = Field(
        default=26, ge=5, le=100,
        json_schema_extra={"label": "慢线周期", "order": 2}
    )
    signal_period: int = Field(
        default=9, ge=2, le=30,
        json_schema_extra={"label": "信号线周期", "order": 3}
    )
    use_histogram: bool = Field(
        default=True,
        json_schema_extra={"label": "使用柱状图确认", "order": 4}
    )
    use_zero_line: bool = Field(
        default=False,
        json_schema_extra={"label": "零轴过滤", "order": 5}
    )
    trend_ma_period: int = Field(
        default=200, ge=50, le=500,
        json_schema_extra={"label": "趋势均线周期", "order": 6}
    )
    use_trend_filter: bool = Field(
        default=False,
        json_schema_extra={"label": "趋势均线过滤", "order": 7}
    )


@dataclass
class MACDConfig(StrategyConfig):
    """MACD策略配置"""
    name: str = "MACD策略"
    # MACD参数
    fast_period: int = 12           # 快线EMA周期
    slow_period: int = 26           # 慢线EMA周期
    signal_period: int = 9          # 信号线EMA周期
    # 信号确认
    use_histogram: bool = True      # 使用柱状图确认信号方向
    use_zero_line: bool = False     # 零轴过滤（只在零轴上方做多）
    # 趋势过滤
    trend_ma_period: int = 200      # 趋势均线周期
    use_trend_filter: bool = False  # 是否启用趋势过滤


class MACDStrategy(BaseStrategy):
    """
    MACD交叉策略

    交易逻辑：
    - 买入：DIF上穿DEA（金叉）
    - 卖出：DIF下穿DEA（死叉）或止损/止盈

    可选确认条件：
    - 柱状图确认：金叉时柱状图由负转正
    - 零轴过滤：只在DIF位于零轴上方时做多（强势区域）
    - 趋势过滤：价格在200日均线上方才做多

    适用场景：中长线趋势跟踪，加密货币的大趋势行情
    """

    strategy_id = "macd"
    strategy_name = "MACD策略"
    strategy_description = "基于MACD金叉死叉的趋势跟踪策略，适合中长线趋势行情"
    params_schema = MACDParams

    def __init__(self, config: MACDConfig):
        super().__init__(config)
        self.macd_config = config

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
    ) -> "MACDStrategy":
        """工厂方法：创建策略实例"""
        params = MACDParams(**strategy_params)

        config = MACDConfig(
            symbol=symbol,
            timeframe=timeframe,
            inst_type=inst_type,
            initial_capital=initial_capital,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            fast_period=params.fast_period,
            slow_period=params.slow_period,
            signal_period=params.signal_period,
            use_histogram=params.use_histogram,
            use_zero_line=params.use_zero_line,
            trend_ma_period=params.trend_ma_period,
            use_trend_filter=params.use_trend_filter,
        )
        return cls(config)

    @classmethod
    def validate_params(cls, params: Dict[str, Any]) -> None:
        """验证策略参数"""
        validated = MACDParams(**params)
        if validated.fast_period >= validated.slow_period:
            raise ValueError("快线周期必须小于慢线周期")

    def calculate_indicators(self, candles: List) -> Dict[str, List[float]]:
        """计算MACD指标"""
        closes = [c.close for c in candles]

        dif, dea, hist = macd(
            closes,
            self.macd_config.fast_period,
            self.macd_config.slow_period,
            self.macd_config.signal_period,
        )

        indicators = {
            "dif": dif,
            "dea": dea,
            "histogram": hist,
        }

        # 趋势均线
        if self.macd_config.use_trend_filter:
            indicators["trend_ma"] = ema(closes, self.macd_config.trend_ma_period)

        return indicators

    def generate_signal(self, index: int) -> Signal:
        """生成交易信号"""
        candle = self.get_candle(index)
        if not candle:
            return Signal(type=SignalType.HOLD, price=0, timestamp=0)

        dif = self.get_indicator("dif", index)
        dif_prev = self.get_indicator("dif", index - 1)
        dea = self.get_indicator("dea", index)
        dea_prev = self.get_indicator("dea", index - 1)
        hist = self.get_indicator("histogram", index)
        hist_prev = self.get_indicator("histogram", index - 1)

        # 数据不足
        if None in [dif, dif_prev, dea, dea_prev]:
            return Signal(
                type=SignalType.HOLD,
                price=candle.close,
                timestamp=candle.timestamp,
                reason="MACD数据不足"
            )

        # 趋势过滤
        if self.macd_config.use_trend_filter:
            trend_ma = self.get_indicator("trend_ma", index)
            if trend_ma is not None and candle.close < trend_ma and self.position.is_empty:
                return Signal(
                    type=SignalType.HOLD,
                    price=candle.close,
                    timestamp=candle.timestamp,
                    reason="趋势过滤：价格低于趋势均线"
                )

        # 零轴过滤
        if self.macd_config.use_zero_line:
            if dif < 0 and self.position.is_empty:
                return Signal(
                    type=SignalType.HOLD,
                    price=candle.close,
                    timestamp=candle.timestamp,
                    reason="零轴过滤：DIF位于零轴下方"
                )

        # 金叉信号：DIF上穿DEA
        if dif_prev <= dea_prev and dif > dea:
            if self.position.is_empty:
                reason = f"MACD金叉: DIF({dif:.4f}) > DEA({dea:.4f})"
                strength = 0.7

                # 柱状图确认：由负转正
                if self.macd_config.use_histogram and hist is not None and hist_prev is not None:
                    if hist > 0 and hist_prev <= 0:
                        reason += " [柱状图确认]"
                        strength = 0.85
                    elif hist <= 0:
                        # 柱状图未翻正，降低信号强度
                        strength = 0.5

                # 零轴上方金叉（强信号）
                if dif > 0 and dea > 0:
                    reason += " [零轴上方]"
                    strength = min(strength + 0.1, 1.0)

                return Signal(
                    type=SignalType.BUY,
                    price=candle.close,
                    timestamp=candle.timestamp,
                    reason=reason,
                    strength=strength,
                    metadata={
                        "dif": dif,
                        "dea": dea,
                        "histogram": hist,
                        "cross_type": "golden",
                    }
                )

        # 死叉信号：DIF下穿DEA
        if dif_prev >= dea_prev and dif < dea:
            if not self.position.is_empty:
                reason = f"MACD死叉: DIF({dif:.4f}) < DEA({dea:.4f})"
                strength = 0.7

                # 柱状图确认：由正转负
                if self.macd_config.use_histogram and hist is not None and hist_prev is not None:
                    if hist < 0 and hist_prev >= 0:
                        reason += " [柱状图确认]"
                        strength = 0.85

                # 零轴下方死叉（强信号）
                if dif < 0 and dea < 0:
                    reason += " [零轴下方]"
                    strength = min(strength + 0.1, 1.0)

                return Signal(
                    type=SignalType.SELL,
                    price=candle.close,
                    timestamp=candle.timestamp,
                    reason=reason,
                    strength=strength,
                    metadata={
                        "dif": dif,
                        "dea": dea,
                        "histogram": hist,
                        "cross_type": "death",
                    }
                )

        return Signal(
            type=SignalType.HOLD,
            price=candle.close,
            timestamp=candle.timestamp,
            reason=f"等待信号 (DIF: {dif:.4f}, DEA: {dea:.4f})"
        )

    def get_params(self) -> Dict[str, Any]:
        """获取策略参数"""
        params = super().get_params()
        params.update({
            "fast_period": self.macd_config.fast_period,
            "slow_period": self.macd_config.slow_period,
            "signal_period": self.macd_config.signal_period,
            "use_histogram": self.macd_config.use_histogram,
            "use_zero_line": self.macd_config.use_zero_line,
            "use_trend_filter": self.macd_config.use_trend_filter,
        })
        return params


def create_macd_strategy(
    symbol: str = "BTC-USDT",
    timeframe: str = "1H",
    initial_capital: float = 10000,
    fast_period: int = 12,
    slow_period: int = 26,
    signal_period: int = 9,
    stop_loss: float = 0.05,
    take_profit: float = 0.10,
    position_size: float = 0.5,
    use_histogram: bool = True,
) -> MACDStrategy:
    """
    创建MACD策略实例

    Args:
        symbol: 交易对
        timeframe: 时间周期
        initial_capital: 初始资金
        fast_period: 快线周期
        slow_period: 慢线周期
        signal_period: 信号线周期
        stop_loss: 止损比例
        take_profit: 止盈比例
        position_size: 仓位比例
        use_histogram: 是否使用柱状图确认

    Returns:
        MACD策略实例
    """
    config = MACDConfig(
        symbol=symbol,
        timeframe=timeframe,
        initial_capital=initial_capital,
        fast_period=fast_period,
        slow_period=slow_period,
        signal_period=signal_period,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_size=position_size,
        use_histogram=use_histogram,
    )
    return MACDStrategy(config)
