# 网格交易策略
# 在价格区间内设置多个网格，低买高卖赚取差价

from typing import List, Dict, Any, Optional, Literal
from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from .base import BaseStrategy, StrategyConfig, Signal, SignalType


# Pydantic 参数 Schema（用于插件化架构）
class GridParams(BaseModel):
    """网格策略参数 Schema"""
    upper_price: float = Field(
        ...,  # 必填
        gt=0,
        json_schema_extra={"label": "网格上限", "order": 1, "required": True}
    )
    lower_price: float = Field(
        ...,  # 必填
        gt=0,
        json_schema_extra={"label": "网格下限", "order": 2, "required": True}
    )
    grid_count: int = Field(
        default=10, ge=2, le=100,
        json_schema_extra={"label": "网格数量", "order": 3}
    )
    grid_type: Literal["arithmetic", "geometric"] = Field(
        default="arithmetic",
        json_schema_extra={
            "label": "网格类型",
            "order": 4,
            "options": ["arithmetic", "geometric"]
        }
    )


@dataclass
class GridConfig(StrategyConfig):
    """网格策略配置"""
    name: str = "网格交易策略"
    # 网格参数
    upper_price: float = 50000          # 网格上限价格
    lower_price: float = 40000          # 网格下限价格
    grid_count: int = 10                # 网格数量
    # 网格类型
    grid_type: str = "arithmetic"       # arithmetic(等差) / geometric(等比)


@dataclass
class GridLevel:
    """网格档位"""
    index: int                          # 网格索引
    price: float                        # 网格价格
    buy_price: float = 0.0              # 实际买入价格
    quantity: float = 0.0               # 该档位持仓数量
    is_holding: bool = False            # 是否持有该档位


class GridStrategy(BaseStrategy):
    """
    网格交易策略

    交易逻辑：
    - 将价格区间划分为多个网格
    - 价格下跌穿越网格线时买入
    - 价格上涨穿越网格线时卖出对应的下方持仓
    - 适合震荡行情，不适合单边行情

    改进点：
    1. 正确追踪每个网格的持仓状态
    2. 动态计算可用资金
    3. 支持同一根K线内多次触发
    """

    # 策略元数据（用于自动注册）
    strategy_id = "grid"
    strategy_name = "网格交易策略"
    strategy_description = "在价格区间内设置网格，低买高卖赚取差价，适合震荡行情"
    params_schema = GridParams

    def __init__(self, config: GridConfig):
        super().__init__(config)
        self.grid_config = config
        self.grid_levels: List[GridLevel] = []
        self._last_price = 0.0
        self._capital_per_grid = 0.0
        self._pending_signals: List[Signal] = []  # 缓存的信号队列
        self._init_grids()

    @classmethod
    def create_instance(
        cls,
        symbol: str = "BTC-USDT",
        timeframe: str = "1H",
        initial_capital: float = 10000,
        position_size: float = 0.8,
        stop_loss: float = 0.0,
        take_profit: float = 0.0,
        inst_type: str = "SPOT",
        **strategy_params
    ) -> "GridStrategy":
        """工厂方法：创建策略实例"""
        # 验证并获取策略参数
        params = GridParams(**strategy_params)

        config = GridConfig(
            symbol=symbol,
            timeframe=timeframe,
            inst_type=inst_type,
            initial_capital=initial_capital,
            position_size=position_size,
            stop_loss=0,        # 网格策略通常不设止损
            take_profit=0,      # 网格策略通常不设止盈
            upper_price=params.upper_price,
            lower_price=params.lower_price,
            grid_count=params.grid_count,
            grid_type=params.grid_type,
        )
        return cls(config)

    @classmethod
    def validate_params(cls, params: Dict[str, Any]) -> None:
        """验证策略参数"""
        validated = GridParams(**params)
        if validated.upper_price <= validated.lower_price:
            raise ValueError("网格上限价格必须大于下限价格")
        # 验证网格价差是否合理
        price_range_ratio = (validated.upper_price - validated.lower_price) / validated.lower_price
        if price_range_ratio < 0.01:
            raise ValueError("网格价格区间过小（至少1%），无法有效套利")

    def _init_grids(self):
        """初始化网格档位"""
        upper = self.grid_config.upper_price
        lower = self.grid_config.lower_price
        count = self.grid_config.grid_count

        self.grid_levels = []

        if self.grid_config.grid_type == "geometric":
            # 等比网格
            ratio = (upper / lower) ** (1 / count)
            for i in range(count + 1):
                price = lower * (ratio ** i)
                self.grid_levels.append(GridLevel(index=i, price=price))
        else:
            # 等差网格
            step = (upper - lower) / count
            for i in range(count + 1):
                price = lower + step * i
                self.grid_levels.append(GridLevel(index=i, price=price))

        # 计算每个网格分配的资金
        total_capital = self.config.initial_capital * self.config.position_size
        self._capital_per_grid = total_capital / count

    def calculate_indicators(self, candles: List) -> Dict[str, List[float]]:
        """网格策略不需要技术指标"""
        return {}

    def on_init(self, candles: List):
        """初始化"""
        super().on_init(candles)
        # 重置网格状态
        for level in self.grid_levels:
            level.buy_price = 0.0
            level.quantity = 0.0
            level.is_holding = False

        # 清空信号队列
        self._pending_signals = []

        # 记录初始价格
        if candles:
            self._last_price = candles[0].close

    def generate_signal(self, index: int) -> Signal:
        """生成交易信号"""
        candle = self.get_candle(index)
        if not candle:
            return Signal(type=SignalType.HOLD, price=0, timestamp=0)

        current_price = candle.close

        # 如果有待处理的信号，返回第一个
        if self._pending_signals:
            return self._pending_signals.pop(0)

        # 价格超出网格范围
        if current_price > self.grid_config.upper_price:
            self._last_price = current_price
            return Signal(
                type=SignalType.HOLD,
                price=current_price,
                timestamp=candle.timestamp,
                reason="价格高于网格上限"
            )

        if current_price < self.grid_config.lower_price:
            self._last_price = current_price
            return Signal(
                type=SignalType.HOLD,
                price=current_price,
                timestamp=candle.timestamp,
                reason="价格低于网格下限"
            )

        # 检查所有穿越的网格（处理价格跳跃）
        signals = self._check_all_grid_crossings(current_price, candle.timestamp)

        self._last_price = current_price

        if signals:
            # 第一个信号立即返回，其余放入队列
            if len(signals) > 1:
                self._pending_signals.extend(signals[1:])
            return signals[0]

        return Signal(
            type=SignalType.HOLD,
            price=current_price,
            timestamp=candle.timestamp,
            reason="等待网格触发"
        )

    def _check_all_grid_crossings(self, current_price: float, timestamp: int) -> List[Signal]:
        """检查所有穿越的网格，返回信号列表"""
        signals = []

        # 确定价格移动方向
        price_dropped = current_price < self._last_price
        price_rose = current_price > self._last_price

        if price_dropped:
            # 价格下跌，检查买入机会
            # 从高到低遍历网格，找所有被穿越的网格
            for level in reversed(self.grid_levels):
                # 价格从上方穿越网格线
                if self._last_price >= level.price > current_price:
                    if not level.is_holding:
                        # 计算买入数量（状态更新延迟到 on_trade 回调）
                        quantity = self._capital_per_grid / current_price

                        signals.append(Signal(
                            type=SignalType.BUY,
                            price=current_price,
                            timestamp=timestamp,
                            reason=f"触发买入网格 #{level.index+1} (网格价:{level.price:.2f})",
                            metadata={
                                "grid_index": level.index,
                                "grid_price": level.price,
                                "grid_quantity": quantity,
                                "is_grid_trade": True,
                            }
                        ))

        elif price_rose:
            # 价格上涨，检查卖出机会
            # 从低到高遍历网格，找所有被穿越的网格
            for level in self.grid_levels:
                # 价格从下方穿越网格线
                if self._last_price <= level.price < current_price:
                    # 查找下方最近的持仓网格
                    sell_level = self._find_holding_level_below(level.index)
                    if sell_level and sell_level.is_holding and sell_level.quantity > 0:
                        quantity = sell_level.quantity
                        buy_price = sell_level.buy_price

                        signals.append(Signal(
                            type=SignalType.SELL,
                            price=current_price,
                            timestamp=timestamp,
                            reason=f"触发卖出网格 #{level.index+1} (卖出档位 #{sell_level.index+1})",
                            metadata={
                                "grid_index": level.index,
                                "grid_price": level.price,
                                "grid_quantity": quantity,
                                "buy_grid_index": sell_level.index,
                                "buy_price": buy_price,
                                "is_grid_trade": True,
                            }
                        ))

        return signals

    def _find_holding_level_below(self, target_index: int) -> Optional[GridLevel]:
        """查找目标索引下方最近的持仓网格"""
        for i in range(target_index - 1, -1, -1):
            if self.grid_levels[i].is_holding:
                return self.grid_levels[i]
        return None

    def on_trade(self, trade):
        """
        成交回调：根据实际成交更新网格档位状态

        解决问题：网格策略在生成信号时就更新档位状态，但回测引擎可能因资金不足
        而减少实际买入数量，导致策略状态与实际持仓不一致。

        现在状态更新延迟到 on_trade 回调，使用实际成交数量更新档位。
        """
        super().on_trade(trade)

        # 只处理网格交易
        if not trade.metadata.get("is_grid_trade"):
            return

        grid_index = trade.metadata.get("grid_index")
        if grid_index is None:
            return

        if trade.side.value == "buy":
            # 买入成交：更新对应网格档位的持仓状态
            if 0 <= grid_index < len(self.grid_levels):
                level = self.grid_levels[grid_index]
                level.is_holding = True
                level.quantity = trade.quantity  # 使用实际成交数量
                level.buy_price = trade.price

        elif trade.side.value == "sell":
            # 卖出成交：清空对应网格档位
            buy_grid_index = trade.metadata.get("buy_grid_index")
            if buy_grid_index is not None and 0 <= buy_grid_index < len(self.grid_levels):
                level = self.grid_levels[buy_grid_index]
                # 部分卖出：减少数量
                level.quantity -= trade.quantity
                if level.quantity <= 0:
                    level.is_holding = False
                    level.quantity = 0
                    level.buy_price = 0

    def get_grid_status(self) -> List[Dict[str, Any]]:
        """获取网格状态"""
        return [
            {
                "index": level.index,
                "price": level.price,
                "is_holding": level.is_holding,
                "quantity": level.quantity,
                "buy_price": level.buy_price,
            }
            for level in self.grid_levels
        ]

    def get_holding_count(self) -> int:
        """获取当前持仓的网格数量"""
        return sum(1 for level in self.grid_levels if level.is_holding)

    def get_params(self) -> Dict[str, Any]:
        """获取策略参数"""
        params = super().get_params()
        params.update({
            "upper_price": self.grid_config.upper_price,
            "lower_price": self.grid_config.lower_price,
            "grid_count": self.grid_config.grid_count,
            "grid_type": self.grid_config.grid_type,
            "capital_per_grid": self._capital_per_grid,
        })
        return params


def create_grid_strategy(
    symbol: str = "BTC-USDT",
    timeframe: str = "1H",
    inst_type: str = "SPOT",
    initial_capital: float = 10000,
    upper_price: float = 50000,
    lower_price: float = 40000,
    grid_count: int = 10,
    position_size: float = 0.8,
    grid_type: str = "arithmetic",
) -> GridStrategy:
    """
    创建网格策略实例

    Args:
        symbol: 交易对
        timeframe: 时间周期
        initial_capital: 初始资金
        upper_price: 网格上限
        lower_price: 网格下限
        grid_count: 网格数量
        position_size: 总仓位比例
        grid_type: 网格类型 (arithmetic/geometric)

    Returns:
        策略实例
    """
    config = GridConfig(
        symbol=symbol,
        timeframe=timeframe,
        inst_type=inst_type,
        initial_capital=initial_capital,
        upper_price=upper_price,
        lower_price=lower_price,
        grid_count=grid_count,
        position_size=position_size,
        grid_type=grid_type,
        stop_loss=0,        # 网格策略通常不设止损
        take_profit=0,      # 网格策略通常不设止盈
    )
    return GridStrategy(config)
