from __future__ import annotations

import types

import pytest

from app.config import OKXApiCredentials
import app.core.websocket_manager as ws_mod


class FakeOutboundGovernor:
    def acquire(self, op_key, scope_key):
        return None

    async def execute_ws_control(self, *, operation, **kwargs):
        return await operation()


class FakeSocket:
    def __init__(self, *, closed: bool = False):
        self.closed = closed
        self.recv_exc = None
        self.state = types.SimpleNamespace(name="OPEN")

    async def send(self, payload):
        return None


class FakePublicClient:
    def __init__(self, url):
        self.url = url
        self.websocket = None

    async def connect(self):
        self.websocket = FakeSocket()
        return None

    async def stop(self):
        return None


class FakePrivateClient:
    def __init__(self, *, apiKey, passphrase, secretKey, url):
        self.api_key = apiKey
        self.passphrase = passphrase
        self.secret_key = secretKey
        self.url = url
        self.websocket = None

    async def connect(self):
        self.websocket = FakeSocket(closed=False)
        return None

    async def stop(self):
        return None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("method_name", "channel_name", "running_attr", "client_attr"),
    [
        ("_start_public_connection", "public", "_public_running", "_public_ws"),
        ("_start_business_connection", "business", "_business_running", "_business_ws"),
    ],
)
async def test_public_ws_start_accepts_sdk_connect_without_return_value(
    monkeypatch,
    method_name,
    channel_name,
    running_attr,
    client_attr,
):
    monkeypatch.setattr(ws_mod.WsPublicAsync, "WsPublicAsync", FakePublicClient)

    manager = ws_mod.OKXWebSocketManager(
        is_simulated=True,
        outbound=FakeOutboundGovernor(),
    )
    spawned = []
    monkeypatch.setattr(
        manager,
        "_spawn_consumer_task",
        lambda name, client, callback: spawned.append((name, client)),
    )

    await getattr(manager, method_name)()

    client = getattr(manager, client_attr)
    assert getattr(manager, running_attr) is True
    assert client.websocket is not None
    assert spawned == [(channel_name, client)]


@pytest.mark.asyncio
async def test_private_ws_start_accepts_sdk_connect_without_return_value(monkeypatch):
    monkeypatch.setattr(ws_mod.WsPrivateAsync, "WsPrivateAsync", FakePrivateClient)
    monkeypatch.setattr(
        ws_mod.config.okx,
        "demo",
        OKXApiCredentials(api_key="key", secret_key="secret", passphrase="pass"),
    )

    manager = ws_mod.OKXWebSocketManager(
        is_simulated=True,
        outbound=FakeOutboundGovernor(),
    )
    spawned = []

    async def fake_sleep(seconds):
        return None

    async def fake_subscribe_private_channels():
        return None

    monkeypatch.setattr(ws_mod.asyncio, "sleep", fake_sleep)
    monkeypatch.setattr(
        manager,
        "_spawn_consumer_task",
        lambda name, client, callback: spawned.append((name, client)),
    )
    monkeypatch.setattr(
        manager,
        "_subscribe_private_channels",
        fake_subscribe_private_channels,
    )

    await manager.start_private()

    assert manager.is_private_running is True
    assert manager._private_ws.websocket is not None
    assert spawned == [("private", manager._private_ws)]
