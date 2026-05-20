import asyncio

import pytest
from fastapi import HTTPException

import app.api.market as market_api
import app.api.trading as trading_api
import app.api.websocket as websocket_api
from app.core.data_storage import DataStorage
from app.core.websocket_manager import OKXWebSocketManager


class _ExplodingMarketFetcher:
    def __init__(self, method_name: str, message: str):
        self._method_name = method_name
        self._message = message

    def get_ticker_cached(self, inst_id: str, inst_type: str):
        if self._method_name != "ticker":
            raise AssertionError("unexpected market fetch call")
        raise RuntimeError(self._message)

    def get_tickers_cached(self, inst_type: str):
        if self._method_name != "tickers":
            raise AssertionError("unexpected market fetch call")
        raise RuntimeError(self._message)

    def get_recent_trades_local_first(self, inst_id: str, limit: int, *, inst_type: str):
        if self._method_name != "trades":
            raise AssertionError("unexpected market fetch call")
        raise RuntimeError(self._message)

    def get_ticker_strict(self, inst_id: str, inst_type: str):
        return self.get_ticker_cached(inst_id, inst_type)

    def get_tickers_strict(self, inst_type: str):
        return self.get_tickers_cached(inst_type)

    def get_recent_trades_strict(self, inst_id: str, limit: int, *, inst_type: str):
        return self.get_recent_trades_local_first(inst_id, limit, inst_type=inst_type)


class _UnavailableMarketFetcher:
    fetcher = None

    def get_ticker_cached(self, inst_id: str, inst_type: str):
        return None

    def get_tickers_cached(self, inst_type: str):
        return {}

    def get_recent_trades_local_first(self, inst_id: str, limit: int, *, inst_type: str):
        return []

    def get_ticker_strict(self, inst_id: str, inst_type: str):
        raise RuntimeError("行情抓取器不可用")

    def get_tickers_strict(self, inst_type: str):
        raise RuntimeError("行情抓取器不可用")

    def get_recent_trades_strict(self, inst_id: str, limit: int, *, inst_type: str):
        raise RuntimeError("行情抓取器不可用")


class _ExplodingAccount:
    is_available = True

    def __init__(self, *, positions_error: str = "", contract_positions_error: str = ""):
        self._positions_error = positions_error
        self._contract_positions_error = contract_positions_error

    def get_positions(self, inst_type: str = "", inst_id: str = ""):
        raise RuntimeError(self._positions_error)

    def get_contract_positions(self, inst_type: str = "SWAP", inst_id: str = ""):
        raise RuntimeError(self._contract_positions_error)


class _ExplodingTrader:
    is_available = True

    def __init__(self, *, orders_error: str = "", history_error: str = "", fills_error: str = ""):
        self._orders_error = orders_error
        self._history_error = history_error
        self._fills_error = fills_error

    def get_pending_orders(self, inst_type: str = "SPOT", inst_id: str = ""):
        raise RuntimeError(self._orders_error)

    def get_order_history(self, inst_type: str = "SPOT", inst_id: str = "", limit: str = "50"):
        raise RuntimeError(self._history_error)

    def get_fills(self, inst_type: str = "SPOT", inst_id: str = "", limit: str = "50"):
        raise RuntimeError(self._fills_error)


class _DummyPublicManager:
    is_running = False
    is_business_running = False


class _DummyPrivateManager:
    def add_account_callback(self, callback):
        self.account_callback = callback

    def add_orders_callback(self, callback):
        self.orders_callback = callback

    def add_fills_callback(self, callback):
        self.fills_callback = callback


class _FakeWsContext:
    def __init__(self):
        self.public_manager = _DummyPublicManager()
        self.private_managers = {
            "simulated": _DummyPrivateManager(),
            "live": _DummyPrivateManager(),
        }
        self.stopped_modes = []

    def ws_manager(self, mode=None):
        if mode in self.private_managers:
            return self.private_managers[mode]
        return self.public_manager

    async def start_ws(self, mode=None):
        return self.public_manager

    async def start_private_ws(self, mode: str):
        return self.private_managers[mode]

    async def stop_private_ws(self, mode: str):
        self.stopped_modes.append(mode)


def _make_connection_subs():
    return {
        "tickers": set(),
        "candles": set(),
        "account": False,
        "orders": False,
        "fills": False,
        "alerts": False,
        "assistant_patrol": False,
        "trend_research": False,
        "mode": None,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("call", "fetcher", "expected_detail"),
    [
        (
            lambda storage, fetcher: market_api.get_ticker(
                "BTC-USDT",
                inst_type=market_api.InstTypeEnum.SPOT,
                fetcher=fetcher,
                storage=storage,
            ),
            _ExplodingMarketFetcher("ticker", "ticker upstream down"),
            "ticker upstream down",
        ),
        (
            lambda storage, fetcher: market_api.get_tickers(
                inst_type=market_api.InstTypeEnum.SPOT,
                fetcher=fetcher,
                storage=storage,
            ),
            _ExplodingMarketFetcher("tickers", "tickers upstream down"),
            "tickers upstream down",
        ),
        (
            lambda storage, fetcher: market_api.get_recent_trades(
                "BTC-USDT",
                limit=20,
                inst_type=market_api.InstTypeEnum.SPOT,
                fetcher=fetcher,
                storage=storage,
            ),
            _ExplodingMarketFetcher("trades", "trades upstream down"),
            "trades upstream down",
        ),
        (
            lambda storage, fetcher: market_api.get_ticker(
                "BTC-USDT",
                inst_type=market_api.InstTypeEnum.SPOT,
                fetcher=fetcher,
                storage=storage,
            ),
            _UnavailableMarketFetcher(),
            "行情抓取器不可用",
        ),
        (
            lambda storage, fetcher: market_api.get_tickers(
                inst_type=market_api.InstTypeEnum.SPOT,
                fetcher=fetcher,
                storage=storage,
            ),
            _UnavailableMarketFetcher(),
            "行情抓取器不可用",
        ),
        (
            lambda storage, fetcher: market_api.get_recent_trades(
                "BTC-USDT",
                limit=20,
                inst_type=market_api.InstTypeEnum.SPOT,
                fetcher=fetcher,
                storage=storage,
            ),
            _UnavailableMarketFetcher(),
            "行情抓取器不可用",
        ),
    ],
)
async def test_market_endpoints_return_503_when_upstream_unavailable(tmp_path, call, fetcher, expected_detail):
    storage = DataStorage(tmp_path / "market.db")

    with pytest.raises(HTTPException) as exc_info:
        await call(storage, fetcher)

    assert exc_info.value.status_code == 503
    assert expected_detail in exc_info.value.detail


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("patch_name", "stub_factory", "call", "expected_detail"),
    [
        (
            "get_account",
            lambda: _ExplodingAccount(positions_error="positions upstream down"),
            lambda: trading_api.get_positions(inst_type="SPOT", inst_id="", mode="simulated"),
            "positions upstream down",
        ),
        (
            "get_account",
            lambda: _ExplodingAccount(contract_positions_error="contract positions upstream down"),
            lambda: trading_api.get_contract_positions(inst_type="SWAP", inst_id="", mode="simulated"),
            "contract positions upstream down",
        ),
        (
            "get_trader",
            lambda: _ExplodingTrader(orders_error="orders upstream down"),
            lambda: trading_api.get_pending_orders(inst_type="SPOT", inst_id="", mode="simulated"),
            "orders upstream down",
        ),
        (
            "get_trader",
            lambda: _ExplodingTrader(history_error="order history upstream down"),
            lambda: trading_api.get_order_history(inst_type="SPOT", inst_id="", limit="50", mode="simulated"),
            "order history upstream down",
        ),
        (
            "get_trader",
            lambda: _ExplodingTrader(fills_error="fills upstream down"),
            lambda: trading_api.get_fills(inst_type="SPOT", inst_id="", limit="50", mode="simulated"),
            "fills upstream down",
        ),
    ],
)
async def test_trading_endpoints_return_503_when_upstream_query_fails(
    monkeypatch,
    patch_name,
    stub_factory,
    call,
    expected_detail,
):
    monkeypatch.setattr(trading_api, patch_name, lambda mode: stub_factory())

    with pytest.raises(HTTPException) as exc_info:
        await call()

    assert exc_info.value.status_code == 503
    assert expected_detail in exc_info.value.detail


def test_public_market_ws_uses_live_source_even_in_simulated_mode():
    manager = OKXWebSocketManager(is_simulated=True)

    assert manager._public_url == "wss://ws.okx.com:8443/ws/v5/public"
    assert manager._business_url == "wss://ws.okx.com:8443/ws/v5/business"
    assert manager._private_url == "wss://wspap.okx.com:8443/ws/v5/private?brokerId=9999"


@pytest.mark.asyncio
async def test_connection_manager_stops_private_ws_when_last_private_channel_unsubscribes(monkeypatch):
    ctx = _FakeWsContext()
    monkeypatch.setattr(websocket_api, "get_ctx", lambda: ctx)

    manager = websocket_api.ConnectionManager()
    ws = object()
    manager._connections[ws] = _make_connection_subs()

    await manager.handle_subscribe(ws, {"channels": ["account"], "mode": "simulated"})
    await manager.handle_unsubscribe(ws, {"channels": ["account"]})

    assert ctx.stopped_modes == ["simulated"]


@pytest.mark.asyncio
async def test_connection_manager_stops_private_ws_when_last_private_client_disconnects(monkeypatch):
    ctx = _FakeWsContext()
    monkeypatch.setattr(websocket_api, "get_ctx", lambda: ctx)

    manager = websocket_api.ConnectionManager()
    ws = object()
    manager._connections[ws] = _make_connection_subs()

    await manager.handle_subscribe(ws, {"channels": ["fills"], "mode": "live"})
    manager.disconnect(ws)
    await asyncio.sleep(0)

    assert ctx.stopped_modes == ["live"]


@pytest.mark.asyncio
async def test_connection_manager_broadcasts_trend_research_to_subscribers_only(monkeypatch):
    from starlette.websockets import WebSocketState

    class FakeSocket:
        def __init__(self):
            self.client_state = WebSocketState.CONNECTED
            self.messages = []

        async def send_text(self, message: str):
            self.messages.append(message)

    ctx = _FakeWsContext()
    monkeypatch.setattr(websocket_api, "get_ctx", lambda: ctx)

    manager = websocket_api.ConnectionManager()
    subscribed = FakeSocket()
    idle = FakeSocket()
    subscribed_subs = _make_connection_subs()
    subscribed_subs["trend_research"] = True
    manager._connections[subscribed] = subscribed_subs
    manager._connections[idle] = _make_connection_subs()

    await manager._broadcast_trend_research({"status": "ready", "rows": []})

    assert len(subscribed.messages) == 1
    assert "\"type\": \"trend_research\"" in subscribed.messages[0]
    assert idle.messages == []
