# 布林带突破策略
# 基于布林带(Bollinger Bands)的波动率突破交易策略
# 参考资料: https://bingx.com/en/learn/article/how-to-use-bollinger-bands-to-spot-breakouts-and-trends-in-crypto-market

from typing import List, Dict, Any
from dataclasses import dataclass
import math

from pydantic import BaseModel, Field

from .base import BaseStrategy, StrategyConfig, Signal, SignalType
from ..core.indicators import bollinger_bands, rsi, sma


class BollingerParams(BaseModel):
    """布林带策略参数 Schema"""
    bb_period: int = Field(
        default=20, ge=5, le=100,
        json_schema_extra={"label": "布林带周期", "order": 1}
    )
    bb_std: float = Field(
        default=2.0, ge=1.0, le=4.0,
        json_schema_extra={"label": "标准差倍数", "order": 2}
    )
    squeeze_threshold: float = Field(
        default=0.03, ge=0.01, le=0.10,
        json_schema_extra={"label": "缩口阈值(带宽比)", "order": 3}
    )
    use_rsi_filter: bool = Field(
        default=True,
        json_schema_extra={"label": "RSI确认过滤", "order": 4}
    )
    rsi_period: int = Field(
        default=14, ge=5, le=50,
        json_schema_extra={"label": "RSI周期", "order": 5}
    )
    volume_confirm: bool = Field(
        default=False,
        json_schema_extra={"label": "成交量确认", "order": 6}
    )


@dataclass
class BollingerConfig(StrategyConfig):
    """布林带策略配置"""
    name: str = "布林带策略"
    # 布林带参数
    bb_period: int = 20             # 布林带周期
    bb_std: float = 2.0             # 标准差倍数
    squeeze_threshold: float = 0.03 # 缩口阈值（带宽比）
    # 过滤参数
    use_rsi_filter: bool = True     # 是否使用RSI过滤
    rsi_period: int = 14            # RSI周期
    volume_confirm: bool = False    # 是否使用成交量确认


class BollingerStrategy(BaseStrategy):
    """
    布林带策略

    交易逻辑（均值回归模式）：
    - 买入：价格触及/跌破下轨后回升到下轨上方
    - 卖出：价格触及/突破上轨后回落到上轨下方

    可选过滤条件：
    - RSI确认：买入时RSI < 40，卖出时RSI > 60
    - 成交量确认：突破时成交量大于均量

    布林带缩口(Squeeze)：
    - 当带宽比低于阈值时，预示即将发生大幅波动
    - 策略会在缩口后的突破方向进行交易

    适用场景：震荡行情的均值回归，以及缩口后的突破交易
    """

    strategy_id = "bollinger"
    strategy_name = "布林带策略"
    strategy_description = "基于布林带的均值回归和突破交易策略，适合震荡和突破行情"
    params_schema = BollingerParams

    def __init__(self, config: BollingerConfig):
        super().__init__(config)
        self.bb_config = config
        # 追踪缩口状态
        self._in_squeeze = False

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
    ) -> "BollingerStrategy":
        """工厂方法：创建策略实例"""
        params = BollingerParams(**strategy_params)

        config = BollingerConfig(
            symbol=symbol,
            timeframe=timeframe,
            inst_type=inst_type,
            initial_capital=initial_capital,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            bb_period=params.bb_period,
            bb_std=params.bb_std,
            squeeze_threshold=params.squeeze_threshold,
            use_rsi_filter=params.use_rsi_filter,
            rsi_period=params.rsi_period,
            volume_confirm=params.volume_confirm,
        )
        return cls(config)

    def calculate_indicators(self, candles: List) -> Dict[str, List[float]]:
        """计算布林带指标"""
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]

        upper, middle, lower = bollinger_bands(
            closes,
            self.bb_config.bb_period,
            self.bb_config.bb_std
        )

        indicators = {
            "bb_upper": upper,
            "bb_middle": middle,
            "bb_lower": lower,
            "close": closes,
            "volume_ma": sma(volumes, 20),
            "volume": volumes,
        }

        # 计算带宽比: (上轨 - 下轨) / 中轨
        bandwidth = []
        for i in range(len(closes)):
            if math.isnan(upper[i]) or math.isnan(lower[i]) or math.isnan(middle[i]) or middle[i] == 0:
                bandwidth.append(float('nan'))
            else:
                bandwidth.append((upper[i] - lower[i]) / middle[i])
        indicators["bandwidth"] = bandwidth

        # 可选RSI
        if self.bb_config.use_rsi_filter:
            indicators["rsi"] = rsi(closes, self.bb_config.rsi_period)

        return indicators

    def generate_signal(self, index: int) -> Signal:
        """生成交易信号"""
        candle = self.get_candle(index)
        if not candle:
            return Signal(type=SignalType.HOLD, price=0, timestamp=0)

        bb_upper = self.get_indicator("bb_upper", index)
        bb_lower = self.get_indicator("bb_lower", index)
        bb_middle = self.get_indicator("bb_middle", index)
        bandwidth = self.get_indicator("bandwidth", index)

        prev_close = self.get_indicator("close", index - 1)

        # 数据不足
        if None in [bb_upper, bb_lower, bb_middle, bandwidth, prev_close]:
            return Signal(
                type=SignalType.HOLD,
                price=candle.close,
                timestamp=candle.timestamp,
                reason="指标数据不足"
            )

        # 检测缩口状态
        if bandwidth < self.bb_config.squeeze_threshold:
            self._in_squeeze = True

        # RSI过滤
        rsi_ok_buy = True
        rsi_ok_sell = True
        current_rsi = None
        if self.bb_config.use_rsi_filter:
            current_rsi = self.get_indicator("rsi", index)
            if current_rsi is not None:
                rsi_ok_buy = current_rsi < 40
                rsi_ok_sell = current_rsi > 60

        # 成交量确认
        volume_ok = True
        if self.bb_config.volume_confirm:
            vol = self.get_indicator("volume", index)
            vol_ma = self.get_indicator("volume_ma", index)
            if vol is not None and vol_ma is not None and vol_ma > 0:
                volume_ok = vol > vol_ma * 1.2

        # 买入信号：价格从下轨下方回升到下轨上方
        if prev_close <= bb_lower and candle.close > bb_lower:
            if self.position.is_empty and rsi_ok_buy:
                reason = f"价格回升突破下轨 ({candle.close:.2f} > {bb_lower:.2f})"
                strength = 0.7

                if self._in_squeeze:
                    reason += " [缩口突破]"
                    strength = 0.9
                    self._in_squeeze = False

                if not volume_ok:
                    return Signal(
                        type=SignalType.HOLD,
                        price=candle.close,
                        timestamp=candle.timestamp,
                        reason="成交量不足，放弃信号"
                    )

                return Signal(
                    type=SignalType.BUY,
                    price=candle.close,
                    timestamp=candle.timestamp,
                    reason=reason,
                    strength=strength,
                    metadata={
                        "bb_upper": bb_upper,
                        "bb_middle": bb_middle,
                        "bb_lower": bb_lower,
                        "bandwidth": bandwidth,
                        "rsi": current_rsi,
                    }
                )

        # 卖出信号：价格从上轨上方回落到上轨下方
        if prev_close >= bb_upper and candle.close < bb_upper:
            if not self.position.is_empty and rsi_ok_sell:
                reason = f"价格回落跌破上轨 ({candle.close:.2f} < {bb_upper:.2f})"
                strength = 0.7

                if not volume_ok:
                    return Signal(
                        type=SignalType.HOLD,
                        price=candle.close,
                        timestamp=candle.timestamp,
                        reason="成交量不足，继续持有"
                    )

                return Signal(
                    type=SignalType.SELL,
                    price=candle.close,
                    timestamp=candle.timestamp,
                    reason=reason,
                    strength=strength,
                    metadata={
                        "bb_upper": bb_upper,
                        "bb_middle": bb_middle,
                        "bb_lower": bb_lower,
                        "bandwidth": bandwidth,
                        "rsi": current_rsi,
                    }
                )

        return Signal(
            type=SignalType.HOLD,
            price=candle.close,
            timestamp=candle.timestamp,
            reason=f"等待信号 (带宽: {bandwidth:.4f})"
        )

    def get_params(self) -> Dict[str, Any]:
        """获取策略参数"""
        params = super().get_params()
        params.update({
            "bb_period": self.bb_config.bb_period,
            "bb_std": self.bb_config.bb_std,
            "squeeze_threshold": self.bb_config.squeeze_threshold,
            "use_rsi_filter": self.bb_config.use_rsi_filter,
            "volume_confirm": self.bb_config.volume_confirm,
        })
        return params


def create_bollinger_strategy(
    symbol: str = "BTC-USDT",
    timeframe: str = "1H",
    initial_capital: float = 10000,
    bb_period: int = 20,
    bb_std: float = 2.0,
    stop_loss: float = 0.05,
    take_profit: float = 0.10,
    position_size: float = 0.5,
    use_rsi_filter: bool = True,
) -> BollingerStrategy:
    """
    创建布林带策略实例

    Args:
        symbol: 交易对
        timeframe: 时间周期
        initial_capital: 初始资金
        bb_period: 布林带周期
        bb_std: 标准差倍数
        stop_loss: 止损比例
        take_profit: 止盈比例
        position_size: 仓位比例
        use_rsi_filter: 是否启用RSI过滤

    Returns:
        布林带策略实例
    """
    config = BollingerConfig(
        symbol=symbol,
        timeframe=timeframe,
        initial_capital=initial_capital,
        bb_period=bb_period,
        bb_std=bb_std,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_size=position_size,
        use_rsi_filter=use_rsi_filter,
    )
    return BollingerStrategy(config)
