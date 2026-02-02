# 策略基类
# 定义所有交易策略的通用接口和基础功能
# 支持策略自动发现和注册的插件化架构

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Type, ClassVar
from enum import Enum
from datetime import datetime

from pydantic import BaseModel


# 全局策略注册表
_strategy_registry: Dict[str, Type["BaseStrategy"]] = {}


def _json_type_to_simple(json_type: str) -> str:
    """将 JSON Schema 类型转换为简单类型"""
    type_map = {
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "string": "string",
        "array": "array",
        "object": "object",
    }
    return type_map.get(json_type, json_type)


class SignalType(Enum):
    """交易信号类型"""
    BUY = "buy"           # 买入
    SELL = "sell"         # 卖出
    HOLD = "hold"         # 持有/观望


class OrderSide(Enum):
    """订单方向"""
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    """订单类型"""
    MARKET = "market"     # 市价单
    LIMIT = "limit"       # 限价单


@dataclass
class Signal:
    """交易信号"""
    type: SignalType                    # 信号类型
    price: float                        # 当前价格
    timestamp: int                      # 时间戳
    reason: str = ""                    # 信号原因
    strength: float = 1.0               # 信号强度 (0-1)
    metadata: Dict[str, Any] = field(default_factory=dict)  # 额外数据


@dataclass
class Order:
    """订单"""
    side: OrderSide                     # 买/卖
    price: float                        # 价格
    quantity: float                     # 数量
    timestamp: int                      # 时间戳
    order_type: OrderType = OrderType.MARKET
    order_id: str = ""
    status: str = "pending"             # pending/filled/cancelled


@dataclass
class Position:
    """持仓"""
    symbol: str                         # 交易对
    quantity: float = 0.0               # 持仓数量
    avg_price: float = 0.0              # 平均成本价
    unrealized_pnl: float = 0.0         # 未实现盈亏
    realized_pnl: float = 0.0           # 已实现盈亏

    @property
    def is_empty(self) -> bool:
        """是否空仓"""
        return self.quantity <= 0

    def update_unrealized_pnl(self, current_price: float):
        """更新未实现盈亏"""
        if self.quantity > 0:
            self.unrealized_pnl = (current_price - self.avg_price) * self.quantity


@dataclass
class Trade:
    """成交记录"""
    timestamp: int                      # 成交时间
    side: OrderSide                     # 买/卖
    price: float                        # 成交价格
    quantity: float                     # 成交数量
    commission: float = 0.0             # 手续费
    pnl: float = 0.0                    # 该笔交易盈亏（平仓时）
    metadata: Dict[str, Any] = field(default_factory=dict)  # 信号元数据（用于网格等策略的状态同步）

    @property
    def value(self) -> float:
        """成交金额"""
        return self.price * self.quantity

    @property
    def datetime(self) -> datetime:
        """成交时间"""
        return datetime.fromtimestamp(self.timestamp / 1000)


@dataclass
class StrategyConfig:
    """策略配置"""
    name: str = "BaseStrategy"
    symbol: str = "BTC-USDT"
    timeframe: str = "1H"
    inst_type: str = "SPOT"              # 交易类型: SPOT/SWAP/FUTURES
    # 资金配置
    initial_capital: float = 10000.0    # 初始资金
    position_size: float = 0.1          # 每次开仓比例 (0-1)
    max_position: float = 1.0           # 最大仓位比例
    # 风控配置
    stop_loss: float = 0.05             # 止损比例
    take_profit: float = 0.10           # 止盈比例
    # 交易成本
    commission_rate: float = 0.001      # 手续费率 (0.1%)
    slippage: float = 0.0005            # 滑点 (0.05%)
    # 额外参数
    params: Dict[str, Any] = field(default_factory=dict)


class BaseStrategy(ABC):
    """
    策略基类
    所有具体策略需要继承此类并实现相关方法

    插件化架构：
    - 子类只需定义 strategy_id, strategy_name, params_schema 类属性即可自动注册
    - 通过 create_instance() 类方法创建实例
    - 通过 get_metadata() 获取策略元数据（含参数 schema）
    """

    # 策略元数据（子类必须覆盖这些属性才能注册）
    strategy_id: ClassVar[Optional[str]] = None
    strategy_name: ClassVar[Optional[str]] = None
    strategy_description: ClassVar[str] = ""
    params_schema: ClassVar[Optional[Type[BaseModel]]] = None

    def __init_subclass__(cls, **kwargs):
        """子类自动注册钩子"""
        super().__init_subclass__(**kwargs)

        # 只有定义了 strategy_id 和 strategy_name 的具体策略才注册
        if cls.strategy_id and cls.strategy_name:
            _strategy_registry[cls.strategy_id] = cls

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
    ) -> "BaseStrategy":
        """
        工厂方法：创建策略实例

        子类应该重写此方法以处理策略特定的参数

        Args:
            symbol: 交易对
            timeframe: 时间周期
            initial_capital: 初始资金
            position_size: 仓位比例
            stop_loss: 止损比例
            take_profit: 止盈比例
            inst_type: 交易类型 (SPOT/SWAP/FUTURES)
            **strategy_params: 策略特定参数

        Returns:
            策略实例
        """
        raise NotImplementedError(f"策略 {cls.strategy_id} 未实现 create_instance 方法")

    @classmethod
    def validate_params(cls, params: Dict[str, Any]) -> None:
        """
        验证策略参数

        Args:
            params: 参数字典

        Raises:
            ValueError: 参数验证失败
        """
        if cls.params_schema:
            # 使用 Pydantic 模型验证参数
            cls.params_schema(**params)

    @classmethod
    def get_metadata(cls) -> Dict[str, Any]:
        """
        获取策略元数据

        Returns:
            包含策略信息和参数 schema 的字典
        """
        result = {
            "id": cls.strategy_id,
            "name": cls.strategy_name,
            "description": cls.strategy_description,
        }

        # 如果定义了参数 schema，生成 JSON Schema
        if cls.params_schema:
            schema = cls.params_schema.model_json_schema()
            # 转换为前端友好的参数列表格式
            params_list = []
            properties = schema.get("properties", {})
            for name, prop in properties.items():
                param_info = {
                    "name": name,
                    "label": prop.get("label", prop.get("title", name)),
                    "type": _json_type_to_simple(prop.get("type", "string")),
                    "default": prop.get("default"),
                    "description": prop.get("description", ""),
                }
                # 添加范围限制
                if "minimum" in prop:
                    param_info["min"] = prop["minimum"]
                elif "exclusiveMinimum" in prop:
                    param_info["min"] = prop["exclusiveMinimum"]
                if "maximum" in prop:
                    param_info["max"] = prop["maximum"]
                elif "exclusiveMaximum" in prop:
                    param_info["max"] = prop["exclusiveMaximum"]
                if "enum" in prop:
                    param_info["options"] = prop["enum"]
                    param_info["type"] = "select"
                # 检查是否必填
                if name in schema.get("required", []):
                    param_info["required"] = True
                params_list.append(param_info)
            result["params"] = params_list
        else:
            result["params"] = []

        return result

    def __init__(self, config: StrategyConfig):
        """
        初始化策略

        Args:
            config: 策略配置
        """
        self.config = config
        self.position = Position(symbol=config.symbol)
        self.trades: List[Trade] = []
        self.signals: List[Signal] = []

        # 内部状态
        self._current_index = 0
        self._candles = []
        self._indicators = {}

    @property
    def name(self) -> str:
        """策略名称"""
        return self.config.name

    @abstractmethod
    def calculate_indicators(self, candles: List) -> Dict[str, List[float]]:
        """
        计算策略所需的技术指标

        Args:
            candles: K线数据列表

        Returns:
            指标字典，key为指标名，value为指标值列表
        """
        pass

    @abstractmethod
    def generate_signal(self, index: int) -> Signal:
        """
        生成交易信号

        Args:
            index: 当前K线索引

        Returns:
            交易信号
        """
        pass

    def on_init(self, candles: List):
        """
        策略初始化，在回测开始前调用

        Args:
            candles: 全部K线数据
        """
        self._candles = candles
        self._indicators = self.calculate_indicators(candles)

    def on_bar(self, index: int) -> Optional[Signal]:
        """
        每根K线调用一次

        Args:
            index: 当前K线索引

        Returns:
            交易信号或None
        """
        self._current_index = index

        # 检查止损止盈
        if not self.position.is_empty:
            current_price = self._candles[index].close
            self.position.update_unrealized_pnl(current_price)

            # 检查止损
            if self._check_stop_loss(current_price):
                return Signal(
                    type=SignalType.SELL,
                    price=current_price,
                    timestamp=self._candles[index].timestamp,
                    reason="止损触发"
                )

            # 检查止盈
            if self._check_take_profit(current_price):
                return Signal(
                    type=SignalType.SELL,
                    price=current_price,
                    timestamp=self._candles[index].timestamp,
                    reason="止盈触发"
                )

        # 生成策略信号
        return self.generate_signal(index)

    def on_trade(self, trade: Trade):
        """
        成交回调

        Args:
            trade: 成交记录
        """
        self.trades.append(trade)

    def on_finish(self):
        """回测结束回调"""
        pass

    def _check_stop_loss(self, current_price: float) -> bool:
        """检查是否触发止损"""
        # avg_price 异常为 0 时直接跳过，避免除零导致策略/引擎崩溃
        if self.position.is_empty or self.config.stop_loss <= 0 or self.position.avg_price <= 0:
            return False

        loss_ratio = (self.position.avg_price - current_price) / self.position.avg_price
        return loss_ratio >= self.config.stop_loss

    def _check_take_profit(self, current_price: float) -> bool:
        """检查是否触发止盈"""
        # avg_price 异常为 0 时直接跳过，避免除零导致策略/引擎崩溃
        if self.position.is_empty or self.config.take_profit <= 0 or self.position.avg_price <= 0:
            return False

        profit_ratio = (current_price - self.position.avg_price) / self.position.avg_price
        return profit_ratio >= self.config.take_profit

    def get_indicator(self, name: str, index: int) -> Optional[float]:
        """
        获取指定位置的指标值

        Args:
            name: 指标名称
            index: K线索引

        Returns:
            指标值，如果不存在或为NaN则返回None
        """
        if name not in self._indicators:
            return None

        values = self._indicators[name]
        if index < 0 or index >= len(values):
            return None

        value = values[index]
        if value is None or (isinstance(value, float) and (value != value)):  # NaN check
            return None

        return value

    def get_candle(self, index: int):
        """获取指定位置的K线"""
        if 0 <= index < len(self._candles):
            return self._candles[index]
        return None

    def get_current_candle(self):
        """获取当前K线"""
        return self.get_candle(self._current_index)

    def get_params(self) -> Dict[str, Any]:
        """获取策略参数"""
        return {
            "name": self.name,
            "symbol": self.config.symbol,
            "timeframe": self.config.timeframe,
            "initial_capital": self.config.initial_capital,
            "position_size": self.config.position_size,
            "stop_loss": self.config.stop_loss,
            "take_profit": self.config.take_profit,
            "commission_rate": self.config.commission_rate,
            **self.config.params
        }
