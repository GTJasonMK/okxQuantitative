# RSI超买超卖策略
# 基于相对强弱指标(RSI)的经典震荡交易策略
# 参考资料: https://www.altrady.com/blog/crypto-trading-strategies/rsi-trading-strategy

from typing import List, Dict, Any
from dataclasses import dataclass

from pydantic import BaseModel, Field

from .base import BaseStrategy, StrategyConfig, Signal, SignalType
from ..core.indicators import rsi, sma


class RSIParams(BaseModel):
    """RSI策略参数 Schema"""
    rsi_period: int = Field(
        default=14, ge=2, le=50,
        json_schema_extra={"label": "RSI周期", "order": 1}
    )
    overbought: int = Field(
        default=70, ge=50, le=95,
        json_schema_extra={"label": "超买阈值", "order": 2}
    )
    oversold: int = Field(
        default=30, ge=5, le=50,
        json_schema_extra={"label": "超卖阈值", "order": 3}
    )
    exit_overbought: int = Field(
        default=50, ge=30, le=80,
        json_schema_extra={"label": "超买退出阈值", "order": 4}
    )
    exit_oversold: int = Field(
        default=50, ge=20, le=70,
        json_schema_extra={"label": "超卖退出阈值", "order": 5}
    )
    use_divergence: bool = Field(
        default=False,
        json_schema_extra={"label": "启用背离检测", "order": 6}
    )


@dataclass
class RSIConfig(StrategyConfig):
    """RSI策略配置"""
    name: str = "RSI策略"
    # RSI参数
    rsi_period: int = 14            # RSI计算周期
    overbought: int = 70            # 超买阈值
    oversold: int = 30              # 超卖阈值
    exit_overbought: int = 50       # 超买区域退出阈值
    exit_oversold: int = 50         # 超卖区域退出阈值
    use_divergence: bool = False    # 是否使用背离信号


class RSIStrategy(BaseStrategy):
    """
    RSI超买超卖策略

    交易逻辑：
    - 买入：RSI从超卖区域(低于oversold)上穿oversold
    - 卖出：RSI从超买区域(高于overbought)下穿overbought，或止损/止盈

    可选：背离信号
    - 看涨背离：价格创新低但RSI未创新低
    - 看跌背离：价格创新高但RSI未创新高

    适用场景：震荡行情，不适合单边趋势行情
    """

    strategy_id = "rsi"
    strategy_name = "RSI策略"
    strategy_description = "基于RSI超买超卖的震荡交易策略，适合区间震荡行情"
    params_schema = RSIParams

    def __init__(self, config: RSIConfig):
        super().__init__(config)
        self.rsi_config = config

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
    ) -> "RSIStrategy":
        """工厂方法：创建策略实例"""
        params = RSIParams(**strategy_params)

        config = RSIConfig(
            symbol=symbol,
            timeframe=timeframe,
            inst_type=inst_type,
            initial_capital=initial_capital,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            rsi_period=params.rsi_period,
            overbought=params.overbought,
            oversold=params.oversold,
            exit_overbought=params.exit_overbought,
            exit_oversold=params.exit_oversold,
            use_divergence=params.use_divergence,
        )
        return cls(config)

    @classmethod
    def validate_params(cls, params: Dict[str, Any]) -> None:
        """验证策略参数"""
        validated = RSIParams(**params)
        if validated.overbought <= validated.oversold:
            raise ValueError("超买阈值必须大于超卖阈值")
        if validated.exit_overbought < validated.oversold:
            raise ValueError("超买退出阈值不能低于超卖阈值")
        if validated.exit_oversold > validated.overbought:
            raise ValueError("超卖退出阈值不能高于超买阈值")

    def calculate_indicators(self, candles: List) -> Dict[str, List[float]]:
        """计算RSI指标"""
        closes = [c.close for c in candles]
        highs = [c.high for c in candles]
        lows = [c.low for c in candles]

        indicators = {
            "rsi": rsi(closes, self.rsi_config.rsi_period),
            "close": closes,
            "high": highs,
            "low": lows,
        }

        return indicators

    def _check_bullish_divergence(self, index: int, lookback: int = 10) -> bool:
        """
        检测看涨背离：价格创新低但RSI未创新低

        Args:
            index: 当前索引
            lookback: 回看周期

        Returns:
            是否存在看涨背离
        """
        if index < lookback:
            return False

        current_rsi = self.get_indicator("rsi", index)
        current_low = self.get_indicator("low", index)

        if current_rsi is None or current_low is None:
            return False

        # 找到回看期间的最低价格和对应的RSI
        min_low = current_low
        min_low_rsi = current_rsi

        for i in range(index - lookback, index):
            low = self.get_indicator("low", i)
            r = self.get_indicator("rsi", i)
            if low is not None and low < min_low:
                min_low = low
                min_low_rsi = r if r is not None else min_low_rsi

        # 看涨背离：当前价格接近或低于前低，但RSI高于前低时的RSI
        if current_low <= min_low * 1.01 and current_rsi > min_low_rsi:
            return True

        return False

    def _check_bearish_divergence(self, index: int, lookback: int = 10) -> bool:
        """
        检测看跌背离：价格创新高但RSI未创新高

        Args:
            index: 当前索引
            lookback: 回看周期

        Returns:
            是否存在看跌背离
        """
        if index < lookback:
            return False

        current_rsi = self.get_indicator("rsi", index)
        current_high = self.get_indicator("high", index)

        if current_rsi is None or current_high is None:
            return False

        # 找到回看期间的最高价格和对应的RSI
        max_high = current_high
        max_high_rsi = current_rsi

        for i in range(index - lookback, index):
            high = self.get_indicator("high", i)
            r = self.get_indicator("rsi", i)
            if high is not None and high > max_high:
                max_high = high
                max_high_rsi = r if r is not None else max_high_rsi

        # 看跌背离：当前价格接近或高于前高，但RSI低于前高时的RSI
        if current_high >= max_high * 0.99 and current_rsi < max_high_rsi:
            return True

        return False

    def generate_signal(self, index: int) -> Signal:
        """生成交易信号"""
        candle = self.get_candle(index)
        if not candle:
            return Signal(type=SignalType.HOLD, price=0, timestamp=0)

        current_rsi = self.get_indicator("rsi", index)
        prev_rsi = self.get_indicator("rsi", index - 1)

        # 数据不足
        if current_rsi is None or prev_rsi is None:
            return Signal(
                type=SignalType.HOLD,
                price=candle.close,
                timestamp=candle.timestamp,
                reason="RSI数据不足"
            )

        # 买入信号：RSI从超卖区域上穿超卖线
        if prev_rsi < self.rsi_config.oversold <= current_rsi:
            if self.position.is_empty:
                reason = f"RSI上穿超卖线: {current_rsi:.2f}"

                # 检查看涨背离增强信号
                if self.rsi_config.use_divergence and self._check_bullish_divergence(index):
                    reason += " (看涨背离)"
                    strength = 0.9
                else:
                    strength = 0.7

                return Signal(
                    type=SignalType.BUY,
                    price=candle.close,
                    timestamp=candle.timestamp,
                    reason=reason,
                    strength=strength,
                    metadata={"rsi": current_rsi, "signal_type": "oversold_cross"}
                )

        # 卖出信号：RSI从超买区域下穿超买线
        if prev_rsi > self.rsi_config.overbought >= current_rsi:
            if not self.position.is_empty:
                reason = f"RSI下穿超买线: {current_rsi:.2f}"

                # 检查看跌背离增强信号
                if self.rsi_config.use_divergence and self._check_bearish_divergence(index):
                    reason += " (看跌背离)"
                    strength = 0.9
                else:
                    strength = 0.7

                return Signal(
                    type=SignalType.SELL,
                    price=candle.close,
                    timestamp=candle.timestamp,
                    reason=reason,
                    strength=strength,
                    metadata={"rsi": current_rsi, "signal_type": "overbought_cross"}
                )

        # 持仓时的中性退出信号
        if not self.position.is_empty:
            # 如果RSI回到中性区域，可以考虑减仓（这里简化为持有）
            pass

        return Signal(
            type=SignalType.HOLD,
            price=candle.close,
            timestamp=candle.timestamp,
            reason=f"等待信号 (RSI: {current_rsi:.2f})"
        )

    def get_params(self) -> Dict[str, Any]:
        """获取策略参数"""
        params = super().get_params()
        params.update({
            "rsi_period": self.rsi_config.rsi_period,
            "overbought": self.rsi_config.overbought,
            "oversold": self.rsi_config.oversold,
            "use_divergence": self.rsi_config.use_divergence,
        })
        return params


def create_rsi_strategy(
    symbol: str = "BTC-USDT",
    timeframe: str = "1H",
    initial_capital: float = 10000,
    rsi_period: int = 14,
    overbought: int = 70,
    oversold: int = 30,
    stop_loss: float = 0.05,
    take_profit: float = 0.10,
    position_size: float = 0.5,
    use_divergence: bool = False,
) -> RSIStrategy:
    """
    创建RSI策略实例

    Args:
        symbol: 交易对
        timeframe: 时间周期
        initial_capital: 初始资金
        rsi_period: RSI周期
        overbought: 超买阈值
        oversold: 超卖阈值
        stop_loss: 止损比例
        take_profit: 止盈比例
        position_size: 仓位比例
        use_divergence: 是否使用背离信号

    Returns:
        RSI策略实例
    """
    config = RSIConfig(
        symbol=symbol,
        timeframe=timeframe,
        initial_capital=initial_capital,
        rsi_period=rsi_period,
        overbought=overbought,
        oversold=oversold,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_size=position_size,
        use_divergence=use_divergence,
    )
    return RSIStrategy(config)
