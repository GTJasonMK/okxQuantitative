import asyncio

import pytest


def test_live_engine_configure_resets_runtime_counters():
    """新会话配置时应清空上一轮运行统计，避免状态串扰。"""
    import app.live.engine as engine_mod
    from app.strategies.base import Position

    engine_mod.LiveTradingEngine._instance = None

    class Dummy:
        is_available = True
        mode = "simulated"

    class DummyStorage:
        def save_live_order(self, **kwargs):
            return True

    class DummyConfig:
        symbol = "BTC-USDT"
        timeframe = "1H"
        inst_type = "SPOT"
        position_size = 0.1

    class DummyStrategy:
        strategy_id = "dummy_reset"
        name = "DummyReset"
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
    engine._state.total_signals = 11
    engine._state.total_orders = 9
    engine._state.failed_orders = 2

    engine.configure(
        strategy=DummyStrategy(),
        check_interval=1,
        trader=Dummy(),
        account=Dummy(),
        candle_manager=Dummy(),
        storage=DummyStorage(),
    )

    assert engine.state.total_signals == 0
    assert engine.state.total_orders == 0
    assert engine.state.failed_orders == 0


@pytest.mark.asyncio
async def test_live_engine_reconciles_delayed_fills_without_double_counting():
    """下单初期未成交时，应通过补偿同步按增量回填仓位且不重复记账。"""
    import app.live.engine as engine_mod
    from app.core.data_fetcher import Candle
    from app.strategies.base import Position, Signal, SignalType

    engine_mod.LiveTradingEngine._instance = None

    class DummyTrader:
        is_available = True
        mode = "simulated"

        def __init__(self):
            self._query_count = 0

        def place_order(self, **kwargs):
            return type("Result", (), {
                "success": True,
                "order_id": "ord-delayed-1",
                "client_order_id": kwargs.get("client_order_id", ""),
                "error_code": "",
                "error_message": "",
            })()

        def get_order(self, inst_id: str, order_id: str = "", client_order_id: str = ""):
            self._query_count += 1
            # 第一次查询：委托已受理但未成交
            if self._query_count == 1:
                return {"ordId": "ord-delayed-1", "fillSz": "0", "avgPx": "0", "state": "live"}
            # 第二次查询：部分成交 0.4
            if self._query_count == 2:
                return {"ordId": "ord-delayed-1", "fillSz": "0.4", "avgPx": "101", "state": "partially_filled"}
            # 第三次查询：全部成交（累计 1.0，累计均价 101.6）
            return {"ordId": "ord-delayed-1", "fillSz": "1", "avgPx": "101.6", "state": "filled"}

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
                    timestamp=1,
                    open=100.0,
                    high=100.0,
                    low=100.0,
                    close=100.0,
                    volume=0.0,
                    volume_ccy=0.0,
                )
            ]

    class DummyStorage:
        def save_live_order(self, **kwargs):
            return True

        def get_cost_basis(self, mode: str, ccy: str = ""):
            return {}

    class DummyConfig:
        symbol = "BTC-USDT"
        timeframe = "1H"
        inst_type = "SPOT"
        position_size = 1.0

    class DummyStrategy:
        strategy_id = "dummy_delayed"
        name = "DummyDelayed"
        config = DummyConfig()
        position = Position(symbol="BTC-USDT")

        def __init__(self):
            self.trades = []

        def on_init(self, candles):
            return None

        def calculate_indicators(self, candles):
            return {}

        def on_bar(self, index):
            return None

        def on_trade(self, trade):
            self.trades.append(trade)

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

    signal = Signal(type=SignalType.BUY, price=100.0, timestamp=123456)
    await engine._execute_signal(signal)

    # 首次下单仅受理，成交未确认，不应立即更新持仓
    assert strategy.position.quantity == pytest.approx(0.0)
    assert len(engine._pending_orders) == 1

    # 第一次补偿：累计成交 0.4
    await engine._reconcile_pending_orders()
    assert strategy.position.quantity == pytest.approx(0.4)
    assert strategy.position.avg_price == pytest.approx(101.0)
    assert len(strategy.trades) == 1
    assert strategy.trades[0].quantity == pytest.approx(0.4)

    # 第二次补偿：累计成交 1.0，增量应为 0.6
    await engine._reconcile_pending_orders()
    assert strategy.position.quantity == pytest.approx(1.0)
    assert strategy.position.avg_price == pytest.approx(101.6)
    assert len(strategy.trades) == 2
    assert strategy.trades[1].quantity == pytest.approx(0.6)
    assert len(engine._pending_orders) == 0

    # 再执行一次补偿，不应重复记账
    await engine._reconcile_pending_orders()
    assert strategy.position.quantity == pytest.approx(1.0)
    assert len(strategy.trades) == 2


@pytest.mark.asyncio
async def test_live_engine_partial_fill_first_query_keeps_reconcile_queue():
    """首轮已部分成交时也应入补偿队列，后续增量成交继续同步。"""
    import app.live.engine as engine_mod
    from app.core.data_fetcher import Candle
    from app.strategies.base import Position, Signal, SignalType

    engine_mod.LiveTradingEngine._instance = None

    class DummyTrader:
        is_available = True
        mode = "simulated"

        def __init__(self):
            self._query_count = 0

        def place_order(self, **kwargs):
            return type("Result", (), {
                "success": True,
                "order_id": "ord-partial-1",
                "client_order_id": kwargs.get("client_order_id", ""),
                "error_code": "",
                "error_message": "",
            })()

        def get_order(self, inst_id: str, order_id: str = "", client_order_id: str = ""):
            self._query_count += 1
            if self._query_count == 1:
                # 首次查询已有部分成交，但订单仍未终态
                return {"ordId": "ord-partial-1", "fillSz": "0.4", "avgPx": "101", "state": "partially_filled"}
            return {"ordId": "ord-partial-1", "fillSz": "1", "avgPx": "101.6", "state": "filled"}

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
                    timestamp=1,
                    open=100.0,
                    high=100.0,
                    low=100.0,
                    close=100.0,
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
            return {}

        def update_live_order_execution(self, **kwargs):
            self.execution_updates.append(kwargs)
            return True

    class DummyConfig:
        symbol = "BTC-USDT"
        timeframe = "1H"
        inst_type = "SPOT"
        position_size = 1.0

    class DummyStrategy:
        strategy_id = "dummy_partial"
        name = "DummyPartial"
        config = DummyConfig()
        position = Position(symbol="BTC-USDT")

        def __init__(self):
            self.trades = []

        def on_init(self, candles):
            return None

        def calculate_indicators(self, candles):
            return {}

        def on_bar(self, index):
            return None

        def on_trade(self, trade):
            self.trades.append(trade)

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

    signal = Signal(type=SignalType.BUY, price=100.0, timestamp=223344)
    await engine._execute_signal(signal)

    # 首轮部分成交应先同步已成交量，并继续进入补偿队列
    assert strategy.position.quantity == pytest.approx(0.4)
    assert len(strategy.trades) == 1
    assert len(engine._pending_orders) == 1
    assert "部分成交" in engine.order_history[-1].error_message

    # 后续补偿应只同步增量 0.6，最终到 1.0 且出队
    await engine._reconcile_pending_orders()
    assert strategy.position.quantity == pytest.approx(1.0)
    assert strategy.position.avg_price == pytest.approx(101.6)
    assert len(strategy.trades) == 2
    assert strategy.trades[1].quantity == pytest.approx(0.6)
    assert len(engine._pending_orders) == 0

    # 补偿同步应回写订单执行结果
    assert storage.execution_updates
    assert storage.execution_updates[-1]["order_id"] == "ord-partial-1"


@pytest.mark.asyncio
async def test_live_engine_restores_pending_orders_from_storage_on_start(monkeypatch):
    """引擎启动时应恢复历史未终态订单，避免重启后丢失补偿同步。"""
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
            return None

    class DummyAccount:
        is_available = True

        def get_max_avail_size(self, *args, **kwargs):
            return {"maxBuy": "0", "maxSell": "0"}

        def get_balance(self, ccy: str = ""):
            return {"details": [{"ccy": "BTC", "availBal": "0", "frozenBal": "0"}]}

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
        def save_live_order(self, **kwargs):
            return True

        def get_cost_basis(self, mode: str, ccy: str = ""):
            return {}

        def get_unreconciled_live_orders(self, mode: str, inst_id: str = "", strategy_id: str = "", limit: int = 200):
            return [
                {
                    "id": 11,
                    "order_id": "",
                    "client_order_id": "clid-restore-1",
                    "inst_id": "BTC-USDT",
                    "side": "buy",
                    "size": "0.4",
                    "price": "101",
                    "signal_type": "buy",
                    "success": True,
                    "error_message": "订单部分成交，补偿同步中",
                    "mode": mode,
                    "strategy_id": "dummy_restore",
                    "strategy_name": "DummyRestore",
                    "timestamp": "2026-02-09T00:00:00",
                }
            ]

        def update_live_order_execution(self, **kwargs):
            return True

    class DummyConfig:
        symbol = "BTC-USDT"
        timeframe = "1H"
        inst_type = "SPOT"
        position_size = 0.1

    class DummyStrategy:
        strategy_id = "dummy_restore"
        name = "DummyRestore"
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

    assert len(engine._pending_orders) == 1
    pending = next(iter(engine._pending_orders.values()))
    assert pending.client_order_id == "clid-restore-1"
    assert pending.synced_fill_size == pytest.approx(0.4)
    assert pending.requested_size is None

    await engine.stop()


@pytest.mark.asyncio
async def test_live_engine_restored_pending_order_not_removed_before_terminal_state():
    """恢复订单 requested_size 未知时，不应因“已成交量>=基线”而提前出队。"""
    import app.live.engine as engine_mod
    from app.strategies.base import Signal, SignalType

    engine_mod.LiveTradingEngine._instance = None

    class DummyStorage:
        def __init__(self):
            self.execution_updates = []

        def save_live_order(self, **kwargs):
            return True

        def get_cost_basis(self, mode: str, ccy: str = ""):
            return {}

        def update_live_order_execution(self, **kwargs):
            self.execution_updates.append(kwargs)
            return True

    class Dummy:
        is_available = True
        mode = "simulated"

    engine = engine_mod.get_live_engine()
    engine.configure(
        strategy=type("S", (), {
            "strategy_id": "restore_hold",
            "name": "RestoreHold",
            "config": type("C", (), {"symbol": "BTC-USDT", "timeframe": "1H", "inst_type": "SPOT", "position_size": 0.1})(),
            "position": __import__("app.strategies.base", fromlist=["Position"]).Position(symbol="BTC-USDT"),
            "on_init": lambda self, candles: None,
            "calculate_indicators": lambda self, candles: {},
            "on_bar": lambda self, index: None,
            "on_trade": lambda self, trade: None,
        })(),
        check_interval=1,
        trader=Dummy(),
        account=Dummy(),
        candle_manager=Dummy(),
        storage=DummyStorage(),
    )

    pending = engine_mod.PendingOrder(
        signal=Signal(type=SignalType.BUY, price=101.0, timestamp=1),
        order_id="",
        client_order_id="clid-hold-1",
        side="buy",
        requested_size=None,
        synced_fill_size=0.4,
        synced_notional=40.4,
    )
    engine._pending_orders = {"cl:clid-hold-1": pending}

    async def fake_fetch_detail(*args, **kwargs):
        return {"ordId": "", "fillSz": "0.4", "avgPx": "101", "state": "partially_filled"}

    engine._fetch_order_detail = fake_fetch_detail  # type: ignore[method-assign]
    await engine._reconcile_pending_orders()

    # 非终态 + requested_size 未知，不应被提前移除
    assert "cl:clid-hold-1" in engine._pending_orders


@pytest.mark.asyncio
async def test_live_engine_update_pending_order_record_supports_client_order_id_only():
    """仅有 client_order_id 时也应回写补偿结果。"""
    import app.live.engine as engine_mod
    from app.strategies.base import Signal, SignalType

    engine_mod.LiveTradingEngine._instance = None

    class DummyStorage:
        def __init__(self):
            self.execution_updates = []

        def save_live_order(self, **kwargs):
            return True

        def get_cost_basis(self, mode: str, ccy: str = ""):
            return {}

        def update_live_order_execution(self, **kwargs):
            self.execution_updates.append(kwargs)
            return True

    storage = DummyStorage()
    engine = engine_mod.get_live_engine()
    engine.configure(
        strategy=type("S", (), {
            "strategy_id": "update_client_only",
            "name": "UpdateClientOnly",
            "config": type("C", (), {"symbol": "BTC-USDT", "timeframe": "1H", "inst_type": "SPOT", "position_size": 0.1})(),
            "position": __import__("app.strategies.base", fromlist=["Position"]).Position(symbol="BTC-USDT"),
            "on_init": lambda self, candles: None,
            "calculate_indicators": lambda self, candles: {},
            "on_bar": lambda self, index: None,
            "on_trade": lambda self, trade: None,
        })(),
        check_interval=1,
        trader=type("T", (), {"is_available": True, "mode": "simulated"})(),
        account=type("A", (), {"is_available": True})(),
        candle_manager=type("M", (), {})(),
        storage=storage,
    )

    pending = engine_mod.PendingOrder(
        signal=Signal(type=SignalType.BUY, price=101.0, timestamp=1),
        order_id="",
        client_order_id="clid-only-1",
        side="buy",
        requested_size=None,
        synced_fill_size=0.5,
        synced_notional=50.5,
    )

    await engine._update_pending_order_record(
        pending,
        {"fillSz": "0.5", "avgPx": "101", "state": "partially_filled"},
    )

    assert storage.execution_updates
    assert storage.execution_updates[-1]["client_order_id"] == "clid-only-1"
