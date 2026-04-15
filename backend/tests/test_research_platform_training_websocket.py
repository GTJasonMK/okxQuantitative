from __future__ import annotations

import asyncio
import json

from starlette.websockets import WebSocketState

import app.api.websocket as websocket_api


class _DummyPublicManager:
    is_running = False
    is_business_running = False

    def add_ticker_callback(self, callback):
        self.ticker_callback = callback

    def add_candle_callback(self, callback):
        self.candle_callback = callback


class _DummyTrendResearchService:
    def add_listener(self, listener):
        self.listener = listener

    def add_diagnostics_listener(self, listener):
        self.diagnostics_listener = listener


class _DummyResearchPlatformService:
    def add_listener(self, listener):
        self.listener = listener


class _DummyContext:
    def __init__(self):
        self.public_manager = _DummyPublicManager()
        self._trend_service = _DummyTrendResearchService()
        self._research_platform = _DummyResearchPlatformService()

    def ws_manager(self, mode=None):
        return self.public_manager

    async def start_ws(self, mode=None):
        return self.public_manager

    def trend_research(self):
        return self._trend_service

    def research_platform(self):
        return self._research_platform


class _DummyWebSocket:
    def __init__(self):
        self.client_state = WebSocketState.CONNECTING
        self.sent_messages: list[str] = []

    async def accept(self):
        self.client_state = WebSocketState.CONNECTED

    async def send_text(self, message: str):
        self.sent_messages.append(message)


def test_training_run_websocket_event_shape(monkeypatch):
    monkeypatch.setattr(websocket_api, 'get_ctx', lambda: _DummyContext())
    manager = websocket_api.ConnectionManager()
    websocket = _DummyWebSocket()

    asyncio.run(manager.connect(websocket))
    asyncio.run(
        manager.handle_subscribe(
            websocket,
            {'action': 'subscribe', 'channels': ['research_platform']},
        )
    )
    asyncio.run(
        manager._broadcast_research_platform(
            {
                'event': 'training_run_updated',
                'run_id': 'run-1',
                'status': 'running',
                'progress_stage': 'rolling_origin_eval',
                'forecast_metrics_ref': 'artifact://forecast',
                'decision_metrics_ref': 'artifact://decision',
                'artifact_bundle_ref': 'artifact://training-run/run-1',
            }
        )
    )

    message = json.loads(websocket.sent_messages[-1])

    assert message['type'] == 'research_platform'
    assert message['data']['event'] == 'training_run_updated'
    assert message['data']['run_id'] == 'run-1'
