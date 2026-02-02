# 多指标混合策略
# 结合RSI、布林带、MACD三大指标的综合交易策略
# 参考资料: 基于多指标共振原理，提高信号可靠性

from typing import List, Dict, Any
from dataclasses import dataclass
import math

from pydantic import BaseModel, Field
from typing import Literal

from .base import BaseStrategy, StrategyConfig, Signal, SignalType
from ..core.indicators import rsi, bollinger_bands, macd


class HybridParams(BaseModel):
    """混合策略参数 Schema"""
    # RSI参数
    rsi_period: int = Field(
        default=14, ge=5, le=50,
        json_schema_extra={"label": "RSI周期", "order": 1}
    )
    rsi_overbought: int = Field(
        default=70, ge=50, le=90,
        json_schema_extra={"label": "RSI超买阈值", "order": 2}
    )
    rsi_oversold: int = Field(
        default=30, ge=10, le=50,
        json_schema_extra={"label": "RSI超卖阈值", "order": 3}
    )
    # 布林带参数
    bb_period: int = Field(
        default=20, ge=10, le=50,
        json_schema_extra={"label": "布林带周期", "order": 4}
    )
    bb_std: float = Field(
        default=2.0, ge=1.0, le=3.0,
        json_schema_extra={"label": "布林带标准差", "order": 5}
    )
    # MACD参数
    macd_fast: int = Field(
        default=12, ge=5, le=30,
        json_schema_extra={"label": "MACD快线周期", "order": 6}
    )
    macd_slow: int = Field(
        default=26, ge=10, le=60,
        json_schema_extra={"label": "MACD慢线周期", "order": 7}
    )
    macd_signal: int = Field(
        default=9, ge=3, le=20,
        json_schema_extra={"label": "MACD信号线周期", "order": 8}
    )
    # 信号模式
    signal_mode: Literal["any", "majority", "all"] = Field(
        default="majority",
        json_schema_extra={
            "label": "信号模式",
            "order": 9,
            "options": ["any", "majority", "all"]
        }
    )


@dataclass
class HybridConfig(StrategyConfig):
    """混合策略配置"""
    name: str = "多指标混合策略"
    # RSI参数
    rsi_period: int = 14
    rsi_overbought: int = 70
    rsi_oversold: int = 30
    # 布林带参数
    bb_period: int = 20
    bb_std: float = 2.0
    # MACD参数
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    # 信号模式: any(任一), majority(多数), all(全部)
    signal_mode: str = "majority"


class HybridStrategy(BaseStrategy):
    """
    多指标混合策略

    核心思想：
    通过多个技术指标的共振来过滤虚假信号，提高交易胜率。
    当多个指标同时给出相同方向的信号时，交易的可靠性更高。

    指标组合：
    1. RSI - 超买超卖判断
    2. 布林带 - 价格位置和波动率
    3. MACD - 趋势和动量

    信号模式：
    - any: 任一指标给出信号即交易（灵敏但容易误判）
    - majority: 2/3指标给出信号才交易（平衡模式）
    - all: 所有指标都给出信号才交易（保守但可靠）

    买入条件：
    - RSI: 从超卖区域回升（RSI上穿30）
    - 布林带: 价格触及下轨后回升
    - MACD: DIF上穿DEA（金叉）

    卖出条件：
    - RSI: 从超买区域回落（RSI下穿70）
    - 布林带: 价格触及上轨后回落
    - MACD: DIF下穿DEA（死叉）

    适用场景：中线交易，适合追求稳定收益的投资者
    """

    strategy_id = "hybrid"
    strategy_name = "多指标混合策略"
    strategy_description = "结合RSI、布林带、MACD的多指标共振策略，信号更可靠"
    params_schema = HybridParams

    def __init__(self, config: HybridConfig):
        super().__init__(config)
        self.hybrid_config = config

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
    ) -> "HybridStrategy":
        """工厂方法：创建策略实例"""
        params = HybridParams(**strategy_params)

        config = HybridConfig(
            symbol=symbol,
            timeframe=timeframe,
            inst_type=inst_type,
            initial_capital=initial_capital,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            rsi_period=params.rsi_period,
            rsi_overbought=params.rsi_overbought,
            rsi_oversold=params.rsi_oversold,
            bb_period=params.bb_period,
            bb_std=params.bb_std,
            macd_fast=params.macd_fast,
            macd_slow=params.macd_slow,
            macd_signal=params.macd_signal,
            signal_mode=params.signal_mode,
        )
        return cls(config)

    @classmethod
    def validate_params(cls, params: Dict[str, Any]) -> None:
        """验证策略参数"""
        validated = HybridParams(**params)
        if validated.rsi_overbought <= validated.rsi_oversold:
            raise ValueError("RSI超买阈值必须大于超卖阈值")
        if validated.macd_fast >= validated.macd_slow:
            raise ValueError("MACD快线周期必须小于慢线周期")

    def calculate_indicators(self, candles: List) -> Dict[str, List[float]]:
        """计算所有指标"""
        closes = [c.close for c in candles]

        # RSI
        rsi_values = rsi(closes, self.hybrid_config.rsi_period)

        # 布林带
        bb_upper, bb_middle, bb_lower = bollinger_bands(
            closes,
            self.hybrid_config.bb_period,
            self.hybrid_config.bb_std
        )

        # MACD
        dif, dea, hist = macd(
            closes,
            self.hybrid_config.macd_fast,
            self.hybrid_config.macd_slow,
            self.hybrid_config.macd_signal,
        )

        return {
            "rsi": rsi_values,
            "bb_upper": bb_upper,
            "bb_middle": bb_middle,
            "bb_lower": bb_lower,
            "dif": dif,
            "dea": dea,
            "macd_hist": hist,
            "close": closes,
        }

    def _check_rsi_buy_signal(self, index: int) -> bool:
        """检查RSI买入信号"""
        current_rsi = self.get_indicator("rsi", index)
        prev_rsi = self.get_indicator("rsi", index - 1)

        if current_rsi is None or prev_rsi is None:
            return False

        # RSI从超卖区域上穿超卖线
        return prev_rsi < self.hybrid_config.rsi_oversold <= current_rsi

    def _check_rsi_sell_signal(self, index: int) -> bool:
        """检查RSI卖出信号"""
        current_rsi = self.get_indicator("rsi", index)
        prev_rsi = self.get_indicator("rsi", index - 1)

        if current_rsi is None or prev_rsi is None:
            return False

        # RSI从超买区域下穿超买线
        return prev_rsi > self.hybrid_config.rsi_overbought >= current_rsi

    def _check_bb_buy_signal(self, index: int) -> bool:
        """检查布林带买入信号"""
        close = self.get_indicator("close", index)
        prev_close = self.get_indicator("close", index - 1)
        bb_lower = self.get_indicator("bb_lower", index)
        prev_bb_lower = self.get_indicator("bb_lower", index - 1)

        if None in [close, prev_close, bb_lower, prev_bb_lower]:
            return False

        # 价格从下轨下方回升到下轨上方
        return prev_close <= prev_bb_lower and close > bb_lower

    def _check_bb_sell_signal(self, index: int) -> bool:
        """检查布林带卖出信号"""
        close = self.get_indicator("close", index)
        prev_close = self.get_indicator("close", index - 1)
        bb_upper = self.get_indicator("bb_upper", index)
        prev_bb_upper = self.get_indicator("bb_upper", index - 1)

        if None in [close, prev_close, bb_upper, prev_bb_upper]:
            return False

        # 价格从上轨上方回落到上轨下方
        return prev_close >= prev_bb_upper and close < bb_upper

    def _check_macd_buy_signal(self, index: int) -> bool:
        """检查MACD买入信号（金叉）"""
        dif = self.get_indicator("dif", index)
        dif_prev = self.get_indicator("dif", index - 1)
        dea = self.get_indicator("dea", index)
        dea_prev = self.get_indicator("dea", index - 1)

        if None in [dif, dif_prev, dea, dea_prev]:
            return False

        # DIF上穿DEA
        return dif_prev <= dea_prev and dif > dea

    def _check_macd_sell_signal(self, index: int) -> bool:
        """检查MACD卖出信号（死叉）"""
        dif = self.get_indicator("dif", index)
        dif_prev = self.get_indicator("dif", index - 1)
        dea = self.get_indicator("dea", index)
        dea_prev = self.get_indicator("dea", index - 1)

        if None in [dif, dif_prev, dea, dea_prev]:
            return False

        # DIF下穿DEA
        return dif_prev >= dea_prev and dif < dea

    def _should_buy(self, buy_signals: List[bool]) -> bool:
        """根据信号模式判断是否买入"""
        count = sum(buy_signals)
        mode = self.hybrid_config.signal_mode

        if mode == "any":
            return count >= 1
        elif mode == "majority":
            return count >= 2
        else:  # all
            return count == 3

    def _should_sell(self, sell_signals: List[bool]) -> bool:
        """根据信号模式判断是否卖出"""
        count = sum(sell_signals)
        mode = self.hybrid_config.signal_mode

        if mode == "any":
            return count >= 1
        elif mode == "majority":
            return count >= 2
        else:  # all
            return count == 3

    def generate_signal(self, index: int) -> Signal:
        """生成交易信号"""
        candle = self.get_candle(index)
        if not candle:
            return Signal(type=SignalType.HOLD, price=0, timestamp=0)

        # 获取当前指标值（用于元数据）
        current_rsi = self.get_indicator("rsi", index)
        dif = self.get_indicator("dif", index)
        dea = self.get_indicator("dea", index)
        bb_upper = self.get_indicator("bb_upper", index)
        bb_lower = self.get_indicator("bb_lower", index)

        # 检查各指标的买入信号
        rsi_buy = self._check_rsi_buy_signal(index)
        bb_buy = self._check_bb_buy_signal(index)
        macd_buy = self._check_macd_buy_signal(index)
        buy_signals = [rsi_buy, bb_buy, macd_buy]

        # 检查各指标的卖出信号
        rsi_sell = self._check_rsi_sell_signal(index)
        bb_sell = self._check_bb_sell_signal(index)
        macd_sell = self._check_macd_sell_signal(index)
        sell_signals = [rsi_sell, bb_sell, macd_sell]

        # 生成信号描述
        def _get_signal_desc(signals: List[bool], names: List[str]) -> str:
            active = [n for n, s in zip(names, signals) if s]
            return ", ".join(active) if active else "无"

        indicator_names = ["RSI", "布林带", "MACD"]

        # 买入判断
        if self.position.is_empty and self._should_buy(buy_signals):
            signal_count = sum(buy_signals)
            signal_desc = _get_signal_desc(buy_signals, indicator_names)
            strength = 0.5 + 0.15 * signal_count  # 信号越多强度越高

            return Signal(
                type=SignalType.BUY,
                price=candle.close,
                timestamp=candle.timestamp,
                reason=f"多指标买入信号 ({signal_count}/3): {signal_desc}",
                strength=strength,
                metadata={
                    "rsi": current_rsi,
                    "rsi_signal": rsi_buy,
                    "bb_signal": bb_buy,
                    "macd_signal": macd_buy,
                    "dif": dif,
                    "dea": dea,
                    "signal_count": signal_count,
                }
            )

        # 卖出判断
        if not self.position.is_empty and self._should_sell(sell_signals):
            signal_count = sum(sell_signals)
            signal_desc = _get_signal_desc(sell_signals, indicator_names)
            strength = 0.5 + 0.15 * signal_count

            return Signal(
                type=SignalType.SELL,
                price=candle.close,
                timestamp=candle.timestamp,
                reason=f"多指标卖出信号 ({signal_count}/3): {signal_desc}",
                strength=strength,
                metadata={
                    "rsi": current_rsi,
                    "rsi_signal": rsi_sell,
                    "bb_signal": bb_sell,
                    "macd_signal": macd_sell,
                    "dif": dif,
                    "dea": dea,
                    "signal_count": signal_count,
                }
            )

        # 构建等待信号的原因
        rsi_str = f"RSI:{current_rsi:.1f}" if current_rsi else "RSI:N/A"
        return Signal(
            type=SignalType.HOLD,
            price=candle.close,
            timestamp=candle.timestamp,
            reason=f"等待共振信号 ({rsi_str})"
        )

    def get_params(self) -> Dict[str, Any]:
        """获取策略参数"""
        params = super().get_params()
        params.update({
            "rsi_period": self.hybrid_config.rsi_period,
            "rsi_overbought": self.hybrid_config.rsi_overbought,
            "rsi_oversold": self.hybrid_config.rsi_oversold,
            "bb_period": self.hybrid_config.bb_period,
            "bb_std": self.hybrid_config.bb_std,
            "macd_fast": self.hybrid_config.macd_fast,
            "macd_slow": self.hybrid_config.macd_slow,
            "macd_signal": self.hybrid_config.macd_signal,
            "signal_mode": self.hybrid_config.signal_mode,
        })
        return params


def create_hybrid_strategy(
    symbol: str = "BTC-USDT",
    timeframe: str = "1H",
    initial_capital: float = 10000,
    stop_loss: float = 0.05,
    take_profit: float = 0.10,
    position_size: float = 0.5,
    signal_mode: str = "majority",
) -> HybridStrategy:
    """
    创建多指标混合策略实例

    Args:
        symbol: 交易对
        timeframe: 时间周期
        initial_capital: 初始资金
        stop_loss: 止损比例
        take_profit: 止盈比例
        position_size: 仓位比例
        signal_mode: 信号模式 (any/majority/all)

    Returns:
        混合策略实例
    """
    config = HybridConfig(
        symbol=symbol,
        timeframe=timeframe,
        initial_capital=initial_capital,
        stop_loss=stop_loss,
        take_profit=take_profit,
        position_size=position_size,
        signal_mode=signal_mode,
    )
    return HybridStrategy(config)
