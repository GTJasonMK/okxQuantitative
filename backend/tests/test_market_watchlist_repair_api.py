from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import market as market_api


@pytest.mark.asyncio
async def test_repair_watched_symbol_starts_jobs_for_enabled_markets(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        market_api,
        "get_watched_symbol",
        lambda symbol: {
            "symbol": "BTC-USDT",
            "sync_spot": True,
            "sync_swap": False,
            "spot_inst_id": "BTC-USDT",
            "swap_inst_id": "BTC-USDT-SWAP",
        },
        raising=True,
    )

    def fake_start_watchlist_sync_jobs(manager, watched_record, *, sync_spot, sync_swap):
        captured["symbol"] = watched_record["symbol"]
        captured["sync_spot"] = sync_spot
        captured["sync_swap"] = sync_swap
        return [
            {"task_id": "job-1", "reused_existing": False},
            {"task_id": "job-2", "reused_existing": True},
        ]

    monkeypatch.setattr(
        market_api,
        "_start_watchlist_sync_jobs",
        fake_start_watchlist_sync_jobs,
        raising=True,
    )

    guardian_calls = []
    monkeypatch.setattr(
        market_api,
        "_request_guardian_run_now_safely",
        lambda source: guardian_calls.append(source),
        raising=True,
    )

    manager = SimpleNamespace(fetcher=object())
    response = await market_api.repair_watched_symbol(
        symbol="BTC-USDT",
        sync_spot=True,
        sync_swap=True,
        manager=manager,
    )

    assert captured["symbol"] == "BTC-USDT"
    assert captured["sync_spot"] is True
    assert captured["sync_swap"] is False
    assert response.data["started_count"] == 1
    assert response.data["reused_count"] == 1
    assert guardian_calls == ["repair_watched_symbol"]


@pytest.mark.asyncio
async def test_repair_watched_symbol_rejects_missing_watchlist_record(monkeypatch):
    monkeypatch.setattr(market_api, "get_watched_symbol", lambda symbol: None, raising=True)
    manager = SimpleNamespace(fetcher=object())

    with pytest.raises(HTTPException) as exc_info:
        await market_api.repair_watched_symbol(
            symbol="DOGE-USDT",
            sync_spot=True,
            sync_swap=True,
            manager=manager,
        )

    assert exc_info.value.status_code == 404
