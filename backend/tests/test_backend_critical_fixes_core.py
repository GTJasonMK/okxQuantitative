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


def test_okx_account_get_balance_retries_transient_ssl_eof(monkeypatch):
    """账户余额查询遇到瞬时 TLS EOF 时，应短重试而不是直接失败。"""
    import app.core.trader as trader_mod

    trader_mod.config.okx.demo.api_key = "demo_key"
    trader_mod.config.okx.demo.secret_key = "demo_secret"
    trader_mod.config.okx.demo.passphrase = "demo_pass"

    created = []

    state = {"failed_once": False}

    class FlakyAccountAPI:
        def __init__(self):
            self.calls = 0

        def get_account_balance(self, ccy: str = ""):
            self.calls += 1
            if not state["failed_once"]:
                state["failed_once"] = True
                raise Exception("[SSL: UNEXPECTED_EOF_WHILE_READING] EOF occurred in violation of protocol (_ssl.c:1032)")
            return {"code": "0", "msg": "", "data": [{"totalEq": "123.45", "details": []}]}

    def fake_account_api(*, api_key, api_secret_key, passphrase, flag, debug=False):
        api = FlakyAccountAPI()
        created.append(api)
        return api

    monkeypatch.setattr(trader_mod.Account, "AccountAPI", fake_account_api)
    monkeypatch.setattr(trader_mod.time, "sleep", lambda *_args, **_kwargs: None, raising=True)

    account = trader_mod.OKXAccount(is_simulated=True)
    balance = account.get_balance()

    assert balance["totalEq"] == "123.45"
    assert len(created) == 2
    assert created[0].calls == 1
    assert created[1].calls == 1


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


def test_data_storage_live_order_mode_migration_works_on_legacy_db(tmp_path):
    """
    兼容旧库：live_order_records 缺少 mode 列时，初始化应先补列再建索引。
    否则启动阶段会因 "no such column: mode" 直接失败。
    """
    import sqlite3

    from app.core.data_storage import DataStorage

    db_path = tmp_path / "legacy_live_order.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE live_order_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            inst_id TEXT NOT NULL,
            side TEXT NOT NULL,
            size TEXT NOT NULL,
            price TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            success INTEGER NOT NULL DEFAULT 0,
            error_message TEXT DEFAULT '',
            strategy_id TEXT,
            strategy_name TEXT,
            ts TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()

    storage = DataStorage(db_path)
    try:
        ok = storage.save_live_order(
            order_id="ord-legacy-1",
            inst_id="BTC-USDT",
            side="buy",
            size="0.01",
            price="100",
            signal_type="BUY",
            success=True,
            ts="2026-02-09T00:00:00",
            mode="live",
            strategy_id="legacy",
            strategy_name="Legacy",
        )
        assert ok is True

        rows = storage.get_live_orders(limit=10, mode="live")
        assert len(rows) == 1
        assert rows[0]["mode"] == "live"
    finally:
        storage.close()


def test_data_storage_live_order_client_id_migration_and_update_by_client_id(tmp_path):
    """旧库缺少 client_order_id 时应自动迁移，并支持按 client_order_id 回写执行结果。"""
    import sqlite3

    from app.core.data_storage import DataStorage

    db_path = tmp_path / "legacy_live_order_client_id.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE live_order_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id TEXT,
            inst_id TEXT NOT NULL,
            side TEXT NOT NULL,
            size TEXT NOT NULL,
            price TEXT NOT NULL,
            signal_type TEXT NOT NULL,
            success INTEGER NOT NULL DEFAULT 0,
            error_message TEXT DEFAULT '',
            strategy_id TEXT,
            strategy_name TEXT,
            ts TIMESTAMP NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()

    storage = DataStorage(db_path)
    try:
        ok = storage.save_live_order(
            order_id="",
            client_order_id="clid-1",
            inst_id="BTC-USDT",
            side="buy",
            size="0",
            price="0",
            signal_type="BUY",
            success=True,
            ts="2026-02-09T00:00:00",
            mode="simulated",
            strategy_id="legacy",
            strategy_name="Legacy",
            error_message="订单已受理，待成交补偿同步",
        )
        assert ok is True

        updated = storage.update_live_order_execution(
            order_id="",
            client_order_id="clid-1",
            mode="simulated",
            size="0.5",
            price="101",
            error_message="订单部分成交，补偿同步中",
        )
        assert updated is True

        rows = storage.get_live_orders(limit=10, mode="simulated")
        assert len(rows) == 1
        assert rows[0]["client_order_id"] == "clid-1"
        assert rows[0]["size"] == "0.5"
        assert rows[0]["price"] == "101"
    finally:
        storage.close()


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
    assert stub.calls == [None, 0]


def test_data_fetcher_get_history_candles_prefers_okx_history_endpoint(monkeypatch):
    """历史回补应优先走 OKX history-candles 接口，避免只拿到最近窗口。"""
    import app.core.data_fetcher as fetcher_mod
    from app.core.data_fetcher import DataFetcher

    monkeypatch.setattr(fetcher_mod.time, "sleep", lambda *_args, **_kwargs: None, raising=True)

    class DummyMarketAPI:
        def __init__(self):
            self.calls = []

        def get_history_candlesticks(self, **kwargs):
            self.calls.append(kwargs.get("after"))
            after = kwargs.get("after")
            if after is None:
                return {
                    "code": "0",
                    "data": [
                        ["6000", "6", "6", "6", "6", "1", "1", "6", "1"],
                        ["5000", "5", "5", "5", "5", "1", "1", "5", "1"],
                        ["4000", "4", "4", "4", "4", "1", "1", "4", "1"],
                    ],
                }
            if after == "3999":
                return {
                    "code": "0",
                    "data": [
                        ["3000", "3", "3", "3", "3", "1", "1", "3", "1"],
                        ["2000", "2", "2", "2", "2", "1", "1", "2", "1"],
                        ["1000", "1", "1", "1", "1", "1", "1", "1", "1"],
                    ],
                }
            return {"code": "0", "data": []}

        def get_candlesticks(self, **kwargs):
            raise AssertionError("历史回补不应退回到 recent candles 接口")

    fetcher = DataFetcher.__new__(DataFetcher)
    monkeypatch.setattr(fetcher, "market_api", DummyMarketAPI(), raising=False)

    candles = fetcher.get_history_candles(
        inst_id="BTC-USDT",
        timeframe="1H",
        start_time=None,
        end_time=None,
        max_candles=6,
    )

    assert [c.timestamp for c in candles] == [1000, 2000, 3000, 4000, 5000, 6000]
    assert fetcher.market_api.calls == [None, "3999"]


def test_data_fetcher_get_candles_skips_unconfirmed_last_bar(monkeypatch):
    """get_candles 应过滤未收盘K线，避免实盘策略对未完成bar下单。"""
    from app.core.data_fetcher import DataFetcher

    class DummyMarketAPI:
        def get_candlesticks(self, **kwargs):
            return {
                "code": "0",
                "data": [
                    # 最新未收盘（confirm=0），应被过滤
                    ["2000", "11", "12", "10", "11.5", "1", "1", "11", "0"],
                    # 已收盘（confirm=1），应保留
                    ["1000", "10", "11", "9", "10.5", "1", "1", "10", "1"],
                ],
            }

    # 跳过 __init__，避免测试环境缺少 python-okx 依赖导致失败。
    fetcher = DataFetcher.__new__(DataFetcher)
    monkeypatch.setattr(fetcher, "market_api", DummyMarketAPI(), raising=False)

    candles = fetcher.get_candles("BTC-USDT", "1H", 2)

    assert len(candles) == 1
    assert candles[0].timestamp == 1000
    assert candles[0].close == 10.5


