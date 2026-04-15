from __future__ import annotations

import asyncio

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


def test_websocket_supports_research_platform_channel(monkeypatch):
    ctx = _DummyContext()
    manager = websocket_api.ConnectionManager()
    websocket = _DummyWebSocket()

    monkeypatch.setattr(websocket_api, 'get_ctx', lambda: ctx)

    asyncio.run(manager.connect(websocket))
    asyncio.run(
        manager.handle_subscribe(
            websocket,
            {'action': 'subscribe', 'channels': ['research_platform']},
        )
    )

    assert manager.get_stats()['research_platform_subscribers'] == 1
    assert manager._connections[websocket]['research_platform'] is True


def test_websocket_broadcasts_collection_runtime_events(monkeypatch):
    ctx = _DummyContext()
    manager = websocket_api.ConnectionManager()
    websocket = _DummyWebSocket()

    monkeypatch.setattr(websocket_api, 'get_ctx', lambda: ctx)

    asyncio.run(manager.connect(websocket))
    asyncio.run(
        manager.handle_subscribe(
            websocket,
            {'action': 'subscribe', 'channels': ['research_platform']},
        )
    )
    asyncio.run(manager._broadcast_research_platform({'event': 'session_failed', 'session_id': 'sess-1'}))
    asyncio.run(
        manager._broadcast_research_platform(
            {'event': 'second_flushed', 'session_id': 'sess-1', 'second_bucket': 1713000000}
        )
    )
    asyncio.run(manager._broadcast_research_platform({'event': 'session_quality_updated', 'session_id': 'sess-1'}))

    assert 'session_failed' in websocket.sent_messages[0]
    assert 'second_flushed' in websocket.sent_messages[1]
    assert 'session_quality_updated' in websocket.sent_messages[2]
