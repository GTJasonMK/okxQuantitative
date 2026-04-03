import asyncio

import pytest


@pytest.mark.asyncio
async def test_backtest_run_passes_inst_type(monkeypatch):
    """
    验证通用回测接口会把 inst_type 传入策略 create_instance，避免 SWAP 数据用 SPOT 配置回测。
    """
    import app.api.backtest as backtest_mod
    from app.core.data_fetcher import Candle

    # stub: manager.get_candles_with_sync
    class DummyManager:
        def get_candles_with_sync(self, *args, **kwargs):
            # 通用回测接口要求至少 10 根 K 线，否则会直接返回 400
            candles = []
            for i in range(10):
                candles.append(
                    Candle(
                        timestamp=1 + i,
                        open=1.0,
                        high=1.0,
                        low=1.0,
                        close=1.0,
                        volume=0.0,
                        volume_ccy=0.0,
                    )
                )
            return candles

    received = {"inst_type": None}

    class DummyStrategyCls:
        @staticmethod
        def validate_params(params):
            return None

        @staticmethod
        def create_instance(*, inst_type="SPOT", **kwargs):
            received["inst_type"] = inst_type
            # 返回一个最简策略对象，BacktestEngine.run 会被 stub 掉
            return object()

    class DummyResult:
        def to_dict(self):
            return {"ok": True}

    class DummyBacktestEngine:
        def run(self, strategy, candles):
            return DummyResult()

    class DummyStorage:
        def save_backtest_result(self, *args, **kwargs):
            return None

    class DummyContext:
        def __init__(self, *, manager, storage):
            self._manager = manager
            self._storage = storage

        def manager(self):
            return self._manager

        def storage(self):
            return self._storage

    monkeypatch.setattr(backtest_mod, "discover_strategies", lambda: None)
    monkeypatch.setattr(backtest_mod, "get_strategy", lambda strategy_id: DummyStrategyCls)
    monkeypatch.setattr(backtest_mod, "BacktestEngine", DummyBacktestEngine)

    req = backtest_mod.UnifiedBacktestRequest(
        symbol="BTC-USDT",
        inst_type="SWAP",
        timeframe="1H",
        days=1,
        initial_capital=10000,
        position_size=0.5,
        stop_loss=0.05,
        take_profit=0.1,
        params={},
    )

    resp = await backtest_mod.backtest_strategy(
        "dummy",
        req,
        ctx=DummyContext(manager=DummyManager(), storage=DummyStorage()),
    )
    assert resp.code == 0
    assert received["inst_type"] == "SWAP"


def test_strategy_stop_loss_take_profit_does_not_divide_by_zero():
    """
    BaseStrategy 的止损/止盈检查会除以 avg_price。
    若 position.quantity>0 但 avg_price=0（状态异常或外部策略写坏），旧逻辑会触发 ZeroDivisionError。

    这里验证：即使 avg_price=0，也不应导致策略/引擎崩溃。
    """
    from app.core.data_fetcher import Candle
    from app.strategies.base import BaseStrategy, StrategyConfig, Signal, SignalType

    class DummyStrategy(BaseStrategy):
        strategy_id = "dummy_stoploss"
        strategy_name = "DummyStopLoss"

        def calculate_indicators(self, candles):
            return {}

        def generate_signal(self, index: int) -> Signal:
            c = self._candles[index]
            return Signal(type=SignalType.HOLD, price=c.close, timestamp=c.timestamp)

    candles = [
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

    s = DummyStrategy(
        StrategyConfig(
            symbol="BTC-USDT",
            timeframe="1H",
            stop_loss=0.05,
            take_profit=0.10,
        )
    )
    s.on_init(candles)

    # 人为制造异常状态：有仓位但 avg_price=0
    s.position.quantity = 1.0
    s.position.avg_price = 0.0

    sig = s.on_bar(0)
    assert sig is not None
    assert sig.type == SignalType.HOLD


@pytest.mark.asyncio
async def test_update_cost_basis_uses_current_balance_for_total_cost(monkeypatch):
    """
    手动录入成本价时，如果能拿到账户余额，应推导当前持仓数量并计算 total_cost；
    否则 total_cost=0 会导致前端盈亏/成本统计严重失真。
    """
    import app.api.trading as trading_mod

    class DummyAccount:
        is_available = True

        def get_balance(self):
            return {
                "details": [
                    {"ccy": "BTC", "availBal": "1.5", "frozenBal": "0.5"},
                ]
            }

    captured: dict = {}

    class DummyStorage:
        def save_cost_basis(self, **kwargs):
            captured.update(kwargs)
            return True

    monkeypatch.setattr(trading_mod, "get_account", lambda mode: DummyAccount())
    monkeypatch.setattr(trading_mod, "get_cached_storage", lambda: DummyStorage())

    req = trading_mod.UpdateCostBasisRequest(ccy="btc", avg_cost=100.0, mode="simulated")
    resp = await trading_mod.update_cost_basis(req)

    assert resp["success"] is True
    assert captured["ccy"] == "BTC"
    assert captured["mode"] == "simulated"
    assert captured["avg_cost"] == 100.0
    assert captured["total_qty"] == 2.0
    assert captured["total_cost"] == 200.0


@pytest.mark.asyncio
async def test_place_order_rejects_non_positive_size(monkeypatch):
    """手动下单接口必须拒绝 size<=0，避免误下单/交易所报错。"""
    from fastapi import HTTPException
    import app.api.trading as trading_mod

    class DummyTrader:
        is_available = True

        def place_order(self, *args, **kwargs):  # pragma: no cover
            raise AssertionError("size 非法时不应触发下单")

    class DummyAccount:
        is_available = True

    monkeypatch.setattr(trading_mod, "get_trader", lambda mode: DummyTrader())
    monkeypatch.setattr(trading_mod, "get_account", lambda mode: DummyAccount())

    # 该用例关注“参数校验”，为避免受当前默认模式影响，强制设为 simulated
    old = trading_mod.config.okx.use_simulated
    trading_mod.config.okx.use_simulated = True
    try:
        req = trading_mod.PlaceOrderRequest(
            inst_id="BTC-USDT",
            side="buy",
            order_type="market",
            size="0",
            price="",
            td_mode="cash",
            mode="simulated",
        )

        with pytest.raises(HTTPException) as exc:
            await trading_mod.place_order(req)
        assert exc.value.status_code == 400
    finally:
        trading_mod.config.okx.use_simulated = old


@pytest.mark.asyncio
async def test_place_order_limit_rejects_non_positive_price(monkeypatch):
    """限价单必须验证 price 为正数。"""
    from fastapi import HTTPException
    import app.api.trading as trading_mod

    class DummyTrader:
        is_available = True

        def place_order(self, *args, **kwargs):  # pragma: no cover
            raise AssertionError("price 非法时不应触发下单")

    class DummyAccount:
        is_available = True

    monkeypatch.setattr(trading_mod, "get_trader", lambda mode: DummyTrader())
    monkeypatch.setattr(trading_mod, "get_account", lambda mode: DummyAccount())

    # 该用例关注“参数校验”，为避免受当前默认模式影响，强制设为 simulated
    old = trading_mod.config.okx.use_simulated
    trading_mod.config.okx.use_simulated = True
    try:
        req = trading_mod.PlaceOrderRequest(
            inst_id="BTC-USDT",
            side="buy",
            order_type="limit",
            size="1",
            price="-1",
            td_mode="cash",
            mode="simulated",
        )

        with pytest.raises(HTTPException) as exc:
            await trading_mod.place_order(req)
        assert exc.value.status_code == 400
    finally:
        trading_mod.config.okx.use_simulated = old


@pytest.mark.asyncio
async def test_place_contract_order_requires_integer_size(monkeypatch):
    """合约下单 size 视为张数，保守要求为正整数。"""
    from fastapi import HTTPException
    import app.api.trading as trading_mod

    class DummyTrader:
        is_available = True

        def place_contract_order(self, *args, **kwargs):  # pragma: no cover
            raise AssertionError("size 非法时不应触发下单")

    class DummyAccount:
        is_available = True

    monkeypatch.setattr(trading_mod, "get_trader", lambda mode: DummyTrader())
    monkeypatch.setattr(trading_mod, "get_account", lambda mode: DummyAccount())

    # 该用例关注“参数校验”，为避免受当前默认模式影响，强制设为 simulated
    old = trading_mod.config.okx.use_simulated
    trading_mod.config.okx.use_simulated = True
    try:
        req = trading_mod.ContractOrderRequest(
            inst_id="BTC-USDT-SWAP",
            side="buy",
            pos_side="long",
            order_type="market",
            size="0.5",
            price="",
            td_mode="cross",
            reduce_only=False,
            mode="simulated",
        )

        with pytest.raises(HTTPException) as exc:
            await trading_mod.place_contract_order(req)
        assert exc.value.status_code == 400
    finally:
        trading_mod.config.okx.use_simulated = old


@pytest.mark.asyncio
async def test_backtest_dual_ma_passes_inst_type_to_strategy_factory(monkeypatch):
    """旧式 dual_ma 回测接口应把 inst_type 传给策略工厂，避免配置/展示错配。"""
    import app.api.backtest as backtest_mod
    from app.core.data_fetcher import Candle

    class DummyManager:
        def get_candles_with_sync(self, *args, **kwargs):
            candles = []
            for i in range(50):
                candles.append(
                    Candle(
                        timestamp=1 + i,
                        open=50.0,
                        high=60.0,
                        low=40.0,
                        close=50.0,
                        volume=0.0,
                        volume_ccy=0.0,
                    )
                )
            return candles

    received = {"inst_type": None}

    def fake_create_dual_ma_strategy(*, inst_type="SPOT", **kwargs):
        received["inst_type"] = inst_type
        return object()

    class DummyResult:
        def to_dict(self):
            return {"ok": True}

    class DummyBacktestEngine:
        def run(self, strategy, candles):
            return DummyResult()

    class DummyStorage:
        def save_backtest_result(self, *args, **kwargs):
            return None

    class DummyContext:
        def __init__(self, *, manager, storage):
            self._manager = manager
            self._storage = storage

        def manager(self):
            return self._manager

        def storage(self):
            return self._storage

    monkeypatch.setattr(backtest_mod, "create_dual_ma_strategy", fake_create_dual_ma_strategy)
    monkeypatch.setattr(backtest_mod, "BacktestEngine", DummyBacktestEngine)

    req = backtest_mod.DualMABacktestRequest(
        symbol="BTC-USDT",
        inst_type="SWAP",
        timeframe="1H",
        days=1,
        initial_capital=10000,
        short_period=5,
        long_period=20,
        stop_loss=0.05,
        take_profit=0.10,
        position_size=0.5,
        use_ema=False,
    )

    resp = await backtest_mod.backtest_dual_ma(
        req,
        ctx=DummyContext(manager=DummyManager(), storage=DummyStorage()),
    )
    assert resp.code == 0
    assert received["inst_type"] == "SWAP"


@pytest.mark.asyncio
async def test_backtest_grid_passes_inst_type_to_strategy_factory(monkeypatch):
    """旧式 grid 回测接口也应透传 inst_type。"""
    import app.api.backtest as backtest_mod
    from app.core.data_fetcher import Candle

    class DummyManager:
        def get_candles_with_sync(self, *args, **kwargs):
            candles = []
            for i in range(50):
                candles.append(
                    Candle(
                        timestamp=1 + i,
                        open=50.0,
                        high=60.0,
                        low=40.0,
                        close=50.0,
                        volume=0.0,
                        volume_ccy=0.0,
                    )
                )
            return candles

    received = {"inst_type": None}

    def fake_create_grid_strategy(*, inst_type="SPOT", **kwargs):
        received["inst_type"] = inst_type
        return object()

    class DummyResult:
        def to_dict(self):
            return {"ok": True}

    class DummyBacktestEngine:
        def run(self, strategy, candles):
            return DummyResult()

    class DummyStorage:
        def save_backtest_result(self, *args, **kwargs):
            return None

    class DummyContext:
        def __init__(self, *, manager, storage):
            self._manager = manager
            self._storage = storage

        def manager(self):
            return self._manager

        def storage(self):
            return self._storage

    monkeypatch.setattr(backtest_mod, "create_grid_strategy", fake_create_grid_strategy)
    monkeypatch.setattr(backtest_mod, "BacktestEngine", DummyBacktestEngine)

    req = backtest_mod.GridBacktestRequest(
        symbol="BTC-USDT",
        inst_type="FUTURES",
        timeframe="1H",
        days=1,
        initial_capital=10000,
        upper_price=55.0,
        lower_price=45.0,
        grid_count=10,
        position_size=0.8,
        grid_type="arithmetic",
    )

    resp = await backtest_mod.backtest_grid(
        req,
        ctx=DummyContext(manager=DummyManager(), storage=DummyStorage()),
    )
    assert resp.code == 0
    assert received["inst_type"] == "FUTURES"


@pytest.mark.asyncio
async def test_market_get_candles_accepts_iso8601_z(monkeypatch):
    """market/candles 的 start_time/end_time 应兼容带 Z 的 ISO8601 输入。"""
    import app.api.market as market_mod

    called = {"ok": False}

    class DummyStorage:
        def get_candles(self, *args, **kwargs):
            called["ok"] = True
            return []

    class DummyManager:
        storage = DummyStorage()
        fetcher = None

    resp = await market_mod.get_candles(
        inst_id="BTC-USDT",
        timeframe=market_mod.TimeframeEnum.H1,
        limit=1,
        start_time="2024-01-01T00:00:00Z",
        end_time=None,
        source="local",
        inst_type=market_mod.InstTypeEnum.SPOT,
        manager=DummyManager(),
    )

    assert called["ok"] is True
    assert resp.total == 0


@pytest.mark.asyncio
async def test_live_engine_uses_client_order_id_for_idempotency(monkeypatch):
    """实时引擎下单时应携带稳定的 client_order_id，用于幂等兜底查询。"""
    import app.live.engine as engine_mod
    from app.core.data_fetcher import Candle
    from app.strategies.base import Signal, SignalType, Position

    engine_mod.LiveTradingEngine._instance = None

    class DummyTrader:
        is_available = True
        mode = "simulated"

        def __init__(self):
            self.last_client_order_id = ""

        def place_order(self, **kwargs):
            self.last_client_order_id = kwargs.get("client_order_id", "")
            return type("Result", (), {
                "success": True,
                "order_id": "ord-1",
                "client_order_id": self.last_client_order_id,
                "error_code": "",
                "error_message": "",
            })()

        def get_order(self, inst_id: str, order_id: str = "", client_order_id: str = ""):
            if client_order_id != self.last_client_order_id:
                return None
            return {"ordId": order_id or "ord-1", "fillSz": "1", "avgPx": "100"}

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
        strategy_id = "dummy"
        name = "Dummy"
        config = DummyConfig()
        position = Position(symbol="BTC-USDT")

        def on_init(self, candles):
            return None

        def calculate_indicators(self, candles):
            return {}

        def on_bar(self, index):
            return Signal(type=SignalType.BUY, price=100.0, timestamp=123456)

        def on_trade(self, trade):
            return None

    trader = DummyTrader()
    engine = engine_mod.get_live_engine()
    engine.configure(
        strategy=DummyStrategy(),
        check_interval=1,
        trader=trader,
        account=DummyAccount(),
        candle_manager=DummyManager(),
        storage=DummyStorage(),
    )

    signal = Signal(type=SignalType.BUY, price=100.0, timestamp=123456)
    await engine._execute_signal(signal)

    assert trader.last_client_order_id.startswith("lv")
    assert len(trader.last_client_order_id) > 10


@pytest.mark.asyncio
async def test_live_engine_hydrates_position_from_account_on_init(monkeypatch):
    """实时引擎启动时应回填账户持仓，避免重启后策略仓位失真。"""
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
            return {
                "details": [
                    {"ccy": "BTC", "availBal": "0.3", "frozenBal": "0.2"},
                    {"ccy": "USDT", "availBal": "100", "frozenBal": "0"},
                ]
            }

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
            return {"BTC": {"avg_cost": 150.0, "total_qty": 0.5, "total_cost": 75.0}}

    class DummyConfig:
        symbol = "BTC-USDT"
        timeframe = "1H"
        inst_type = "SPOT"
        position_size = 0.1

    class DummyStrategy:
        strategy_id = "dummy_hydrate"
        name = "DummyHydrate"
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

    assert strategy.position.quantity == pytest.approx(0.5)
    assert strategy.position.avg_price == pytest.approx(150.0)
    await engine.stop()
