import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient
import pytest

import app.api.websocket as websocket_api


class _FakeTrendResearchService:
    def __init__(self):
        self.listeners = []
        self.diagnostics_listeners = []

    def add_listener(self, listener):
        self.listeners.append(listener)

    def add_diagnostics_listener(self, listener):
        self.diagnostics_listeners.append(listener)

    def emit(self, payload):
        for listener in list(self.listeners):
            listener(payload)

    def emit_diagnostics(self, payload):
        for listener in list(self.diagnostics_listeners):
            listener(payload)


class _DummyPublicManager:
    is_running = False
    is_business_running = False

    def add_ticker_callback(self, callback):
        self.ticker_callback = callback

    def add_candle_callback(self, callback):
        self.candle_callback = callback


class _DummyContext:
    def __init__(self, trend_service):
        self.public_manager = _DummyPublicManager()
        self._trend_service = trend_service

    def ws_manager(self, mode=None):
        return self.public_manager

    async def start_ws(self, mode=None):
        return self.public_manager

    def trend_research(self):
        return self._trend_service

    def add_ws_restart_listener(self, listener):
        self.restart_listener = listener


def test_trend_research_service_listener_bridges_to_market_websocket(monkeypatch):
    trend_service = _FakeTrendResearchService()
    ctx = _DummyContext(trend_service)
    manager = websocket_api.ConnectionManager()
    loop_holder = {}
    original_connect = manager.connect

    async def connect_and_capture_loop(websocket):
        loop_holder["loop"] = asyncio.get_running_loop()
        await original_connect(websocket)

    monkeypatch.setattr(websocket_api, "get_ctx", lambda: ctx)
    monkeypatch.setattr(manager, "connect", connect_and_capture_loop)
    monkeypatch.setattr(websocket_api, "connection_manager", manager)

    def bridge(payload):
        asyncio.create_task(manager._broadcast_trend_research(payload))

    trend_service.add_listener(bridge)

    app = FastAPI()
    app.include_router(websocket_api.router)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/market") as websocket:
            websocket.send_json({"action": "subscribe", "channels": ["trend_research"]})
            subscribed = websocket.receive_json()

            assert subscribed["type"] == "subscribed"
            assert subscribed["channels"] == ["trend_research"]

            loop_holder["loop"].call_soon_threadsafe(
                trend_service.emit,
                {
                    "summary": {"trade_ready_count": 1},
                    "instruments": [{"inst_id": "BTC-USDT-SWAP"}],
                },
            )

            message = websocket.receive_json()
            assert message["type"] == "trend_research"
            assert message["data"]["summary"]["trade_ready_count"] == 1


@pytest.mark.asyncio
async def test_trend_research_bridge_coalesces_burst_payloads(monkeypatch):
    manager = websocket_api.ConnectionManager()
    sent_payloads = []
    first_send_started = asyncio.Event()
    release_send = asyncio.Event()

    async def fake_broadcast(payload):
        sent_payloads.append(payload)
        first_send_started.set()
        await release_send.wait()

    monkeypatch.setattr(websocket_api, "connection_manager", manager)
    monkeypatch.setattr(manager, "_broadcast_trend_research", fake_broadcast)

    websocket_api._on_trend_research_event({"seq": 1})
    websocket_api._on_trend_research_event({"seq": 2})
    websocket_api._on_trend_research_event({"seq": 3})

    await asyncio.wait_for(first_send_started.wait(), timeout=1)
    await asyncio.sleep(0)

    assert sent_payloads == [{"seq": 3}]

    release_send.set()
    await asyncio.sleep(0)


@pytest.mark.asyncio
async def test_trend_diagnostics_bridge_filters_selected_instrument(monkeypatch):
    manager = websocket_api.ConnectionManager()
    delivered = []

    async def fake_broadcast_to_subscribers(message, filter_fn):
        btc_subs = {"trend_diagnostics": {"active": True, "inst_id": "BTC-USDT-SWAP", "timeline_limit": 20}}
        eth_subs = {"trend_diagnostics": {"active": True, "inst_id": "ETH-USDT-SWAP", "timeline_limit": 20}}
        if filter_fn(btc_subs):
            delivered.append(("BTC-USDT-SWAP", message["data"]["inst_id"]))
        if filter_fn(eth_subs):
            delivered.append(("ETH-USDT-SWAP", message["data"]["inst_id"]))

    monkeypatch.setattr(manager, "_broadcast_to_subscribers", fake_broadcast_to_subscribers, raising=False)

    await manager._broadcast_trend_diagnostics(
        {
            "event_type": "timeline_appended",
            "inst_id": "BTC-USDT-SWAP",
            "payload": {"timeline_entry": {"sequence": 2, "kind": "trade"}},
        }
    )

    assert delivered == [("BTC-USDT-SWAP", "BTC-USDT-SWAP")]
