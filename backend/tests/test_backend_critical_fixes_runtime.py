import asyncio

import pytest


@pytest.mark.asyncio
async def test_restart_ws_manager_notifies_listeners(monkeypatch):
    """
    restart_ws_manager() 必须通知监听器，否则前端 WS 连接不断开但推送会静默中断。
    """
    import app.core.websocket_manager as ws_mod

    class DummyManager:
        async def stop(self):
            return None

    async def fake_start_ws_manager(mode=None):
        # restart_ws_manager 会调用 start_ws_manager(mode=None)
        ws_mod._ws_managers = {"simulated": DummyManager()}
        return ws_mod._ws_managers["simulated"]

    # 隔离全局状态，避免污染其他测试
    ws_mod._ws_managers = {"simulated": DummyManager()}
    ws_mod._ws_restart_listeners.clear()

    monkeypatch.setattr(ws_mod, "start_ws_manager", fake_start_ws_manager)

    called = {"count": 0}

    async def listener():
        called["count"] += 1

    ws_mod.add_ws_restart_listener(listener)

    await ws_mod.restart_ws_manager()
    assert called["count"] == 1


@pytest.mark.asyncio
async def test_live_engine_start_with_strategy_is_atomic(monkeypatch):
    """
    验证 LiveTradingEngine.start_with_strategy 能防止重复启动（STARTING 阶段也算启动中）。
    """
    import app.live.engine as engine_mod
    from app.core.data_fetcher import Candle

    # 重置单例，避免跨测试状态泄漏
    engine_mod.LiveTradingEngine._instance = None

    class DummyTrader:
        is_available = True

        def place_order(self, *args, **kwargs):  # pragma: no cover
            raise AssertionError("测试不应触发真实下单逻辑")

    class DummyAccount:
        is_available = True

        def get_max_avail_size(self, *args, **kwargs):  # pragma: no cover
            return {"maxBuy": "0", "maxSell": "0"}

    class DummyManager:
        def get_candles_cached(self, *args, **kwargs):
            # 返回 1 根 K 线即可通过初始化
            return [
                Candle(
                    timestamp=1,
                    open=1.0,
                    high=1.0,
                    low=1.0,
                    close=1.0,
                    volume=0.0,
                    volume_ccy=0.0,
                )
            ]

    class DummyStorage:
        def save_live_order(self, *args, **kwargs):  # pragma: no cover
            return None

    class DummyConfig:
        symbol = "BTC-USDT"
        timeframe = "1H"
        inst_type = "SPOT"
        position_size = 0.1

    class DummyStrategy:
        strategy_id = "dummy"
        name = "Dummy"
        config = DummyConfig()

        def on_init(self, candles):
            return None

        def calculate_indicators(self, candles):  # pragma: no cover
            return {}

        def on_bar(self, index):  # pragma: no cover
            return None

        def on_trade(self, trade):  # pragma: no cover
            return None

    async def fake_run_loop(self):
        # 避免测试中真正执行 _check_and_execute
        await asyncio.sleep(3600)

    monkeypatch.setattr(engine_mod.LiveTradingEngine, "_run_loop", fake_run_loop, raising=True)

    engine = engine_mod.get_live_engine()

    await engine.start_with_strategy(
        strategy=DummyStrategy(),
        check_interval=1,
        trader=DummyTrader(),
        account=DummyAccount(),
        candle_manager=DummyManager(),
        storage=DummyStorage(),
    )
    assert engine.is_running is True

    with pytest.raises(RuntimeError):
        await engine.start_with_strategy(
            strategy=DummyStrategy(),
            check_interval=1,
            trader=DummyTrader(),
            account=DummyAccount(),
            candle_manager=DummyManager(),
            storage=DummyStorage(),
        )

    await engine.stop()
    assert engine.state.status.value == "stopped"


@pytest.mark.asyncio
async def test_live_engine_calculate_size_sell_is_capped_by_strategy_position(monkeypatch):
    """
    风险控制：SELL 信号的下单数量不得超过策略自身维护的持仓数量。

    否则在账户存在“非策略持仓”时，可能把账户可卖的资产全部卖出，造成严重误操作（实盘风险极高）。
    """
    import app.live.engine as engine_mod
    from app.strategies.base import Signal, SignalType, Position

    # 重置单例，避免跨测试状态泄漏
    engine_mod.LiveTradingEngine._instance = None

    class DummyTrader:
        is_available = True

    class DummyAccount:
        is_available = True

        def get_max_avail_size(self, *args, **kwargs):
            # 模拟账户可卖数量很大（例如账户里还有“非策略持仓”）
            return {"maxBuy": "0", "maxSell": "10"}

    class DummyManager:
        def get_candles_cached(self, *args, **kwargs):  # pragma: no cover
            return []

    class DummyStorage:
        def save_live_order(self, *args, **kwargs):  # pragma: no cover
            return None

    class DummyConfig:
        symbol = "BTC-USDT"
        timeframe = "1H"
        inst_type = "SPOT"
        position_size = 0.1

    class DummyStrategy:
        strategy_id = "dummy"
        name = "Dummy"
        config = DummyConfig()
        position = Position(symbol="BTC-USDT")

        def on_init(self, candles):  # pragma: no cover
            return None

        def calculate_indicators(self, candles):  # pragma: no cover
            return {}

        def on_bar(self, index):  # pragma: no cover
            return None

        def on_trade(self, trade):  # pragma: no cover
            return None

    engine = engine_mod.get_live_engine()
    strategy = DummyStrategy()
    engine.configure(
        strategy=strategy,
        check_interval=1,
        trader=DummyTrader(),
        account=DummyAccount(),
        candle_manager=DummyManager(),
        storage=DummyStorage(),
    )

    signal = Signal(type=SignalType.SELL, price=100.0, timestamp=1)

    # 1) 策略持仓为 0.5，账户可卖为 10：必须只卖出 0.5
    strategy.position.quantity = 0.5
    size = await engine._calculate_size(signal)
    assert size == "0.5"

    # 2) 策略空仓时，即使账户可卖>0，也不应下单卖出
    strategy.position.quantity = 0.0
    size2 = await engine._calculate_size(signal)
    assert size2 == "0"


@pytest.mark.asyncio
async def test_live_engine_calculate_size_sell_is_capped_by_strategy_owned_quantity():
    """SELL 数量应受“策略归属仓位”限制，避免误卖账户里非策略来源仓位。"""
    import app.live.engine as engine_mod
    from app.strategies.base import Signal, SignalType, Position

    engine_mod.LiveTradingEngine._instance = None

    class DummyTrader:
        is_available = True

    class DummyAccount:
        is_available = True

        def get_max_avail_size(self, *args, **kwargs):
            return {"maxBuy": "0", "maxSell": "10"}

    class DummyManager:
        def get_candles_cached(self, *args, **kwargs):  # pragma: no cover
            return []

    class DummyStorage:
        def save_live_order(self, *args, **kwargs):  # pragma: no cover
            return None

    class DummyConfig:
        symbol = "BTC-USDT"
        timeframe = "1H"
        inst_type = "SPOT"
        position_size = 0.1

    class DummyStrategy:
        strategy_id = "owned_qty_guard"
        name = "OwnedQtyGuard"
        config = DummyConfig()
        position = Position(symbol="BTC-USDT")

        def on_init(self, candles):  # pragma: no cover
            return None

        def calculate_indicators(self, candles):  # pragma: no cover
            return {}

        def on_bar(self, index):  # pragma: no cover
            return None

        def on_trade(self, trade):  # pragma: no cover
            return None

    engine = engine_mod.get_live_engine()
    strategy = DummyStrategy()
    engine.configure(
        strategy=strategy,
        check_interval=1,
        trader=DummyTrader(),
        account=DummyAccount(),
        candle_manager=DummyManager(),
        storage=DummyStorage(),
    )

    # 账户可卖 10，策略名义仓位 1.0，但“策略归属仓位”只有 0.2，只能卖 0.2。
    strategy.position.quantity = 1.0
    engine._owned_qty_ready = True
    engine._strategy_owned_qty = 0.2

    signal = Signal(type=SignalType.SELL, price=100.0, timestamp=1)
    size = await engine._calculate_size(signal)
    assert size == "0.2"


@pytest.mark.asyncio
async def test_live_engine_reconcile_restored_order_rebaseline_avoids_restart_double_count(monkeypatch):
    """重启恢复订单首轮仅对齐基线，不应把停机期间成交再次累计到策略仓位。"""
    import app.live.engine as engine_mod
    from app.core.data_fetcher import Candle
    from app.strategies.base import Position

    engine_mod.LiveTradingEngine._instance = None

    class DummyTrader:
        is_available = True
        mode = "simulated"

        def place_order(self, **kwargs):  # pragma: no cover
            raise AssertionError("不应触发下单")

        def get_order(self, inst_id: str, order_id: str = "", client_order_id: str = ""):
            return {"ordId": "", "fillSz": "1", "avgPx": "100", "state": "filled"}

    class DummyAccount:
        is_available = True

        def get_max_avail_size(self, *args, **kwargs):
            return {"maxBuy": "0", "maxSell": "0"}

        def get_balance(self, ccy: str = ""):
            return {"details": [{"ccy": "BTC", "availBal": "1.0", "frozenBal": "0"}]}

    class DummyManager:
        def get_candles_cached(self, *args, **kwargs):
            return [
                Candle(
                    timestamp=1,
                    open=200.0,
                    high=200.0,
                    low=200.0,
                    close=200.0,
                    volume=0.0,
                    volume_ccy=0.0,
                )
            ]

    class DummyStorage:
        def __init__(self):
            self.execution_updates = []

        def save_live_order(self, **kwargs):
            return True

        def get_cost_basis(self, mode: str, ccy: str = ""):
            return {"BTC": {"avg_cost": 100.0}}

        def get_unreconciled_live_orders(self, mode: str, inst_id: str = "", strategy_id: str = "", limit: int = 200):
            return [
                {
                    "id": 1,
                    "order_id": "",
                    "client_order_id": "clid-restart-1",
                    "inst_id": "BTC-USDT",
                    "side": "buy",
                    "size": "0.4",
                    "price": "100",
                    "signal_type": "buy",
                    "success": True,
                    "error_message": "订单部分成交，补偿同步中",
                    "mode": mode,
                    "strategy_id": "restart_rebaseline",
                    "strategy_name": "RestartRebaseline",
                    "timestamp": "2026-02-09T00:00:00",
                }
            ]

        def get_live_orders(self, limit: int = 50, mode: str = "", strategy_id: str = ""):
            return [
                {
                    "inst_id": "BTC-USDT",
                    "side": "buy",
                    "size": "0.4",
                    "success": True,
                }
            ]

        def update_live_order_execution(self, **kwargs):
            self.execution_updates.append(kwargs)
            return True

    class DummyConfig:
        symbol = "BTC-USDT"
        timeframe = "1H"
        inst_type = "SPOT"
        position_size = 0.1

    class DummyStrategy:
        strategy_id = "restart_rebaseline"
        name = "RestartRebaseline"
        config = DummyConfig()
        position = Position(symbol="BTC-USDT")

        def on_init(self, candles):
            self._candles = candles
            self._indicators = {}

        def calculate_indicators(self, candles):
            return {}

        def on_bar(self, index):
            return None

        def on_trade(self, trade):
            return None

    async def fake_run_loop(self):
        await asyncio.sleep(3600)

    monkeypatch.setattr(engine_mod.LiveTradingEngine, "_run_loop", fake_run_loop, raising=True)

    engine = engine_mod.get_live_engine()
    strategy = DummyStrategy()

    await engine.start_with_strategy(
        strategy=strategy,
        check_interval=1,
        trader=DummyTrader(),
        account=DummyAccount(),
        candle_manager=DummyManager(),
        storage=DummyStorage(),
    )

    assert strategy.position.quantity == pytest.approx(1.0)
    await engine._reconcile_pending_orders()

    # 若发生重复累计，这里会变成 1.6
    assert strategy.position.quantity == pytest.approx(1.0)
    # 基线对齐后，归属仓位应同步到完整成交量（0.4 -> 1.0）。
    assert engine._strategy_owned_qty == pytest.approx(1.0)
    assert len(engine._pending_orders) == 0

    await engine.stop()


@pytest.mark.asyncio
async def test_live_engine_execute_signal_waits_core_finish_when_cancelled(monkeypatch):
    """取消执行任务时应等待核心下单链路结束，避免丢失落库步骤。"""
    import app.live.engine as engine_mod
    from app.strategies.base import Position, Signal, SignalType

    engine_mod.LiveTradingEngine._instance = None

    class Dummy:
        is_available = True

    class DummyStorage:
        def save_live_order(self, **kwargs):
            return True

    class DummyConfig:
        symbol = "BTC-USDT"
        timeframe = "1H"
        inst_type = "SPOT"
        position_size = 0.1

    class DummyStrategy:
        strategy_id = "cancel_guard"
        name = "CancelGuard"
        config = DummyConfig()
        position = Position(symbol="BTC-USDT")

        def on_init(self, candles):
            return None

        def calculate_indicators(self, candles):
            return {}

        def on_bar(self, index):
            return None

        def on_trade(self, trade):
            return None

    engine = engine_mod.get_live_engine()
    engine.configure(
        strategy=DummyStrategy(),
        check_interval=1,
        trader=Dummy(),
        account=Dummy(),
        candle_manager=Dummy(),
        storage=DummyStorage(),
    )

    finished = {"done": False}

    async def fake_core(self, signal):
        await asyncio.sleep(0.01)
        finished["done"] = True

    monkeypatch.setattr(engine_mod.LiveTradingEngine, "_execute_signal_core", fake_core, raising=True)

    signal = Signal(type=SignalType.BUY, price=100.0, timestamp=1)
    task = asyncio.create_task(engine._execute_signal(signal))
    await asyncio.sleep(0)
    task.cancel()

    with pytest.raises(asyncio.CancelledError):
        await task

    assert finished["done"] is True


@pytest.mark.asyncio
async def test_live_engine_hydrate_strategy_owned_quantity_is_order_independent():
    """策略归属仓位回填应与返回顺序无关，避免倒序记录导致净仓位算错。"""
    import app.live.engine as engine_mod
    from app.strategies.base import Position

    engine_mod.LiveTradingEngine._instance = None

    class Dummy:
        is_available = True
        mode = "simulated"

    class DummyStorage:
        def save_live_order(self, **kwargs):
            return True

        def get_live_orders(self, limit: int = 50, mode: str = "", strategy_id: str = ""):
            # 倒序返回：先看到卖单，再看到买单（真实查询通常按时间倒序）。
            return [
                {"inst_id": "BTC-USDT", "side": "sell", "size": "1", "success": True},
                {"inst_id": "BTC-USDT", "side": "buy", "size": "1", "success": True},
            ]

    class DummyConfig:
        symbol = "BTC-USDT"
        timeframe = "1H"
        inst_type = "SPOT"
        position_size = 0.1

    class DummyStrategy:
        strategy_id = "owned_qty_order_independent"
        name = "OwnedQtyOrderIndependent"
        config = DummyConfig()
        position = Position(symbol="BTC-USDT")

        def on_init(self, candles):  # pragma: no cover
            return None

        def calculate_indicators(self, candles):  # pragma: no cover
            return {}

        def on_bar(self, index):  # pragma: no cover
            return None

        def on_trade(self, trade):  # pragma: no cover
            return None

    engine = engine_mod.get_live_engine()
    engine.configure(
        strategy=DummyStrategy(),
        check_interval=1,
        trader=Dummy(),
        account=Dummy(),
        candle_manager=Dummy(),
        storage=DummyStorage(),
    )

    await engine._hydrate_strategy_owned_quantity()
    assert engine._owned_qty_ready is True
    assert engine._strategy_owned_qty == pytest.approx(0.0)


@pytest.mark.asyncio
async def test_live_engine_check_and_execute_skips_duplicate_bar_signal():
    """同一根 K 线只处理一次信号，避免周期内重复下单。"""
    import app.live.engine as engine_mod
    from app.core.data_fetcher import Candle
    from app.strategies.base import Position, Signal, SignalType

    engine_mod.LiveTradingEngine._instance = None

    class DummyTrader:
        is_available = True
        mode = "simulated"

    class DummyAccount:
        is_available = True

        def get_max_avail_size(self, *args, **kwargs):
            return {"maxBuy": "1", "maxSell": "1"}

        def get_balance(self, ccy: str = ""):
            return {"totalEq": "1000", "details": []}

    class DummyManager:
        def get_candles_cached(self, *args, **kwargs):
            return [
                Candle(
                    timestamp=123456789,
                    open=100.0,
                    high=100.0,
                    low=100.0,
                    close=100.0,
                    volume=1.0,
                    volume_ccy=1.0,
                )
            ]

    class DummyStorage:
        def save_live_order(self, **kwargs):
            return True

    class DummyConfig:
        symbol = "BTC-USDT"
        timeframe = "1H"
        inst_type = "SPOT"
        position_size = 0.1

    class DummyStrategy:
        strategy_id = "dup_bar_guard"
        name = "DupBarGuard"
        config = DummyConfig()
        position = Position(symbol="BTC-USDT")

        def __init__(self):
            self.calls = 0

        def on_init(self, candles):
            return None

        def calculate_indicators(self, candles):
            return {}

        def on_bar(self, index):
            self.calls += 1
            return Signal(type=SignalType.BUY, price=100.0, timestamp=123456789)

        def on_trade(self, trade):
            return None

    engine = engine_mod.get_live_engine()
    strategy = DummyStrategy()
    engine.configure(
        strategy=strategy,
        check_interval=1,
        trader=DummyTrader(),
        account=DummyAccount(),
        candle_manager=DummyManager(),
        storage=DummyStorage(),
    )

    executed = {"count": 0}

    async def fake_execute(signal):
        executed["count"] += 1

    engine._execute_signal = fake_execute  # type: ignore[method-assign]

    await engine._check_and_execute()
    await engine._check_and_execute()

    assert strategy.calls == 1
    assert executed["count"] == 1
    assert engine.state.total_signals == 1


@pytest.mark.asyncio
async def test_live_engine_execute_signal_fallback_on_non_exception_error_code():
    """下单返回失败码时也应通过 clOrdId 兜底查询，避免漏记真实成交订单。"""
    import app.live.engine as engine_mod
    from app.strategies.base import Position, Signal, SignalType

    engine_mod.LiveTradingEngine._instance = None

    class DummyTrader:
        is_available = True
        mode = "simulated"

        def place_order(self, **kwargs):
            return type("Result", (), {
                "success": False,
                "order_id": "",
                "client_order_id": kwargs.get("client_order_id", ""),
                "error_code": "51000",
                "error_message": "mock non-zero code",
            })()

        def get_order(self, inst_id: str, order_id: str = "", client_order_id: str = ""):
            if client_order_id:
                return {"ordId": "ord-fallback-1", "fillSz": "0.2", "avgPx": "101", "state": "filled"}
            return None

    class DummyAccount:
        is_available = True

        def get_max_avail_size(self, *args, **kwargs):
            return {"maxBuy": "1", "maxSell": "1"}

        def get_balance(self, ccy: str = ""):
            return {"totalEq": "1000", "details": []}

    class DummyManager:
        def get_candles_cached(self, *args, **kwargs):  # pragma: no cover
            return []

    class DummyStorage:
        def __init__(self):
            self.saved = []

        def save_live_order(self, **kwargs):
            self.saved.append(kwargs)
            return True

    class DummyConfig:
        symbol = "BTC-USDT"
        timeframe = "1H"
        inst_type = "SPOT"
        position_size = 0.1

    class DummyStrategy:
        strategy_id = "fallback_error_code"
        name = "FallbackErrorCode"
        config = DummyConfig()
        position = Position(symbol="BTC-USDT")

        def on_init(self, candles):
            return None

        def calculate_indicators(self, candles):
            return {}

        def on_bar(self, index):
            return None

        def on_trade(self, trade):
            return None

    storage = DummyStorage()
    engine = engine_mod.get_live_engine()
    strategy = DummyStrategy()
    engine.configure(
        strategy=strategy,
        check_interval=1,
        trader=DummyTrader(),
        account=DummyAccount(),
        candle_manager=DummyManager(),
        storage=storage,
    )

    signal = Signal(type=SignalType.BUY, price=100.0, timestamp=42)
    await engine._execute_signal_core(signal)

    assert engine.state.successful_orders == 1
    assert engine.state.failed_orders == 0
    assert strategy.position.quantity == pytest.approx(0.2)
    assert engine.order_history[-1].success is True
    assert "失败码" in engine.order_history[-1].error_message

