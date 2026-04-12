from __future__ import annotations

from types import SimpleNamespace

import pytest

import app.core.trend_research.factory as factory_mod

from tests.test_trend_research_service import (
    FakeFetcher,
    FakeStorage,
    FakeWSManager,
)


@pytest.mark.asyncio
async def test_trend_research_service_rebinds_to_new_ws_manager_after_restart():
    from app.core.trend_research.service import TrendResearchService

    old_ws_manager = FakeWSManager()
    new_ws_manager = FakeWSManager()
    service = TrendResearchService(
        whitelist=("BTC-USDT-SWAP",),
        storage=FakeStorage(),
        fetcher=FakeFetcher(),
        ws_manager=old_ws_manager,
        ws_manager_supplier=lambda: new_ws_manager,
        feature_bar_seconds=1,
        state_sync_seconds=30,
        book_channel="books5",
    )

    await service.start()
    await service.on_ws_manager_restart()

    assert service.ws_manager is new_ws_manager
    assert service.on_trade not in old_ws_manager.trade_callbacks
    assert service.on_book not in old_ws_manager.book_callbacks
    assert service.on_trade in new_ws_manager.trade_callbacks
    assert service.on_book in new_ws_manager.book_callbacks
    assert new_ws_manager.trade_subscriptions == ["BTC-USDT-SWAP"]
    assert new_ws_manager.book_subscriptions == [("BTC-USDT-SWAP", "books5")]


def test_trend_research_factory_registers_ws_restart_listener(monkeypatch):
    factory_mod._service = None
    listeners = []
    ws_manager = FakeWSManager()

    defaults = {
        "enabled": True,
        "whitelist": ["BTC-USDT-SWAP"],
        "feature_bar_seconds": 1,
        "state_sync_seconds": 30,
        "book_channel": "books5",
    }

    class DummyContext:
        cfg = SimpleNamespace(trend_research=SimpleNamespace())

        def storage(self):
            return FakeStorage()

        def fetcher(self):
            return FakeFetcher()

        def ws_manager(self):
            return ws_manager

        def add_ws_restart_listener(self, listener):
            listeners.append(listener)

    monkeypatch.setattr(factory_mod, "build_default_trend_research_settings", lambda cfg: defaults)
    monkeypatch.setattr(factory_mod, "load_trend_research_settings", lambda cfg: defaults)
    monkeypatch.setattr(factory_mod, "_load_saved_model_bundle", lambda: None)

    service = factory_mod.get_trend_research_service(DummyContext())

    assert len(listeners) == 1
    assert listeners[0].__self__ is service
    assert listeners[0].__name__ == "on_ws_manager_restart"

    factory_mod._service = None
