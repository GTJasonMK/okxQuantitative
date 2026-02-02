# 实时交易引擎
# 将策略信号转换为实际的 OKX 订单执行

import asyncio
from typing import Optional, Dict, Any, List, Protocol
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from threading import Lock

from ..strategies.base import BaseStrategy, Signal, SignalType, StrategyConfig, Trade, OrderSide
from ..core.data_fetcher import Candle


class TraderPort(Protocol):
    """交易执行器接口（用于降低 LiveTradingEngine 与具体实现的耦合）"""

    @property
    def is_available(self) -> bool: ...

    def place_order(
        self,
        inst_id: str,
        side: str,
        order_type: str,
        size: str,
        price: str = "",
        td_mode: str = "cash",
        client_order_id: str = "",
    ): ...

    def get_order(self, inst_id: str, order_id: str) -> Optional[Dict[str, Any]]: ...


class AccountPort(Protocol):
    """账户查询接口（用于降低 LiveTradingEngine 与具体实现的耦合）"""

    @property
    def is_available(self) -> bool: ...

    def get_max_avail_size(self, inst_id: str, td_mode: str = "cash", *, last_price: Optional[float] = None) -> Dict[str, Any]: ...


class CandleManagerPort(Protocol):
    """K 线获取接口（用于降低 LiveTradingEngine 与缓存/存储实现的耦合）"""

    def get_candles_cached(
        self,
        inst_id: str,
        timeframe: str,
        count: int = 100,
        *,
        inst_type: str = "SPOT",
    ) -> List[Candle]: ...


class LiveOrderStoragePort(Protocol):
    """实时交易订单持久化接口"""

    def save_live_order(
        self,
        *,
        order_id: str,
        inst_id: str,
        side: str,
        size: str,
        price: str,
        signal_type: str,
        success: bool,
        ts: str,
        strategy_id: str,
        strategy_name: str,
        error_message: str,
    ) -> Any: ...


class EngineStatus(Enum):
    """引擎状态"""
    STOPPED = "stopped"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    ERROR = "error"


@dataclass
class EngineState:
    """引擎状态快照"""
    status: EngineStatus = EngineStatus.STOPPED
    strategy_id: str = ""
    strategy_name: str = ""
    symbol: str = ""
    timeframe: str = ""
    inst_type: str = "SPOT"  # 交易类型: SPOT/SWAP/FUTURES
    start_time: Optional[datetime] = None
    last_signal_time: Optional[datetime] = None
    last_signal_type: str = ""
    total_signals: int = 0
    total_orders: int = 0
    successful_orders: int = 0
    failed_orders: int = 0
    error_message: str = ""


@dataclass
class OrderRecord:
    """订单记录"""
    timestamp: datetime
    signal_type: str
    order_id: str
    inst_id: str
    side: str
    size: str
    price: str
    success: bool
    error_message: str = ""


class LiveTradingEngine:
    """
    实时交易引擎

    负责：
    1. 定时获取最新行情数据
    2. 将数据传递给策略生成信号
    3. 将信号转换为实际订单
    4. 管理运行状态和错误处理
    """
    _instance: Optional['LiveTradingEngine'] = None
    _lock = Lock()

    def __new__(cls):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True

        # 核心组件
        self._trader: Optional[TraderPort] = None
        self._account: Optional[AccountPort] = None
        self._candle_manager: Optional[CandleManagerPort] = None
        self._storage: Optional[LiveOrderStoragePort] = None
        self._strategy: Optional[BaseStrategy] = None

        # 控制流锁：防止并发 start/stop 导致重复任务或状态错乱
        #
        # 注意：LiveTradingEngine 是单例对象，测试/热重载等场景可能跨事件循环复用该对象。
        # asyncio.Lock 会绑定创建它的事件循环；若跨 loop 复用会触发
        # "is bound to a different event loop" 异常。因此这里按当前运行 loop 延迟创建。
        self._control_lock: Optional[asyncio.Lock] = None
        self._control_lock_loop = None

        # 状态管理
        self._state = EngineState()
        self._running = False
        self._task: Optional[asyncio.Task] = None

        # 订单记录
        self._order_history: List[OrderRecord] = []
        self._max_history_size = 100

        # 配置
        self._check_interval = 60  # 默认60秒检查一次

    def _get_control_lock(self) -> asyncio.Lock:
        """获取与当前事件循环绑定的控制锁（避免跨 loop 复用导致 RuntimeError）"""
        loop = asyncio.get_running_loop()
        if self._control_lock is None or self._control_lock_loop is not loop:
            self._control_lock_loop = loop
            self._control_lock = asyncio.Lock()
        return self._control_lock

    @property
    def state(self) -> EngineState:
        """获取当前状态"""
        return self._state

    @property
    def is_running(self) -> bool:
        """是否正在运行"""
        return self._running and self._state.status in (EngineStatus.STARTING, EngineStatus.RUNNING)

    @property
    def order_history(self) -> List[OrderRecord]:
        """获取订单历史"""
        return self._order_history.copy()

    def configure(
        self,
        strategy: BaseStrategy,
        check_interval: int = 60,
        *,
        trader: TraderPort,
        account: AccountPort,
        candle_manager: CandleManagerPort,
        storage: LiveOrderStoragePort,
    ):
        """
        配置引擎

        Args:
            strategy: 策略实例
            check_interval: 检查间隔（秒）
            trader: 交易执行器（由调用方注入）
            account: 账户查询器（由调用方注入）
            candle_manager: K线/缓存管理器（由调用方注入）
            storage: 订单持久化存储（由调用方注入）
        """
        if self.is_running:
            raise RuntimeError("引擎运行中，无法修改配置")

        self._strategy = strategy
        self._check_interval = check_interval

        # 依赖注入：避免 LiveTradingEngine 直接依赖全局单例/配置，从而降低耦合并提升可测试性
        self._trader = trader
        self._account = account
        self._candle_manager = candle_manager
        self._storage = storage

        # 更新状态
        self._state.strategy_id = strategy.strategy_id or ""
        self._state.strategy_name = strategy.name
        self._state.symbol = strategy.config.symbol
        self._state.timeframe = strategy.config.timeframe
        self._state.inst_type = strategy.config.inst_type

    async def start_with_strategy(
        self,
        strategy: BaseStrategy,
        check_interval: int = 60,
        *,
        trader: TraderPort,
        account: AccountPort,
        candle_manager: CandleManagerPort,
        storage: LiveOrderStoragePort,
    ):
        """
        原子化的“配置并启动”

        解决的问题：
        - 并发调用 start / 重复点击导致多任务循环、重复下单
        - BackgroundTasks 延迟启动期间窗口期允许重复启动/覆盖配置
        """
        async with self._get_control_lock():
            if self._state.status in (EngineStatus.STARTING, EngineStatus.RUNNING, EngineStatus.STOPPING):
                raise RuntimeError(f"引擎正在运行或启动中 (status={self._state.status.value})")

            # 复用现有配置逻辑
            self.configure(
                strategy=strategy,
                check_interval=check_interval,
                trader=trader,
                account=account,
                candle_manager=candle_manager,
                storage=storage,
            )
            await self._start_unlocked()

    async def _start_unlocked(self):
        """启动引擎（要求调用方已持有 _control_lock）"""
        # 防重入：启动阶段也算“在运行”
        if self._state.status in (EngineStatus.STARTING, EngineStatus.RUNNING, EngineStatus.STOPPING):
            raise RuntimeError(f"引擎已在运行或启动中 (status={self._state.status.value})")

        if not self._strategy:
            raise ValueError("未配置策略")

        if not self._trader or not self._trader.is_available:
            raise ValueError("交易 API 不可用，请检查 API 配置")

        if not self._account or not self._account.is_available:
            raise ValueError("账户 API 不可用，请检查 API 配置")

        if not self._candle_manager:
            raise ValueError("行情管理器未注入，无法获取K线数据")

        if not self._storage:
            raise ValueError("订单存储未注入，无法持久化订单记录")

        self._running = True
        self._state.status = EngineStatus.STARTING
        self._state.start_time = datetime.now()
        self._state.error_message = ""

        # 初始化策略
        try:
            await self._init_strategy()
            self._state.status = EngineStatus.RUNNING
            print(f"[LiveEngine] 启动成功: {self._state.strategy_name} @ {self._state.symbol}")

            # 启动主循环
            self._task = asyncio.create_task(self._run_loop())

        except Exception as e:
            self._state.status = EngineStatus.ERROR
            self._state.error_message = str(e)
            self._running = False
            raise

    async def start(self):
        """启动引擎"""
        async with self._get_control_lock():
            await self._start_unlocked()

    async def stop(self):
        """停止引擎"""
        async with self._get_control_lock():
            if not self._running:
                return

            print("[LiveEngine] 正在停止...")
            self._state.status = EngineStatus.STOPPING
            self._running = False

            if self._task:
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

            self._state.status = EngineStatus.STOPPED
            print("[LiveEngine] 已停止")

    async def _init_strategy(self):
        """初始化策略"""
        # 获取历史数据初始化策略
        manager = self._candle_manager
        if not manager:
            raise ValueError("行情管理器未注入")
        candles = await asyncio.to_thread(
            manager.get_candles_cached,
            inst_id=self._state.symbol,
            timeframe=self._state.timeframe,
            count=200,  # 获取足够的历史数据
            inst_type=self._state.inst_type,
        )

        if not candles:
            raise ValueError(f"无法获取 {self._state.symbol} 的历史数据")

        # 调用策略的初始化方法
        self._strategy.on_init(candles)
        print(f"[LiveEngine] 策略初始化完成，历史数据: {len(candles)} 根K线")

    async def _run_loop(self):
        """主运行循环"""
        while self._running:
            try:
                await self._check_and_execute()
            except Exception as e:
                print(f"[LiveEngine] 执行错误: {e}")
                self._state.error_message = str(e)

            # 等待下一次检查
            await asyncio.sleep(self._check_interval)

    async def _check_and_execute(self):
        """检查信号并执行"""
        # 获取最新数据
        manager = self._candle_manager
        if not manager:
            print("[LiveEngine] 行情管理器未注入")
            return
        candles = await asyncio.to_thread(
            manager.get_candles_cached,
            inst_id=self._state.symbol,
            timeframe=self._state.timeframe,
            count=200,
            inst_type=self._state.inst_type,
        )

        if not candles:
            print("[LiveEngine] 无法获取最新数据")
            return

        # 更新策略数据
        self._strategy._candles = candles
        self._strategy._indicators = self._strategy.calculate_indicators(candles)

        # 获取信号
        index = len(candles) - 1
        signal = self._strategy.on_bar(index)

        if not signal:
            return

        # 记录信号
        self._state.total_signals += 1
        self._state.last_signal_time = datetime.now()
        self._state.last_signal_type = signal.type.value

        # 执行信号
        if signal.type != SignalType.HOLD:
            await self._execute_signal(signal)

    async def _execute_signal(self, signal: Signal):
        """执行交易信号"""
        print(f"[LiveEngine] 收到信号: {signal.type.value} @ {signal.price}")

        # 计算交易数量
        size = await self._calculate_size(signal)
        if not size or float(size) <= 0:
            print("[LiveEngine] 计算数量为0，跳过执行")
            return

        # 下单（使用 asyncio.to_thread 避免阻塞事件循环）
        side = "buy" if signal.type == SignalType.BUY else "sell"
        result = await asyncio.to_thread(
            self._trader.place_order,
            inst_id=self._state.symbol,
            side=side,
            order_type="market",  # 使用市价单
            size=size
        )

        # 尽量用“实际成交”信息更新仓位与记录：
        # - place_order 成功仅代表委托受理，不一定代表已完全成交
        # - 若直接用 signal.price 与请求 size 更新仓位，遇到部分成交/滑点会造成策略仓位与真实账户偏离
        executed_size = size
        executed_price = signal.price
        if result.success and result.order_id:
            try:
                # 市价单通常很快成交；这里做少量轮询，尽量拿到 fillSz/avgPx
                for _ in range(5):
                    detail = await asyncio.to_thread(self._trader.get_order, self._state.symbol, result.order_id)
                    if not detail:
                        break

                    fill_sz_raw = detail.get("fillSz", "") or "0"
                    avg_px_raw = detail.get("avgPx", "") or "0"
                    try:
                        fill_sz = float(fill_sz_raw)
                        avg_px = float(avg_px_raw)
                    except (TypeError, ValueError):
                        fill_sz = 0.0
                        avg_px = 0.0

                    if fill_sz > 0:
                        executed_size = str(fill_sz)
                        if avg_px > 0:
                            executed_price = avg_px
                        break

                    # 仍未拿到成交信息：短暂等待后再查一次
                    await asyncio.sleep(0.2)
            except Exception as e:
                print(f"[LiveEngine] 查询订单成交信息失败，将回退使用请求数量/信号价格: {e}")

        # 记录订单
        record = OrderRecord(
            timestamp=datetime.now(),
            signal_type=signal.type.value,
            order_id=result.order_id if result.success else "",
            inst_id=self._state.symbol,
            side=side,
            size=executed_size,
            price=str(executed_price),
            success=result.success,
            error_message=result.error_message
        )
        await self._add_order_record(record)

        # 更新统计
        self._state.total_orders += 1
        if result.success:
            self._state.successful_orders += 1
            print(f"[LiveEngine] 订单成功: {result.order_id}")
            # 更新策略持仓状态（同步实际成交后的持仓）
            await self._sync_position(signal, executed_size, executed_price)
        else:
            self._state.failed_orders += 1
            print(f"[LiveEngine] 订单失败: {result.error_message}")

    async def _sync_position(self, signal: Signal, size: str, fill_price: Optional[float] = None):
        """
        同步策略持仓状态

        在实时交易中，订单执行后需要更新策略的 position 对象，
        否则策略会一直认为空仓，导致：
        - 买入信号反复触发
        - 卖出信号永远不触发
        - 止损止盈检查无效

        同时调用策略的 on_trade 回调，用于网格等策略更新内部状态
        """
        try:
            qty = float(size)
            price = float(fill_price) if fill_price is not None else float(signal.price)
            if signal.type == SignalType.BUY:
                # 买入：增加持仓
                old_qty = self._strategy.position.quantity
                old_cost = self._strategy.position.avg_price * old_qty
                new_cost = price * qty
                new_qty = old_qty + qty
                if new_qty > 0:
                    self._strategy.position.quantity = new_qty
                    self._strategy.position.avg_price = (old_cost + new_cost) / new_qty
            elif signal.type == SignalType.SELL:
                # 卖出：减少持仓
                self._strategy.position.quantity = max(0, self._strategy.position.quantity - qty)
                if self._strategy.position.quantity == 0:
                    self._strategy.position.avg_price = 0.0
            print(f"[LiveEngine] 持仓更新: qty={self._strategy.position.quantity:.6f}, avg_price={self._strategy.position.avg_price:.2f}")

            # 调用策略的 on_trade 回调（用于网格等策略更新内部状态）
            trade = Trade(
                timestamp=int(datetime.now().timestamp() * 1000),
                side=OrderSide.BUY if signal.type == SignalType.BUY else OrderSide.SELL,
                price=price,
                quantity=qty,
                commission=0.0,
                pnl=0.0,
                metadata=signal.metadata or {},
            )
            self._strategy.on_trade(trade)

        except Exception as e:
            print(f"[LiveEngine] 同步持仓状态失败: {e}")

    async def _calculate_size(self, signal: Signal) -> str:
        """
        计算交易数量

        根据策略配置的仓位比例和账户可用余额计算
        网格策略会使用信号中指定的 grid_quantity
        """
        try:
            # 检查是否为网格交易（使用信号中指定的数量）
            is_grid_trade = signal.metadata.get("is_grid_trade", False) if signal.metadata else False
            grid_quantity = signal.metadata.get("grid_quantity") if signal.metadata else None

            if is_grid_trade and grid_quantity:
                # 网格交易：使用信号指定的数量
                # 但仍需检查是否超过账户可用余额
                max_size = await asyncio.to_thread(
                    self._account.get_max_avail_size,
                    inst_id=self._state.symbol,
                    td_mode="cash",
                    last_price=float(signal.price) if signal.price is not None else None,
                )

                if signal.type == SignalType.BUY:
                    max_buy = float(max_size.get("maxBuy", 0))
                    size = min(grid_quantity, max_buy)  # 取较小值
                    return str(round(size, 6)) if size > 0 else "0"

                elif signal.type == SignalType.SELL:
                    max_sell = float(max_size.get("maxSell", 0))
                    strategy_qty = float(getattr(self._strategy.position, "quantity", 0) or 0)
                    size = min(float(grid_quantity), max_sell, strategy_qty)  # 部分卖出
                    return str(round(size, 6)) if size > 0 else "0"

            # 非网格交易：按仓位比例计算
            max_size = await asyncio.to_thread(
                self._account.get_max_avail_size,
                inst_id=self._state.symbol,
                td_mode="cash",
                last_price=float(signal.price) if signal.price is not None else None,
            )

            if signal.type == SignalType.BUY:
                max_buy = float(max_size.get("maxBuy", 0))
                # 按仓位比例计算
                size = max_buy * self._strategy.config.position_size
                return str(round(size, 6))

            elif signal.type == SignalType.SELL:
                max_sell = float(max_size.get("maxSell", 0))
                # 风险控制：只卖出策略自身维护的持仓数量，避免误卖出账户中“非策略持仓”的资产。
                # 同时用 max_sell 做上限，避免账户实际可卖数量不足导致交易所拒单。
                strategy_qty = float(getattr(self._strategy.position, "quantity", 0) or 0)
                size = min(max_sell, strategy_qty)
                return str(round(size, 6)) if size > 0 else "0"

        except Exception as e:
            print(f"[LiveEngine] 计算数量失败: {e}")
            return "0"

        return "0"

    async def _add_order_record(self, record: OrderRecord):
        """添加订单记录（同时保存到内存和数据库）"""
        self._order_history.append(record)
        # 限制内存中的历史记录数量
        if len(self._order_history) > self._max_history_size:
            self._order_history = self._order_history[-self._max_history_size:]

        # 持久化到数据库
        try:
            storage = self._storage
            if not storage:
                return
            # sqlite 写入可能较慢，放到线程池避免阻塞 WS 推送/引擎循环
            await asyncio.to_thread(
                storage.save_live_order,
                order_id=record.order_id,
                inst_id=record.inst_id,
                side=record.side,
                size=record.size,
                price=record.price,
                signal_type=record.signal_type,
                success=record.success,
                ts=record.timestamp.isoformat(),
                strategy_id=self._state.strategy_id,
                strategy_name=self._state.strategy_name,
                error_message=record.error_message,
            )
        except Exception as e:
            print(f"[LiveEngine] 保存订单记录到数据库失败: {e}")

    def get_status_dict(self) -> Dict[str, Any]:
        """获取状态字典（用于 API 返回）"""
        return {
            "status": self._state.status.value,
            "strategy_id": self._state.strategy_id,
            "strategy_name": self._state.strategy_name,
            "symbol": self._state.symbol,
            "timeframe": self._state.timeframe,
            "inst_type": self._state.inst_type,
            "start_time": self._state.start_time.isoformat() if self._state.start_time else None,
            "last_signal_time": self._state.last_signal_time.isoformat() if self._state.last_signal_time else None,
            "last_signal_type": self._state.last_signal_type,
            "total_signals": self._state.total_signals,
            "total_orders": self._state.total_orders,
            "successful_orders": self._state.successful_orders,
            "failed_orders": self._state.failed_orders,
            "error_message": self._state.error_message,
            "check_interval": self._check_interval,
        }


# 便捷函数
def get_live_engine() -> LiveTradingEngine:
    """获取单例引擎"""
    return LiveTradingEngine()
