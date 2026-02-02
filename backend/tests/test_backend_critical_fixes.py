import asyncio

import pytest


@pytest.fixture(autouse=True)
def _avoid_asyncio_default_executor_hang(monkeypatch):
    """
    在当前运行环境中，asyncio.to_thread() 会创建默认线程池；
    pytest/asyncio 在关闭事件循环时可能卡在 shutdown_default_executor。

    单元测试里我们把 to_thread 改为“同步执行并立即返回”，避免测试进程挂死。
    """

    async def _to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", _to_thread, raising=True)


def test_okx_trader_uses_mode_specific_credentials(monkeypatch):
    """
    确保 OKXTrader 会按实例模式(simulated/live)选择对应密钥，
    避免“请求 mode 和实际用的密钥”不一致导致的资金风险。
    """
    import app.core.trader as trader_mod

    # 配置两套不同的密钥（模拟盘/实盘）
    trader_mod.config.okx.demo.api_key = "demo_key"
    trader_mod.config.okx.demo.secret_key = "demo_secret"
    trader_mod.config.okx.demo.passphrase = "demo_pass"

    trader_mod.config.okx.live.api_key = "live_key"
    trader_mod.config.okx.live.secret_key = "live_secret"
    trader_mod.config.okx.live.passphrase = "live_pass"

    created = []

    def fake_trade_api(*, api_key, api_secret_key, passphrase, flag, debug=False):
        created.append(
            {
                "api_key": api_key,
                "api_secret_key": api_secret_key,
                "passphrase": passphrase,
                "flag": flag,
                "debug": debug,
            }
        )
        return object()

    monkeypatch.setattr(trader_mod.Trade, "TradeAPI", fake_trade_api)

    trader_mod.OKXTrader(is_simulated=True)
    assert created[-1]["api_key"] == "demo_key"
    assert created[-1]["flag"] == "1"

    trader_mod.OKXTrader(is_simulated=False)
    assert created[-1]["api_key"] == "live_key"
    assert created[-1]["flag"] == "0"


def test_okx_account_uses_mode_specific_credentials(monkeypatch):
    """同上：OKXAccount 也必须按实例模式选密钥。"""
    import app.core.trader as trader_mod

    trader_mod.config.okx.demo.api_key = "demo_key"
    trader_mod.config.okx.demo.secret_key = "demo_secret"
    trader_mod.config.okx.demo.passphrase = "demo_pass"

    trader_mod.config.okx.live.api_key = "live_key"
    trader_mod.config.okx.live.secret_key = "live_secret"
    trader_mod.config.okx.live.passphrase = "live_pass"

    created = []

    def fake_account_api(*, api_key, api_secret_key, passphrase, flag, debug=False):
        created.append(
            {
                "api_key": api_key,
                "api_secret_key": api_secret_key,
                "passphrase": passphrase,
                "flag": flag,
                "debug": debug,
            }
        )
        return object()

    monkeypatch.setattr(trader_mod.Account, "AccountAPI", fake_account_api)

    trader_mod.OKXAccount(is_simulated=True)
    assert created[-1]["api_key"] == "demo_key"
    assert created[-1]["flag"] == "1"

    trader_mod.OKXAccount(is_simulated=False)
    assert created[-1]["api_key"] == "live_key"
    assert created[-1]["flag"] == "0"


def test_okx_trader_reinit_clears_old_api_when_creds_missing(monkeypatch):
    """
    配置变更为无效（例如密钥被清空）时，reinit 必须清空旧 TradeAPI，
    否则会出现“用户以为已失效/已切换，但实际仍用旧密钥继续下单”的高风险情况。
    """
    import app.core.trader as trader_mod

    trader_mod.config.okx.demo.api_key = "demo_key"
    trader_mod.config.okx.demo.secret_key = "demo_secret"
    trader_mod.config.okx.demo.passphrase = "demo_pass"

    monkeypatch.setattr(trader_mod.Trade, "TradeAPI", lambda **kwargs: object())

    trader = trader_mod.OKXTrader(is_simulated=True)
    assert trader.is_available is True

    # 置空凭证后重新初始化：必须变为不可用
    trader_mod.config.okx.demo.passphrase = ""
    trader.reinit()
    assert trader.is_available is False


def test_okx_trader_spot_market_order_uses_base_ccy_size(monkeypatch):
    """
    关键：OKX 现货 market BUY 默认把 sz 解释为 quote_ccy（例如 USDT）。
    本项目（前端/策略）把 size 视为 base_ccy（例如 BTC），因此必须显式传 tgtCcy=base_ccy。
    """
    import app.core.trader as trader_mod

    trader_mod.config.okx.demo.api_key = "demo_key"
    trader_mod.config.okx.demo.secret_key = "demo_secret"
    trader_mod.config.okx.demo.passphrase = "demo_pass"

    called = {"kwargs": None}

    class DummyTradeAPI:
        def place_order(self, **kwargs):
            called["kwargs"] = kwargs
            return {"code": "0", "data": [{"ordId": "1", "clOrdId": ""}]}

    monkeypatch.setattr(trader_mod.Trade, "TradeAPI", lambda **_kwargs: DummyTradeAPI())

    trader = trader_mod.OKXTrader(is_simulated=True)

    result = trader.place_order(
        inst_id="BTC-USDT",
        side="buy",
        order_type="market",
        size="0.1",
        price="",
        td_mode="cash",
        client_order_id="",
    )

    assert result.success is True
    assert called["kwargs"] is not None
    assert called["kwargs"]["tgtCcy"] == "base_ccy"
    assert called["kwargs"]["sz"] == "0.1"
    assert called["kwargs"]["px"] == ""


def test_okx_trader_market_order_rejects_when_sdk_does_not_support_tgt_ccy(monkeypatch):
    """
    若 SDK 不支持 tgtCcy，宁可拒单也不要用默认行为继续下单（会导致 size 单位错配）。
    """
    import app.core.trader as trader_mod

    trader_mod.config.okx.demo.api_key = "demo_key"
    trader_mod.config.okx.demo.secret_key = "demo_secret"
    trader_mod.config.okx.demo.passphrase = "demo_pass"

    class DummyTradeAPI:
        # 故意不接受 tgtCcy 参数，触发 TypeError
        def place_order(self, instId, tdMode, side, ordType, sz, px, clOrdId):
            return {"code": "0", "data": [{"ordId": "1", "clOrdId": ""}]}

    monkeypatch.setattr(trader_mod.Trade, "TradeAPI", lambda **_kwargs: DummyTradeAPI())

    trader = trader_mod.OKXTrader(is_simulated=True)

    result = trader.place_order(
        inst_id="BTC-USDT",
        side="buy",
        order_type="market",
        size="0.1",
        price="",
        td_mode="cash",
        client_order_id="",
    )

    assert result.success is False
    assert result.error_code == "UNSUPPORTED_SDK"


def test_okx_account_reinit_clears_old_api_when_creds_missing(monkeypatch):
    """同上：AccountAPI 也必须在凭证无效时清空旧实例。"""
    import app.core.trader as trader_mod

    trader_mod.config.okx.demo.api_key = "demo_key"
    trader_mod.config.okx.demo.secret_key = "demo_secret"
    trader_mod.config.okx.demo.passphrase = "demo_pass"

    monkeypatch.setattr(trader_mod.Account, "AccountAPI", lambda **kwargs: object())

    account = trader_mod.OKXAccount(is_simulated=True)
    assert account.is_available is True

    trader_mod.config.okx.demo.api_key = ""
    account.reinit()
    assert account.is_available is False


def test_okx_trader_get_all_fills_history_breaks_when_bill_id_missing(monkeypatch):
    """
    防御性：OKXTrader.get_all_fills_history 分页依赖 billId。

    若 SDK/接口未返回 billId，旧逻辑会在 len(fills)==100 时重复拉取同一页，最多循环 100 次，
    造成大量重复请求（触发限流/卡死风险）。
    """
    import app.core.trader as trader_mod

    trader_mod.config.okx.demo.api_key = "demo_key"
    trader_mod.config.okx.demo.secret_key = "demo_secret"
    trader_mod.config.okx.demo.passphrase = "demo_pass"

    monkeypatch.setattr(trader_mod.Trade, "TradeAPI", lambda **kwargs: object())

    trader = trader_mod.OKXTrader(is_simulated=True)

    calls = {"n": 0}

    def fake_get_fills_history(*, inst_type="SPOT", inst_id="", limit="100", after="", before=""):
        calls["n"] += 1
        # 模拟返回 100 条，但最后一条缺少 billId（无法推进分页）
        return [{"tradeId": str(i), "billId": ""} for i in range(100)]

    trader.get_fills_history = fake_get_fills_history  # type: ignore[method-assign]

    fills = trader.get_all_fills_history(inst_type="SPOT")
    assert calls["n"] == 1
    assert len(fills) == 100


def test_data_storage_save_fills_batch_counts_only_new_records(tmp_path):
    """
    save_fills_batch 应只统计“新增”记录，重复 sync 时返回 0，避免前端误以为新增了大量成交。
    """
    from app.core.data_storage import DataStorage

    storage = DataStorage(tmp_path / "test.db")

    fills = [
        {
            "tradeId": "t1",
            "instId": "BTC-USDT",
            "side": "buy",
            "fillPx": "100",
            "fillSz": "0.1",
            "fee": "-0.0001",
            "feeCcy": "BTC",
            "ts": 1,
        },
        # 同一 tradeId 的重复记录
        {
            "tradeId": "t1",
            "instId": "BTC-USDT",
            "side": "buy",
            "fillPx": "100",
            "fillSz": "0.1",
            "fee": "-0.0001",
            "feeCcy": "BTC",
            "ts": 1,
        },
    ]

    new_1 = storage.save_fills_batch(fills, mode="simulated")
    assert new_1 == 1

    new_2 = storage.save_fills_batch(fills, mode="simulated")
    assert new_2 == 0


def test_data_fetcher_get_history_candles_stops_when_pagination_not_advancing(monkeypatch):
    """
    防御性：get_history_candles 若 after 不推进（接口忽略 after/重复返回同一页），
    不应重复请求直到 max_candles 才停止，否则会显著拖慢同步并触发限流。
    """
    import app.core.data_fetcher as fetcher_mod
    from app.core.data_fetcher import DataFetcher, Candle

    # 避免测试中真实 sleep
    monkeypatch.setattr(fetcher_mod.time, "sleep", lambda *_args, **_kwargs: None, raising=True)

    class StubFetcher:
        def __init__(self):
            self.calls = []

        def get_candles(self, inst_id, timeframe="1H", limit=300, after=None, before=None):
            self.calls.append(after)
            # 模拟“接口忽略 after，总是返回同一页（300条）”
            return [
                Candle(timestamp=i, open=1.0, high=1.0, low=1.0, close=1.0, volume=0.0, volume_ccy=0.0)
                for i in range(1, 301)
            ]

    stub = StubFetcher()
    candles = DataFetcher.get_history_candles(
        stub,  # type: ignore[arg-type]
        inst_id="BTC-USDT",
        timeframe="1H",
        start_time=None,
        end_time=None,
        max_candles=10000,
    )

    # 第一次拿到 300 条，第二次检测到 after 未推进后停止，不应无限追加
    assert len(candles) == 300
    assert stub.calls == [None, 1]


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

    monkeypatch.setattr(trading_mod, "get_trader", lambda mode: DummyTrader())

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

    monkeypatch.setattr(trading_mod, "get_trader", lambda mode: DummyTrader())

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

    monkeypatch.setattr(trading_mod, "get_trader", lambda mode: DummyTrader())

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
