import asyncio

from fastapi import FastAPI
from fastapi.testclient import TestClient

import app.api.websocket as websocket_api


class _DummyPublicManager:
    is_running = False
    is_business_running = False

    def add_ticker_callback(self, callback):
        self.ticker_callback = callback

    def add_candle_callback(self, callback):
        self.candle_callback = callback


class _DummyTrendResearchService:
    def __init__(self):
        self.snapshot_count = 0

    def build_diagnostics_snapshot(self, *, inst_id=None, timeline_limit=40):
        self.snapshot_count += 1
        return {
            "selected_inst_id": inst_id or "BTC-USDT-SWAP",
            "instruments": [
                {
                    "inst_id": "BTC-USDT-SWAP",
                    "pipeline_stage": "collecting",
                    "is_error": False,
                    "is_stale": False,
                }
            ],
            "global_health": {
                "whitelist_count": 1,
                "active_count": 1,
                "stale_count": 0,
                "error_count": 0,
                "last_event_at": 1712365200.0,
            },
            "instrument_health": {
                "inst_id": "BTC-USDT-SWAP",
                "pipeline_stage": "collecting",
            },
            "timeline": [],
            "details": {
                "subscription_state": "subscribed",
            },
            "emitted_at": 1712365200.0 + self.snapshot_count,
        }


class _DummyContext:
    def __init__(self, trend_service=None):
        self.public_manager = _DummyPublicManager()
        self._trend_service = trend_service or _DummyTrendResearchService()

    def ws_manager(self, mode=None):
        return self.public_manager

    async def start_ws(self, mode=None):
        return self.public_manager

    def trend_research(self):
        return self._trend_service


def test_market_websocket_delivers_trend_research_updates(monkeypatch):
    ctx = _DummyContext()
    manager = websocket_api.ConnectionManager()
    loop_holder = {}
    original_connect = manager.connect

    async def connect_and_capture_loop(websocket):
        loop_holder["loop"] = asyncio.get_running_loop()
        await original_connect(websocket)

    monkeypatch.setattr(websocket_api, "get_ctx", lambda: ctx)
    monkeypatch.setattr(manager, "connect", connect_and_capture_loop)
    monkeypatch.setattr(websocket_api, "connection_manager", manager)

    app = FastAPI()
    app.include_router(websocket_api.router)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/market") as websocket:
            websocket.send_json({"action": "subscribe", "channels": ["trend_research"]})
            subscribed = websocket.receive_json()

            assert subscribed["type"] == "subscribed"
            assert subscribed["channels"] == ["trend_research"]
            assert manager.get_stats()["trend_research_subscribers"] == 1

            future = asyncio.run_coroutine_threadsafe(
                manager._broadcast_trend_research(
                    {
                        "status": "ready",
                        "training_run": {
                            "status": "running",
                            "current_stage": "train_epochs",
                        },
                        "training_summary": {
                            "status": "running",
                            "current_epoch": 8,
                            "total_epochs": 20,
                        },
                        "rows": [{"inst_id": "BTC-USDT-SWAP", "trend_state": "range"}],
                    }
                ),
                loop_holder["loop"],
            )
            assert future.result(timeout=2) is None

            message = websocket.receive_json()
            assert message["type"] == "trend_research"
            assert message["data"]["status"] == "ready"
            assert message["data"]["training_run"]["status"] == "running"
            assert message["data"]["training_run"]["current_stage"] == "train_epochs"
            assert message["data"]["training_summary"]["current_epoch"] == 8
            assert message["data"]["rows"][0]["inst_id"] == "BTC-USDT-SWAP"

    assert manager.get_stats()["trend_research_subscribers"] == 0


def test_market_websocket_delivers_trend_diagnostics_snapshot(monkeypatch):
    ctx = _DummyContext()
    manager = websocket_api.ConnectionManager()

    monkeypatch.setattr(websocket_api, "get_ctx", lambda: ctx)
    monkeypatch.setattr(websocket_api, "connection_manager", manager)

    app = FastAPI()
    app.include_router(websocket_api.router)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/market") as websocket:
            websocket.send_json(
                {
                    "action": "subscribe",
                    "channels": ["trend_diagnostics"],
                    "inst_id": "BTC-USDT-SWAP",
                    "timeline_limit": 20,
                }
            )
            snapshot = websocket.receive_json()

            assert snapshot["type"] == "trend_diagnostics"
            assert snapshot["data"]["event_type"] == "snapshot"
            assert snapshot["data"]["selected_inst_id"] == "BTC-USDT-SWAP"


def test_market_websocket_can_refresh_trend_diagnostics_snapshot_without_new_events(monkeypatch):
    trend_service = _DummyTrendResearchService()
    ctx = _DummyContext(trend_service=trend_service)
    manager = websocket_api.ConnectionManager()
    loop_holder = {}
    original_connect = manager.connect

    async def connect_and_capture_loop(websocket):
        loop_holder["loop"] = asyncio.get_running_loop()
        await original_connect(websocket)

    monkeypatch.setattr(websocket_api, "get_ctx", lambda: ctx)
    monkeypatch.setattr(manager, "connect", connect_and_capture_loop)
    monkeypatch.setattr(websocket_api, "connection_manager", manager)

    app = FastAPI()
    app.include_router(websocket_api.router)

    with TestClient(app) as client:
        with client.websocket_connect("/ws/market") as websocket:
            websocket.send_json(
                {
                    "action": "subscribe",
                    "channels": ["trend_diagnostics"],
                    "inst_id": "BTC-USDT-SWAP",
                    "timeline_limit": 20,
                }
            )
            first_snapshot = websocket.receive_json()
            assert first_snapshot["data"]["emitted_at"] == 1712365201.0
            subscribed = websocket.receive_json()
            assert subscribed["type"] == "subscribed"

            future = asyncio.run_coroutine_threadsafe(
                manager._broadcast_trend_diagnostics_snapshots_once(),
                loop_holder["loop"],
            )
            assert future.result(timeout=2) is None

            second_snapshot = websocket.receive_json()
            assert second_snapshot["type"] == "trend_diagnostics"
            assert second_snapshot["data"]["event_type"] == "snapshot"
            assert second_snapshot["data"]["emitted_at"] == 1712365202.0
