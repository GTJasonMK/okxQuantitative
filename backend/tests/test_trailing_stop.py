# 追踪止损测试

import pytest

from app.strategies.base import (
    BaseStrategy,
    OrderSide,
    Position,
    Signal,
    SignalType,
    StrategyConfig,
    Trade,
)


class SimpleTestStrategy(BaseStrategy):
    """始终发出买入信号的测试策略（用于测试追踪止损）"""

    strategy_id = None  # 不注册到全局注册表
    strategy_name = None

    def calculate_indicators(self, candles):
        pass

    def generate_signal(self, index):
        if self.position.is_empty and index == 0:
            return Signal(
                type=SignalType.BUY,
                price=self._candles[index].close,
                timestamp=self._candles[index].timestamp,
                reason="测试买入",
            )
        return None

    @classmethod
    def create_instance(cls, **kwargs):
        config = StrategyConfig(
            trailing_stop=kwargs.get("trailing_stop", 0.05),
            trailing_stop_activation=kwargs.get("trailing_stop_activation", 0.0),
            stop_loss=kwargs.get("stop_loss", 0.0),
            take_profit=kwargs.get("take_profit", 0.0),
        )
        return cls(config)


class FakeCandle:
    def __init__(self, close, timestamp=0):
        self.open = close
        self.high = close
        self.low = close
        self.close = close
        self.volume = 100
        self.volume_ccy = 0
        self.timestamp = timestamp


class TestTrailingStop:
    """追踪止损逻辑测试"""

    def test_trailing_stop_disabled(self):
        """trailing_stop=0 时不触发"""
        config = StrategyConfig(trailing_stop=0.0)
        strategy = SimpleTestStrategy(config)
        strategy.position = Position(symbol="BTC-USDT", quantity=1.0, avg_price=100)
        strategy._trailing_stop_highest = 120.0

        assert strategy._check_trailing_stop(90.0) is False

    def test_trailing_stop_triggers(self):
        """价格从最高点回落超过阈值触发"""
        config = StrategyConfig(trailing_stop=0.05)  # 5% 追踪止损
        strategy = SimpleTestStrategy(config)
        strategy.position = Position(symbol="BTC-USDT", quantity=1.0, avg_price=100)
        strategy._trailing_stop_highest = 120.0

        # 从 120 回落到 114 = 5% → 刚好触发
        assert strategy._check_trailing_stop(114.0) is True

    def test_trailing_stop_not_yet(self):
        """价格回落未达阈值不触发"""
        config = StrategyConfig(trailing_stop=0.05)
        strategy = SimpleTestStrategy(config)
        strategy.position = Position(symbol="BTC-USDT", quantity=1.0, avg_price=100)
        strategy._trailing_stop_highest = 120.0

        # 从 120 回落到 115 = 4.17% < 5%
        assert strategy._check_trailing_stop(115.0) is False

    def test_trailing_stop_with_activation(self):
        """设置激活条件：盈利达到阈值后才启用"""
        config = StrategyConfig(
            trailing_stop=0.05,
            trailing_stop_activation=0.10,  # 盈利 10% 后才激活
        )
        strategy = SimpleTestStrategy(config)
        strategy.position = Position(symbol="BTC-USDT", quantity=1.0, avg_price=100)
        strategy._trailing_stop_highest = 115.0

        # 价格在 109，盈利 9% < 10% 激活条件，不触发
        assert strategy._check_trailing_stop(109.0) is False

        # 价格在 111，盈利 11% > 10%，且从 115 回落 > 5%
        strategy._trailing_stop_highest = 120.0
        assert strategy._check_trailing_stop(113.0) is True

    def test_highest_price_resets_on_buy(self):
        """买入时重置最高价"""
        config = StrategyConfig(trailing_stop=0.05)
        strategy = SimpleTestStrategy(config)
        strategy._trailing_stop_highest = 200.0

        # 模拟买入回调
        strategy.position = Position(symbol="BTC-USDT", quantity=1.0, avg_price=100)
        trade = Trade(
            timestamp=1000,
            side=OrderSide.BUY,
            price=105.0,
            quantity=1.0,
        )
        strategy.on_trade(trade)

        assert strategy._trailing_stop_highest == 105.0

    def test_highest_price_updated_in_on_bar(self):
        """on_bar 中更新最高价"""
        config = StrategyConfig(trailing_stop=0.05, stop_loss=0, take_profit=0)
        strategy = SimpleTestStrategy(config)
        strategy.position = Position(symbol="BTC-USDT", quantity=1.0, avg_price=100)
        strategy._trailing_stop_highest = 100.0

        candles = [FakeCandle(close=110, timestamp=1000)]
        strategy._candles = candles

        strategy.on_bar(0)
        assert strategy._trailing_stop_highest == 110.0

    def test_empty_position_no_trigger(self):
        """空仓不触发"""
        config = StrategyConfig(trailing_stop=0.05)
        strategy = SimpleTestStrategy(config)
        strategy._trailing_stop_highest = 120.0

        assert strategy._check_trailing_stop(100.0) is False
