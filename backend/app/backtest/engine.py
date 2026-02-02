# 回测引擎核心
# 负责模拟交易执行和资金管理

from typing import List, Dict, Any, Optional, Type
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

from ..strategies.base import (
    BaseStrategy, StrategyConfig,
    Signal, SignalType, Order, OrderSide, OrderType, Trade, Position
)
from ..core.data_fetcher import Candle


@dataclass
class AccountState:
    """账户状态快照"""
    timestamp: int                      # 时间戳
    cash: float                         # 现金
    position_value: float               # 持仓市值
    total_equity: float                 # 总权益
    position_quantity: float            # 持仓数量
    unrealized_pnl: float               # 未实现盈亏


@dataclass
class BacktestConfig:
    """回测配置"""
    initial_capital: float = 10000.0    # 初始资金
    commission_rate: float = 0.001      # 手续费率
    slippage: float = 0.0005            # 滑点
    enable_fractional: bool = True      # 是否允许小数交易


@dataclass
class BacktestResult:
    """回测结果"""
    # 基本信息
    strategy_name: str
    symbol: str
    timeframe: str
    start_time: str
    end_time: str
    duration_days: int

    # 资金曲线
    equity_curve: List[AccountState] = field(default_factory=list)

    # 交易记录
    trades: List[Trade] = field(default_factory=list)
    signals: List[Signal] = field(default_factory=list)

    # 绩效指标
    initial_capital: float = 0.0
    final_capital: float = 0.0
    total_return: float = 0.0           # 总收益率 (%)
    annual_return: float = 0.0          # 年化收益率 (%)
    max_drawdown: float = 0.0           # 最大回撤 (%)
    max_drawdown_duration: int = 0      # 最大回撤持续时间 (K线数)
    sharpe_ratio: float = 0.0           # 夏普比率
    sortino_ratio: float = 0.0          # 索提诺比率
    calmar_ratio: float = 0.0           # 卡尔玛比率
    win_rate: float = 0.0               # 胜率 (%)
    profit_factor: float = 0.0          # 盈亏比
    total_trades: int = 0               # 总交易次数
    winning_trades: int = 0             # 盈利交易次数
    losing_trades: int = 0              # 亏损交易次数
    avg_profit: float = 0.0             # 平均盈利
    avg_loss: float = 0.0               # 平均亏损
    largest_profit: float = 0.0         # 最大单笔盈利
    largest_loss: float = 0.0           # 最大单笔亏损
    avg_holding_period: float = 0.0     # 平均持仓周期
    total_commission: float = 0.0       # 总手续费

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "strategy_name": self.strategy_name,
            "symbol": self.symbol,
            "timeframe": self.timeframe,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_days": self.duration_days,
            "initial_capital": self.initial_capital,
            "final_capital": round(self.final_capital, 2),
            "total_return": round(self.total_return, 2),
            "annual_return": round(self.annual_return, 2),
            "max_drawdown": round(self.max_drawdown, 2),
            "sharpe_ratio": round(self.sharpe_ratio, 2),
            "sortino_ratio": round(self.sortino_ratio, 2),
            "calmar_ratio": round(self.calmar_ratio, 2),
            "win_rate": round(self.win_rate, 2),
            "profit_factor": round(self.profit_factor, 2),
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "avg_profit": round(self.avg_profit, 2),
            "avg_loss": round(self.avg_loss, 2),
            "largest_profit": round(self.largest_profit, 2),
            "largest_loss": round(self.largest_loss, 2),
            "total_commission": round(self.total_commission, 2),
            "equity_curve": [
                {
                    "timestamp": s.timestamp,
                    "equity": round(s.total_equity, 2),
                    "cash": round(s.cash, 2),
                    "position_value": round(s.position_value, 2),
                }
                for s in self.equity_curve[::max(1, len(self.equity_curve) // 500)]  # 采样降低数据量
            ],
            "trades": [
                {
                    "timestamp": t.timestamp,
                    "datetime": t.datetime.isoformat(),
                    "side": t.side.value,
                    "price": round(t.price, 4),
                    "quantity": round(t.quantity, 6),
                    "value": round(t.value, 2),
                    "commission": round(t.commission, 4),
                    "pnl": round(t.pnl, 2),
                }
                for t in self.trades
            ],
        }


class BacktestEngine:
    """
    回测引擎

    负责：
    1. 加载历史K线数据
    2. 按时间顺序模拟行情
    3. 执行策略信号
    4. 管理资金和持仓
    5. 计算绩效指标
    """

    def __init__(self, config: BacktestConfig = None):
        """
        初始化回测引擎

        Args:
            config: 回测配置
        """
        self.config = config or BacktestConfig()

        # 账户状态
        self.cash = 0.0
        self.position = Position(symbol="")
        self.trades: List[Trade] = []
        self.equity_curve: List[AccountState] = []

        # 回测数据
        self.candles: List[Candle] = []
        self.current_index = 0

    def run(
        self,
        strategy: BaseStrategy,
        candles: List[Candle],
    ) -> BacktestResult:
        """
        运行回测

        Args:
            strategy: 策略实例
            candles: K线数据

        Returns:
            回测结果
        """
        if not candles:
            raise ValueError("K线数据为空")

        # 初始化
        self._reset()
        self.candles = candles
        self.cash = strategy.config.initial_capital
        self.position = Position(symbol=strategy.config.symbol)

        # 关键：让策略和引擎共享同一个 Position 对象
        # 否则引擎执行买卖更新的是引擎的 position，
        # 而策略在 generate_signal() 中检查的是策略自己的 position（永远空仓），
        # 导致策略永远无法触发卖出信号、止损止盈也失效
        strategy.position = self.position

        # 策略初始化
        strategy.on_init(candles)

        # 逐根K线回测
        for i in range(len(candles)):
            self.current_index = i
            candle = candles[i]

            # 更新持仓市值
            self.position.update_unrealized_pnl(candle.close)

            # 获取策略信号
            signal = strategy.on_bar(i)

            # 执行信号
            if signal and signal.type != SignalType.HOLD:
                self._execute_signal(signal, strategy)

            # 记录账户状态
            self._record_state(candle)

        # 策略结束回调
        strategy.on_finish()

        # 计算绩效指标
        result = self._calculate_metrics(strategy, candles)

        return result

    def _reset(self):
        """重置引擎状态"""
        self.cash = 0.0
        self.position = Position(symbol="")
        self.trades = []
        self.equity_curve = []
        self.candles = []
        self.current_index = 0

    def _execute_signal(self, signal: Signal, strategy: BaseStrategy):
        """
        执行交易信号

        Args:
            signal: 交易信号
            strategy: 策略实例
        """
        candle = self.candles[self.current_index]

        # 计算滑点后的执行价格
        slippage_factor = 1 + self.config.slippage if signal.type == SignalType.BUY else 1 - self.config.slippage
        exec_price = signal.price * slippage_factor

        if signal.type == SignalType.BUY:
            self._execute_buy(exec_price, strategy, signal)
        elif signal.type == SignalType.SELL:
            self._execute_sell(exec_price, strategy, signal)

    def _execute_buy(self, price: float, strategy: BaseStrategy, signal: Signal):
        """执行买入"""
        # 检查是否为网格交易（使用策略指定的数量）
        is_grid_trade = signal.metadata.get("is_grid_trade", False) if signal.metadata else False
        grid_quantity = signal.metadata.get("grid_quantity") if signal.metadata else None

        if is_grid_trade and grid_quantity:
            # 网格交易：使用策略指定的数量
            quantity = grid_quantity
            buy_value = quantity * price
            commission = buy_value * self.config.commission_rate

            # 检查现金是否足够
            if self.cash < buy_value + commission:
                # 现金不足，减少买入数量
                available = self.cash / (1 + self.config.commission_rate)
                quantity = available / price
                if quantity <= 0:
                    return
                buy_value = quantity * price
                commission = buy_value * self.config.commission_rate
        else:
            # 普通交易：使用仓位比例计算
            # 检查是否超过最大仓位限制
            max_position = getattr(strategy.config, 'max_position', 1.0)
            current_position_value = self.position.quantity * price
            total_equity = self.cash + current_position_value
            current_position_ratio = current_position_value / total_equity if total_equity > 0 else 0

            if current_position_ratio >= max_position:
                # 已达到最大仓位，不再加仓
                return

            # 计算可用于本次买入的资金（考虑最大仓位限制）
            remaining_position_ratio = max_position - current_position_ratio
            target_ratio = min(strategy.config.position_size, remaining_position_ratio)
            available_cash = self.cash * target_ratio

            commission = available_cash * self.config.commission_rate
            buy_value = available_cash - commission

            if buy_value <= 0:
                return

            quantity = buy_value / price

        if not self.config.enable_fractional:
            quantity = int(quantity)
            if quantity <= 0:
                return
            buy_value = quantity * price
            commission = buy_value * self.config.commission_rate

        # 更新持仓（成本计算包含手续费）
        actual_cost = buy_value + commission  # 实际花费包含手续费
        if self.position.quantity > 0:
            # 加仓：计算新的平均成本（手续费计入成本）
            total_quantity = self.position.quantity + quantity
            # 原成本 = 原数量 * 原均价（已包含之前的手续费摊销）
            total_cost = self.position.avg_price * self.position.quantity + actual_cost
            self.position.avg_price = total_cost / total_quantity
            self.position.quantity = total_quantity
        else:
            # 新开仓：均价 = 总成本 / 数量
            self.position.quantity = quantity
            self.position.avg_price = actual_cost / quantity

        # 扣除现金
        self.cash -= actual_cost

        # 记录交易（传递信号元数据，用于网格等策略的状态同步）
        trade = Trade(
            timestamp=signal.timestamp,
            side=OrderSide.BUY,
            price=price,
            quantity=quantity,
            commission=commission,
            metadata=signal.metadata or {},
        )
        self.trades.append(trade)

        # 同步未实现盈亏（用于当根K线的状态记录展示）
        candle = self.candles[self.current_index]
        self.position.update_unrealized_pnl(candle.close)

        strategy.on_trade(trade)

    def _execute_sell(self, price: float, strategy: BaseStrategy, signal: Signal):
        """执行卖出"""
        if self.position.is_empty:
            return

        # 检查是否为网格交易（使用策略指定的数量进行部分卖出）
        is_grid_trade = signal.metadata.get("is_grid_trade", False) if signal.metadata else False
        grid_quantity = signal.metadata.get("grid_quantity") if signal.metadata else None

        if is_grid_trade and grid_quantity:
            # 网格交易：部分卖出
            quantity = min(grid_quantity, self.position.quantity)
        else:
            # 普通交易：全部卖出
            quantity = self.position.quantity

        sell_value = quantity * price
        commission = sell_value * self.config.commission_rate

        # 计算盈亏（按照卖出比例计算成本）
        cost_basis = self.position.avg_price * quantity
        pnl = sell_value - commission - cost_basis

        # 更新现金
        self.cash += (sell_value - commission)

        # 记录已实现盈亏
        self.position.realized_pnl += pnl

        # 记录交易（传递信号元数据，用于网格等策略的状态同步）
        trade = Trade(
            timestamp=signal.timestamp,
            side=OrderSide.SELL,
            price=price,
            quantity=quantity,
            commission=commission,
            pnl=pnl,
            metadata=signal.metadata or {},
        )
        self.trades.append(trade)

        # 更新持仓
        self.position.quantity -= quantity
        if self.position.quantity <= 0:
            # 清空持仓
            self.position.quantity = 0
            self.position.avg_price = 0
            self.position.unrealized_pnl = 0

        # 同步未实现盈亏（用于当根K线的状态记录展示）
        candle = self.candles[self.current_index]
        self.position.update_unrealized_pnl(candle.close)

        # 成交回调放在持仓更新之后，保证策略看到的是“成交后的仓位状态”
        strategy.on_trade(trade)

    def _record_state(self, candle: Candle):
        """记录账户状态"""
        position_value = self.position.quantity * candle.close
        total_equity = self.cash + position_value

        state = AccountState(
            timestamp=candle.timestamp,
            cash=self.cash,
            position_value=position_value,
            total_equity=total_equity,
            position_quantity=self.position.quantity,
            unrealized_pnl=self.position.unrealized_pnl,
        )
        self.equity_curve.append(state)

    def _calculate_metrics(
        self,
        strategy: BaseStrategy,
        candles: List[Candle]
    ) -> BacktestResult:
        """计算绩效指标"""
        from .metrics import calculate_metrics

        # duration_days：用于展示/落库的“回测覆盖天数”，不能用K线数量代替
        # 用首尾时间戳计算“包含首尾两天”的天数：floor(diff_days) + 1
        duration_days = 0
        if candles:
            if len(candles) >= 2:
                first_ts = candles[0].timestamp
                last_ts = candles[-1].timestamp
                duration_days = max(1, int((last_ts - first_ts) / (1000 * 86400)) + 1)
            else:
                duration_days = 1

        result = BacktestResult(
            strategy_name=strategy.name,
            symbol=strategy.config.symbol,
            timeframe=strategy.config.timeframe,
            start_time=candles[0].datetime.isoformat() if candles else "",
            end_time=candles[-1].datetime.isoformat() if candles else "",
            duration_days=duration_days,
            equity_curve=self.equity_curve,
            trades=self.trades,
            initial_capital=strategy.config.initial_capital,
        )

        # 使用指标计算模块计算详细指标
        calculate_metrics(result)

        return result
