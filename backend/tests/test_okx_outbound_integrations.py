from __future__ import annotations

import asyncio
import types
import unittest

import app.core.websocket_manager as ws_mod
from app.core.data_fetcher import DataFetcher
from app.core.trader import OKXAccount, OKXTrader
from app.core.websocket_manager import OKXWebSocketManager


class FakeOutboundGovernor:
    def __init__(self):
        self.rest_calls: list[tuple[str, str, str, str]] = []
        self.ws_calls: list[tuple[str, str, str, str]] = []

    def execute_rest(self, *, op_key, scope_key, inst_id="", mode="", operation):
        self.rest_calls.append((op_key, scope_key, inst_id, mode))
        return operation()

    async def execute_ws_control(self, *, op_key, scope_key, inst_id="", mode="", operation):
        self.ws_calls.append((op_key, scope_key, inst_id, mode))
        return await operation()


class FakeSocket:
    def __init__(self, *, closed: bool):
        self.closed = closed
        self.state = types.SimpleNamespace(name="CLOSED" if closed else "OPEN")
        self.protocol = types.SimpleNamespace(close_exc=RuntimeError("closed") if closed else None)


class FakePublicWS:
    def __init__(self, *, closed: bool = False):
        self.websocket = FakeSocket(closed=closed)
        self.subscribe_calls: list[list[dict]] = []
        self.unsubscribe_calls: list[list[dict]] = []
        self.stop_calls = 0

    async def subscribe(self, params, callback):
        self.subscribe_calls.append(params)
        return None

    async def unsubscribe(self, params, callback):
        self.unsubscribe_calls.append(params)
        return None

    async def stop(self):
        self.stop_calls += 1
        return None


def build_ws_manager(*, public_ws, outbound):
    manager = object.__new__(OKXWebSocketManager)
    manager._is_simulated = True
    manager._public_url = "wss://ws.okx.com:8443/ws/v5/public"
    manager._business_url = "wss://ws.okx.com:8443/ws/v5/business"
    manager._private_url = "wss://wspap.okx.com:8443/ws/v5/private?brokerId=9999"
    manager._public_running = True
    manager._business_running = False
    manager._private_running = False
    manager._public_ws = public_ws
    manager._business_ws = None
    manager._private_ws = None
    manager._public_consumer_task = None
    manager._business_consumer_task = None
    manager._private_consumer_task = None
    manager._subscribed_ticker_instruments = set()
    manager._subscribed_trade_instruments = set()
    manager._subscribed_book_keys = set()
    manager._subscribed_candle_keys = set()
    manager._ticker_cache = {}
    manager._candle_cache = {}
    manager._account_cache = {}
    manager._orders_cache = []
    manager._fills_cache = []
    manager._ticker_callbacks = []
    manager._trade_callbacks = []
    manager._book_callbacks = []
    manager._candle_callbacks = []
    manager._account_callbacks = []
    manager._orders_callbacks = []
    manager._fills_callbacks = []
    manager._public_message_count = 0
    manager._business_message_count = 0
    manager._private_message_count = 0
    manager._start_time = None
    manager._lock = None
    manager._outbound = outbound
    return manager


class DataFetcherOutboundIntegrationTests(unittest.TestCase):
    def test_data_fetcher_ticker_must_use_governor_before_market_api_call(self):
        calls = FakeOutboundGovernor()

        class FakeMarketAPI:
            def get_ticker(self, **kwargs):
                return {
                    "code": "0",
                    "data": [{"instId": "BTC-USDT", "last": "1", "ts": "1"}],
                }

        fetcher = object.__new__(DataFetcher)
        fetcher.market_api = FakeMarketAPI()
        fetcher.public_api = None
        fetcher.is_simulated = False
        fetcher._outbound = calls

        fetcher.get_ticker("BTC-USDT")

        self.assertEqual(calls.rest_calls, [("market.ticker", "public_ip", "BTC-USDT", "")])

    def test_data_fetcher_full_orderbook_uses_books_full_rule(self):
        calls = FakeOutboundGovernor()

        class FakeFullOrderbookResponse:
            def raise_for_status(self):
                return None

            def json(self):
                return {
                    "code": "0",
                    "data": [{"asks": [], "bids": [], "ts": "1"}],
                }

        fetcher = object.__new__(DataFetcher)
        fetcher.market_api = None
        fetcher.public_api = None
        fetcher.is_simulated = False
        fetcher._outbound = calls

        import app.core.data_fetcher as data_fetcher_module

        original_get = data_fetcher_module.httpx.get
        data_fetcher_module.httpx.get = lambda *args, **kwargs: FakeFullOrderbookResponse()
        try:
            fetcher.get_orderbook("BTC-USDT", 800)
        finally:
            data_fetcher_module.httpx.get = original_get

        self.assertEqual(calls.rest_calls[0][0], "market.books_full")


class TraderOutboundIntegrationTests(unittest.TestCase):
    def test_okx_trader_place_order_uses_trade_user_inst_scope(self):
        calls = FakeOutboundGovernor()

        class FakeTradeAPI:
            def place_order(self, **kwargs):
                return {"code": "0", "data": [{"ordId": "1", "clOrdId": ""}]}

        trader = object.__new__(OKXTrader)
        trader._is_simulated = False
        trader._trade_api = FakeTradeAPI()
        trader._outbound = calls

        trader.place_order("BTC-USDT", "buy", "limit", "1", "1")

        self.assertEqual(
            calls.rest_calls,
            [("trade.place_order", "trade_user_inst:live:BTC-USDT", "BTC-USDT", "live")],
        )

    def test_okx_account_get_balance_uses_private_user_scope(self):
        calls = FakeOutboundGovernor()

        class FakeAccountAPI:
            def get_account_balance(self, **kwargs):
                return {"code": "0", "data": [{"totalEq": "12"}], "msg": ""}

        account = object.__new__(OKXAccount)
        account._is_simulated = True
        account._account_api = FakeAccountAPI()
        account._outbound = calls

        payload = account.get_balance("USDT")

        self.assertEqual(payload["totalEq"], "12")
        self.assertEqual(
            calls.rest_calls,
            [("account.balance", "private_user:simulated", "", "simulated")],
        )


class WebSocketOutboundIntegrationTests(unittest.IsolatedAsyncioTestCase):
    async def test_ws_manager_subscribe_tickers_uses_connection_scope(self):
        calls = FakeOutboundGovernor()
        manager = build_ws_manager(public_ws=FakePublicWS(), outbound=calls)

        await manager.subscribe_tickers(["BTC-USDT"])

        self.assertEqual(calls.ws_calls[0][0], "ws.subscribe")
        self.assertTrue(calls.ws_calls[0][1].startswith("ws_conn_ops:"))
        self.assertEqual(calls.ws_calls[0][3], "simulated")

    async def test_ws_manager_reconnects_stale_public_socket_before_subscribe_trades(self):
        calls = FakeOutboundGovernor()
        stale_ws = FakePublicWS(closed=True)
        fresh_ws = FakePublicWS(closed=False)
        manager = build_ws_manager(public_ws=stale_ws, outbound=calls)
        manager._subscribed_ticker_instruments = {"BTC-USDT"}
        manager._subscribed_trade_instruments = {"BTC-USDT-SWAP"}
        manager._subscribed_book_keys = {"BTC-USDT-SWAP|books5"}

        reconnects = []

        async def fake_start():
            reconnects.append("public")
            manager._public_ws = fresh_ws
            manager._public_running = True

        manager._start_public_connection = fake_start

        await manager.subscribe_trades(["BTC-USDT-SWAP", "ETH-USDT-SWAP"])

        self.assertEqual(reconnects, ["public"])
        self.assertEqual(stale_ws.stop_calls, 1)
        self.assertIn([{"channel": "tickers", "instId": "BTC-USDT"}], fresh_ws.subscribe_calls)
        self.assertIn([{"channel": "trades", "instId": "BTC-USDT-SWAP"}], fresh_ws.subscribe_calls)
        self.assertIn([{"channel": "books5", "instId": "BTC-USDT-SWAP"}], fresh_ws.subscribe_calls)
        self.assertIn([{"channel": "trades", "instId": "ETH-USDT-SWAP"}], fresh_ws.subscribe_calls)

    async def test_ws_manager_recovers_public_socket_after_consumer_disconnect(self):
        calls = FakeOutboundGovernor()
        stale_ws = FakePublicWS(closed=False)
        fresh_ws = FakePublicWS(closed=False)
        manager = build_ws_manager(public_ws=stale_ws, outbound=calls)
        manager._subscribed_ticker_instruments = {"BTC-USDT"}
        manager._subscribed_trade_instruments = {"BTC-USDT-SWAP"}
        manager._subscribed_book_keys = {"BTC-USDT-SWAP|books5"}

        reconnected = asyncio.Event()
        original_delay = ws_mod.WS_RECONNECT_DELAY_SECONDS

        async def fake_start():
            manager._public_ws = fresh_ws
            manager._public_running = True
            reconnected.set()

        manager._start_public_connection = fake_start

        try:
            ws_mod.WS_RECONNECT_DELAY_SECONDS = 0
            await manager._handle_consumer_disconnect("public", stale_ws, RuntimeError("boom"))
            await asyncio.wait_for(reconnected.wait(), timeout=1)
            await asyncio.sleep(0)
        finally:
            ws_mod.WS_RECONNECT_DELAY_SECONDS = original_delay

        self.assertIn([{"channel": "tickers", "instId": "BTC-USDT"}], fresh_ws.subscribe_calls)
        self.assertIn([{"channel": "trades", "instId": "BTC-USDT-SWAP"}], fresh_ws.subscribe_calls)
        self.assertIn([{"channel": "books5", "instId": "BTC-USDT-SWAP"}], fresh_ws.subscribe_calls)

    async def test_ws_manager_refresh_trade_and_book_subscriptions_force_replay(self):
        calls = FakeOutboundGovernor()
        public_ws = FakePublicWS(closed=False)
        manager = build_ws_manager(public_ws=public_ws, outbound=calls)
        manager._subscribed_trade_instruments = {"BTC-USDT-SWAP"}
        manager._subscribed_book_keys = {"BTC-USDT-SWAP|books5"}

        await manager.refresh_trade_subscriptions(["BTC-USDT-SWAP"])
        await manager.refresh_book_subscriptions(["BTC-USDT-SWAP"], channel="books5")

        self.assertEqual(
            public_ws.unsubscribe_calls[0],
            [{"channel": "trades", "instId": "BTC-USDT-SWAP"}],
        )
        self.assertEqual(
            public_ws.subscribe_calls[0],
            [{"channel": "trades", "instId": "BTC-USDT-SWAP"}],
        )
        self.assertEqual(
            public_ws.unsubscribe_calls[1],
            [{"channel": "books5", "instId": "BTC-USDT-SWAP"}],
        )
        self.assertEqual(
            public_ws.subscribe_calls[1],
            [{"channel": "books5", "instId": "BTC-USDT-SWAP"}],
        )


if __name__ == "__main__":
    unittest.main()
