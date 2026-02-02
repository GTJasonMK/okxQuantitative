# 双均线策略
# 经典的趋势跟踪策略，使用短期和长期均线的交叉作为买卖信号

from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from .base import BaseStrategy, StrategyConfig, Signal, SignalType
from ..core.indicators import sma, ema


# Pydantic 参数 Schema（用于插件化架构）
class DualMAParams(BaseModel):
    """双均线策略参数 Schema"""
    short_period: int = Field(
        default=5, ge=2, le=50,
        json_schema_extra={"label": "短期均线周期", "order": 1}
    )
    long_period: int = Field(
        default=20, ge=5, le=200,
        json_schema_extra={"label": "长期均线周期", "order": 2}
    )
    use_ema: bool = Field(
        default=False,
        json_schema_extra={"label": "使用EMA", "order": 3}
    )
    min_volume_ratio: float = Field(
        default=0.0, ge=0, le=10,
        json_schema_extra={"label": "最小成交量倍数", "order": 4}
    )
    trend_filter: bool = Field(
        default=False,
        json_schema_extra={"label": "趋势过滤", "order": 5}
    )


@dataclass
class DualMAConfig(StrategyConfig):
    """双均线策略配置"""
    name: str = "双均线策略"
    # 均线参数
    short_period: int = 5               # 短期均线周期
    long_period: int = 20               # 长期均线周期
    use_ema: bool = False               # 是否使用EMA（默认SMA）
    # 额外过滤条件
    min_volume_ratio: float = 0.0       # 最小成交量倍数（相对均量）
    trend_filter: bool = False          # 是否启用趋势过滤


class DualMAStrategy(BaseStrategy):
    """
    双均线策略

    交易逻辑：
    - 买入：短期均线上穿长期均线（金叉）
    - 卖出：短期均线下穿长期均线（死叉）或止损/止盈
    """

    # 策略元数据（用于自动注册）
    strategy_id = "dual_ma"
    strategy_name = "双均线策略"
    strategy_description = "使用短期和长期均线的交叉作为买卖信号，适合趋势行情"
    params_schema = DualMAParams

    def __init__(self, config: DualMAConfig):
        super().__init__(config)
        self.ma_config = config

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
    ) -> "DualMAStrategy":
        """工厂方法：创建策略实例"""
        # 验证并获取策略参数
        params = DualMAParams(**strategy_params)

        config = DualMAConfig(
            symbol=symbol,
            timeframe=timeframe,
            inst_type=inst_type,
            initial_capital=initial_capital,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            short_period=params.short_period,
            long_period=params.long_period,
            use_ema=params.use_ema,
            min_volume_ratio=params.min_volume_ratio,
            trend_filter=params.trend_filter,
        )
        return cls(config)

    @classmethod
    def validate_params(cls, params: Dict[str, Any]) -> None:
        """验证策略参数"""
        validated = DualMAParams(**params)
        if validated.short_period >= validated.long_period:
            raise ValueError("短期均线周期必须小于长期均线周期")

    def calculate_indicators(self, candles: List) -> Dict[str, List[float]]:
        """计算双均线指标"""
        closes = [c.close for c in candles]
        volumes = [c.volume for c in candles]

        # 选择均线类型
        ma_func = ema if self.ma_config.use_ema else sma

        indicators = {
            "ma_short": ma_func(closes, self.ma_config.short_period),
            "ma_long": ma_func(closes, self.ma_config.long_period),
            "volume_ma": sma(volumes, 20),
        }

        # 如果启用趋势过滤，添加更长周期均线
        if self.ma_config.trend_filter:
            indicators["ma_trend"] = sma(closes, 60)

        return indicators

    def generate_signal(self, index: int) -> Signal:
        """生成交易信号"""
        candle = self.get_candle(index)
        if not candle:
            return Signal(type=SignalType.HOLD, price=0, timestamp=0)

        # 获取当前和前一根K线的均线值
        ma_short = self.get_indicator("ma_short", index)
        ma_short_prev = self.get_indicator("ma_short", index - 1)
        ma_long = self.get_indicator("ma_long", index)
        ma_long_prev = self.get_indicator("ma_long", index - 1)

        # 数据不足，持有观望
        if None in [ma_short, ma_short_prev, ma_long, ma_long_prev]:
            return Signal(
                type=SignalType.HOLD,
                price=candle.close,
                timestamp=candle.timestamp,
                reason="指标数据不足"
            )

        # 检查成交量过滤
        if self.ma_config.min_volume_ratio > 0:
            volume_ma = self.get_indicator("volume_ma", index)
            if volume_ma and candle.volume < volume_ma * self.ma_config.min_volume_ratio:
                return Signal(
                    type=SignalType.HOLD,
                    price=candle.close,
                    timestamp=candle.timestamp,
                    reason="成交量不足"
                )

        # 检查趋势过滤
        if self.ma_config.trend_filter:
            ma_trend = self.get_indicator("ma_trend", index)
            if ma_trend:
                # 价格在趋势线下方时不做多
                if candle.close < ma_trend and self.position.is_empty:
                    return Signal(
                        type=SignalType.HOLD,
                        price=candle.close,
                        timestamp=candle.timestamp,
                        reason="趋势过滤：价格低于趋势线"
                    )

        # 金叉：短期均线上穿长期均线
        if ma_short_prev <= ma_long_prev and ma_short > ma_long:
            if self.position.is_empty:
                return Signal(
                    type=SignalType.BUY,
                    price=candle.close,
                    timestamp=candle.timestamp,
                    reason=f"金叉信号: MA{self.ma_config.short_period}上穿MA{self.ma_config.long_period}",
                    strength=min((ma_short - ma_long) / ma_long * 100, 1.0),
                    metadata={
                        "ma_short": ma_short,
                        "ma_long": ma_long,
                        "cross_type": "golden"
                    }
                )

        # 死叉：短期均线下穿长期均线
        if ma_short_prev >= ma_long_prev and ma_short < ma_long:
            if not self.position.is_empty:
                return Signal(
                    type=SignalType.SELL,
                    price=candle.close,
                    timestamp=candle.timestamp,
                    reason=f"死叉信号: MA{self.ma_config.short_period}下穿MA{self.ma_config.long_period}",
                    strength=min((ma_long - ma_short) / ma_long * 100, 1.0),
                    metadata={
                        "ma_short": ma_short,
                        "ma_long": ma_long,
                        "cross_type": "death"
                    }
                )

        # 无信号
        return Signal(
            type=SignalType.HOLD,
            price=candle.close,
            timestamp=candle.timestamp,
            reason="等待信号"
        )

    def get_params(self) -> Dict[str, Any]:
        """获取策略参数"""
        params = super().get_params()
        params.update({
            "short_period": self.ma_config.short_period,
            "long_period": self.ma_config.long_period,
            "use_ema": self.ma_config.use_ema,
            "trend_filter": self.ma_config.trend_filter,
        })
        return params


def create_dual_ma_strategy(
    symbol: str = "BTC-USDT",
    timeframe: str = "1H",
    inst_type: str = "SPOT",
    initial_capital: float = 10000,
    short_period: int = 5,
    long_period: int = 20,
    stop_loss: float = 0.05,
    take_profit: float = 0.10,
    position_size: float = 0.5,
    use_ema: bool = False,
) -> DualMAStrategy:
    """
    创建双均线策略实例

    Args:
        symbol: 交易对
        timeframe: 时间周期
        initial_capital: 初始资金
        short_period: 短期均线周期
        long_period: 长期均线周期
        stop_loss: 止损比例
        take_profit: 止盈比例
        position_size: 仓位比例
        use_ema: 是否使用EMA

    Returns:
        策略实例
    """
    config = DualMAConfig(
        symbol=symbol,
        timeframe=timeframe,
        inst_type=inst_type,
        initial_capital=initial_capital,
        short_period=short_period,
        long_period=long_period,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_size=position_size,
        use_ema=use_ema,
    )
    return DualMAStrategy(config)
