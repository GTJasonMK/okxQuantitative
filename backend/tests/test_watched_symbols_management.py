from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api.market import _build_inventory_response
from app.api import market as market_api
from app.core.data_fetcher import Candle, MarketTrade, Ticker
from app.core.data_storage import DataStorage
from app.models.schemas import WatchedSymbolCreateRequest
from app.utils import preferences_store
from app.utils.watched_symbols_store import (
    add_watched_symbol,
    load_watched_symbols,
    remove_watched_symbol,
)


def test_watched_symbols_store_normalizes_and_deduplicates(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences_store, "PREFERENCES_FILE", tmp_path / "prefs.json", raising=True)

    created, existed = add_watched_symbol("btc")
    assert existed is False
    assert created["symbol"] == "BTC-USDT"
    assert created["spot_inst_id"] == "BTC-USDT"
    assert created["swap_inst_id"] == "BTC-USDT-SWAP"

    duplicate, existed = add_watched_symbol("BTC-USDT-SWAP")
    assert existed is True
    assert duplicate["symbol"] == "BTC-USDT"

    second, existed = add_watched_symbol("eth-usdt")
    assert existed is False
    assert second["symbol"] == "ETH-USDT"

    watched_symbols = load_watched_symbols()
    assert [item["symbol"] for item in watched_symbols] == ["BTC-USDT", "ETH-USDT"]

    removed, ok = remove_watched_symbol("btc-usdt")
    assert ok is True
    assert removed["symbol"] == "BTC-USDT"
    assert [item["symbol"] for item in load_watched_symbols()] == ["ETH-USDT"]


def test_watched_symbols_store_updates_sync_preferences_for_existing_symbol(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences_store, "PREFERENCES_FILE", tmp_path / "prefs.json", raising=True)

    created, existed = add_watched_symbol("btc", sync_spot=True, sync_swap=True)
    assert existed is False
    assert created["sync_spot"] is True
    assert created["sync_swap"] is True

    updated, existed = add_watched_symbol("BTC-USDT", sync_spot=False, sync_swap=True)
    assert existed is True
    assert updated["sync_spot"] is False
    assert updated["sync_swap"] is True

    stored = load_watched_symbols()
    assert stored[0]["symbol"] == "BTC-USDT"
    assert stored[0]["sync_spot"] is False
    assert stored[0]["sync_swap"] is True


def test_delete_symbol_related_data_removes_all_local_artifacts(tmp_path):
    storage = DataStorage(tmp_path / "market.db")
    now_ms = int(time.time() * 1000)

    spot_candle = Candle(
        timestamp=now_ms - 60_000,
        open=100.0,
        high=110.0,
        low=99.0,
        close=105.0,
        volume=12.0,
        volume_ccy=1200.0,
    )
    swap_candle = Candle(
        timestamp=now_ms,
        open=200.0,
        high=210.0,
        low=198.0,
        close=208.0,
        volume=20.0,
        volume_ccy=4200.0,
    )
    storage.save_candles("BTC-USDT", "1H", [spot_candle], "SPOT")
    storage.save_candles("BTC-USDT-SWAP", "1H", [swap_candle], "SWAP")

    storage.save_ticker_snapshot(
        Ticker(
            inst_id="BTC-USDT",
            last=105.0,
            last_sz=0.2,
            ask_px=105.1,
            ask_sz=0.5,
            bid_px=104.9,
            bid_sz=0.6,
            open_24h=100.0,
            high_24h=108.0,
            low_24h=96.0,
            vol_24h=2000.0,
            vol_ccy_24h=210_000.0,
            timestamp=now_ms,
        ),
        inst_type="SPOT",
        source="rest",
    )
    storage.save_recent_trades(
        [
            MarketTrade(
                inst_id="BTC-USDT",
                trade_id="trade-1",
                price=105.0,
                size=0.3,
                side="buy",
                timestamp=now_ms,
            )
        ],
        inst_type="SPOT",
        source="rest",
    )
    storage.save_fill(
        trade_id="fill-1",
        inst_id="BTC-USDT",
        side="buy",
        fill_px=105.0,
        fill_sz=0.4,
        ts=now_ms,
        mode="live",
        fee=0.01,
        fee_ccy="USDT",
    )
    storage.save_live_order(
        order_id="order-1",
        inst_id="BTC-USDT",
        side="buy",
        size="0.4",
        price="105",
        signal_type="manual",
        success=True,
        ts="2026-03-27T00:00:00",
        mode="live",
    )
    storage.save_backtest_result(
        {
            "strategy_name": "demo",
            "symbol": "BTC-USDT",
            "timeframe": "1H",
            "duration_days": 30,
            "initial_capital": 1000,
            "final_capital": 1100,
        },
        strategy_id="demo_strategy",
    )
    with storage._get_cursor() as cursor:
        cursor.execute(
            """
            INSERT INTO cost_basis (ccy, mode, avg_cost, total_qty, total_cost, total_fee)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("BTC", "live", "100", "1", "100", "0.1"),
        )

    deleted_counts = storage.delete_symbol_related_data("btc-usdt")

    assert deleted_counts["candles"] == 2
    assert deleted_counts["sync_records"] == 2
    assert deleted_counts["market_ticker_snapshots"] == 1
    assert deleted_counts["market_recent_trades"] == 1
    assert deleted_counts["local_fills"] == 1
    assert deleted_counts["live_order_records"] == 1
    assert deleted_counts["backtest_results"] == 1
    assert deleted_counts["cost_basis"] == 1
    assert deleted_counts["total"] == sum(
        value
        for key, value in deleted_counts.items()
        if key != "total"
    )

    assert storage.get_latest_candles("BTC-USDT", "1H", 10, inst_type="SPOT") == []
    assert storage.get_latest_candles("BTC-USDT-SWAP", "1H", 10, inst_type="SWAP") == []
    assert storage.get_sync_record("BTC-USDT", "1H", "SPOT") is None
    assert storage.get_sync_record("BTC-USDT-SWAP", "1H", "SWAP") is None
    assert storage.get_latest_ticker("BTC-USDT", inst_type="SPOT") is None
    assert storage.get_recent_trades("BTC-USDT", limit=5, inst_type="SPOT") == []
    assert storage.get_fills("live", inst_id="BTC-USDT", limit=5) == []
    assert storage.get_live_orders(limit=5, mode="live") == []
    assert storage.get_backtest_results(limit=5, symbol="BTC-USDT") == []

    with storage._get_cursor() as cursor:
        cursor.execute("SELECT COUNT(*) AS cnt FROM cost_basis WHERE ccy = ?", ("BTC",))
        row = cursor.fetchone()
        assert row["cnt"] == 0


def test_delete_symbol_related_data_keeps_other_pairs_with_same_base_ccy(tmp_path):
    storage = DataStorage(tmp_path / "market.db")
    now_ms = int(time.time() * 1000)

    storage.save_fill(
        trade_id="btc-usdt-fill",
        inst_id="BTC-USDT",
        side="buy",
        fill_px=100.0,
        fill_sz=1.0,
        ts=now_ms,
        mode="live",
        fee=0.0,
        fee_ccy="USDT",
    )
    storage.save_fill(
        trade_id="btc-usdc-fill",
        inst_id="BTC-USDC",
        side="buy",
        fill_px=200.0,
        fill_sz=2.0,
        ts=now_ms + 1,
        mode="live",
        fee=0.0,
        fee_ccy="USDC",
    )
    storage.update_cost_basis_from_fills("live")

    deleted_counts = storage.delete_symbol_related_data("BTC-USDT")

    remaining_fills = storage.get_fills("live", inst_id="BTC-USDC", limit=10)
    btc_cost = storage.get_cost_basis("live", "BTC")

    assert deleted_counts["local_fills"] == 1
    assert storage.get_fills("live", inst_id="BTC-USDT", limit=10) == []
    assert len(remaining_fills) == 1
    assert remaining_fills[0]["trade_id"] == "btc-usdc-fill"
    assert btc_cost["BTC"]["total_qty"] == pytest.approx(2.0)
    assert btc_cost["BTC"]["avg_cost"] == pytest.approx(200.0)


def test_build_inventory_response_marks_orphans_and_aggregates_counts(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences_store, "PREFERENCES_FILE", tmp_path / "prefs.json", raising=True)
    add_watched_symbol("btc")

    storage = DataStorage(tmp_path / "market.db")
    now_ms = int(time.time() * 1000)

    storage.save_candles(
        "BTC-USDT",
        "1H",
        [
            Candle(
                timestamp=now_ms,
                open=100.0,
                high=110.0,
                low=99.0,
                close=105.0,
                volume=12.0,
                volume_ccy=1200.0,
            )
        ],
        "SPOT",
    )
    storage.save_candles(
        "ETH-USDT",
        "4H",
        [
            Candle(
                timestamp=now_ms,
                open=2000.0,
                high=2100.0,
                low=1980.0,
                close=2060.0,
                volume=8.0,
                volume_ccy=16000.0,
            )
        ],
        "SPOT",
    )
    storage.save_recent_trades(
        [
            MarketTrade(
                inst_id="ETH-USDT",
                trade_id="eth-trade-1",
                price=2060.0,
                size=0.2,
                side="buy",
                timestamp=now_ms,
            )
        ],
        inst_type="SPOT",
        source="rest",
    )

    inventory = _build_inventory_response(storage)

    assert inventory["summary"]["symbol_count"] == 2
    assert inventory["summary"]["watched_symbol_count"] == 1
    assert inventory["summary"]["orphan_symbol_count"] == 1
    assert inventory["summary"]["total_candles"] == 2

    rows_by_symbol = {row["symbol"]: row for row in inventory["rows"]}
    assert rows_by_symbol["BTC-USDT"]["watched"] is True
    assert rows_by_symbol["BTC-USDT"]["orphan"] is False
    assert rows_by_symbol["ETH-USDT"]["watched"] is False
    assert rows_by_symbol["ETH-USDT"]["orphan"] is True
    assert rows_by_symbol["ETH-USDT"]["storage_counts"]["market_recent_trades"] == 1


def test_build_inventory_response_uses_covered_watch_count_not_total_watchlist(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences_store, "PREFERENCES_FILE", tmp_path / "prefs.json", raising=True)
    add_watched_symbol("btc")
    add_watched_symbol("eth")

    storage = DataStorage(tmp_path / "market.db")
    now_ms = int(time.time() * 1000)
    storage.save_candles(
        "BTC-USDT",
        "1H",
        [
            Candle(
                timestamp=now_ms,
                open=100.0,
                high=110.0,
                low=99.0,
                close=105.0,
                volume=12.0,
                volume_ccy=1200.0,
            )
        ],
        "SPOT",
    )

    inventory = _build_inventory_response(storage)

    assert inventory["summary"]["symbol_count"] == 1
    assert inventory["summary"]["watched_symbol_count"] == 1
    assert inventory["summary"]["watched_list_count"] == 2


class _FakeGuardian:
    def __init__(self):
        self.run_now_calls = 0

    def request_run_now(self):
        self.run_now_calls += 1
        return {"requested": True}


class _FakeManager:
    def __init__(self, fetcher):
        self.fetcher = fetcher


class _FailingGuardian:
    def request_run_now(self):
        raise RuntimeError("guardian boom")


def test_start_watchlist_sync_jobs_respects_enabled_guardian_plans(monkeypatch):
    class _FakeGuardianSettings:
        def get_settings(self):
            return {
                "plans": [
                    {"timeframe": "1D", "enabled": True, "bootstrap_days": 365, "archive_mode": "full"},
                    {"timeframe": "1H", "enabled": False, "bootstrap_days": 90, "archive_mode": "full"},
                    {"timeframe": "5m", "enabled": True, "bootstrap_days": 7, "archive_mode": "rolling"},
                ]
            }

    class _FakeTaskManager:
        def __init__(self):
            self.calls = []

        def start_job(self, **kwargs):
            self.calls.append(kwargs)
            return {"task_id": f"task-{len(self.calls)}", **kwargs}

    monkeypatch.setattr(market_api, "get_data_guardian", lambda: _FakeGuardianSettings())
    fake_task_manager = _FakeTaskManager()
    monkeypatch.setattr(market_api, "get_market_sync_task_manager", lambda: fake_task_manager)

    jobs = market_api._start_watchlist_sync_jobs(
        manager=SimpleNamespace(),
        watched_symbol={
            "symbol": "BTC-USDT",
            "spot_inst_id": "BTC-USDT",
            "swap_inst_id": "BTC-USDT-SWAP",
        },
        sync_spot=True,
        sync_swap=False,
    )

    assert [job["timeframe"] for job in jobs] == ["1D", "5m"]
    assert [job["mode"] for job in jobs] == ["full", "window"]


@pytest.mark.asyncio
async def test_create_watched_symbol_rolls_back_when_fetcher_unavailable(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences_store, "PREFERENCES_FILE", tmp_path / "prefs.json", raising=True)

    guardian = _FakeGuardian()
    monkeypatch.setattr(market_api, "get_data_guardian", lambda: guardian)

    with pytest.raises(HTTPException) as exc:
        await market_api.create_watched_symbol(
            WatchedSymbolCreateRequest(symbol="btc"),
            manager=_FakeManager(fetcher=None),
        )

    assert exc.value.status_code == 503
    assert "新增关注币种已回滚" in exc.value.detail
    assert load_watched_symbols() == []
    assert guardian.run_now_calls == 0


@pytest.mark.asyncio
async def test_create_watched_symbol_rolls_back_when_sync_job_start_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences_store, "PREFERENCES_FILE", tmp_path / "prefs.json", raising=True)

    guardian = _FakeGuardian()
    monkeypatch.setattr(market_api, "get_data_guardian", lambda: guardian)
    monkeypatch.setattr(
        market_api,
        "_start_watchlist_sync_jobs",
        lambda *args, **kwargs: (_ for _ in ()).throw(RuntimeError("boom")),
    )

    with pytest.raises(HTTPException) as exc:
        await market_api.create_watched_symbol(
            WatchedSymbolCreateRequest(symbol="eth-usdt"),
            manager=_FakeManager(fetcher=object()),
        )

    assert exc.value.status_code == 500
    assert "新增关注币种已回滚" in exc.value.detail
    assert "boom" in exc.value.detail
    assert load_watched_symbols() == []
    assert guardian.run_now_calls == 0


@pytest.mark.asyncio
async def test_create_watched_symbol_succeeds_when_guardian_run_now_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences_store, "PREFERENCES_FILE", tmp_path / "prefs.json", raising=True)
    monkeypatch.setattr(market_api, "get_data_guardian", lambda: _FailingGuardian())
    monkeypatch.setattr(
        market_api,
        "_start_watchlist_sync_jobs",
        lambda *args, **kwargs: [{
            "task_id": "task-1",
            "inst_id": "SOL-USDT",
            "inst_type": "SPOT",
            "timeframe": "1H",
            "mode": "window",
            "days": 30,
            "status": "running",
            "created_at": "2026-04-20T00:00:00+00:00",
        }],
    )

    response = await market_api.create_watched_symbol(
        WatchedSymbolCreateRequest(symbol="sol"),
        manager=_FakeManager(fetcher=object()),
    )

    assert response.data is not None
    assert response.data.watched_symbol.symbol == "SOL-USDT"
    assert response.data.existed is False
    assert response.data.sync_jobs[0].task_id == "task-1"
    assert [item["symbol"] for item in load_watched_symbols()] == ["SOL-USDT"]


@pytest.mark.asyncio
async def test_delete_watched_symbol_rolls_back_watchlist_when_storage_delete_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences_store, "PREFERENCES_FILE", tmp_path / "prefs.json", raising=True)
    add_watched_symbol("btc")

    storage = DataStorage(tmp_path / "market.db")
    monkeypatch.setattr(
        storage,
        "delete_symbol_related_data",
        lambda symbol: (_ for _ in ()).throw(RuntimeError("db boom")),
        raising=False,
    )
    monkeypatch.setattr(market_api, "get_data_guardian", lambda: _FakeGuardian())

    with pytest.raises(HTTPException) as exc:
        await market_api.delete_watched_symbol("btc", storage=storage)

    assert exc.value.status_code == 500
    assert "回滚关注列表" in exc.value.detail
    assert [item["symbol"] for item in load_watched_symbols()] == ["BTC-USDT"]
    assert storage.is_symbol_write_blocked("BTC-USDT") is False


@pytest.mark.asyncio
async def test_delete_watched_symbol_succeeds_when_guardian_run_now_fails(tmp_path, monkeypatch):
    monkeypatch.setattr(preferences_store, "PREFERENCES_FILE", tmp_path / "prefs.json", raising=True)
    add_watched_symbol("btc")
    storage = DataStorage(tmp_path / "market.db")
    monkeypatch.setattr(market_api, "get_data_guardian", lambda: _FailingGuardian())

    response = await market_api.delete_watched_symbol("btc", storage=storage)

    assert response.data is not None
    assert response.data.symbol == "BTC-USDT"
    assert response.data.deleted is True
    assert load_watched_symbols() == []
    assert storage.is_symbol_write_blocked("BTC-USDT") is True


@pytest.mark.asyncio
async def test_market_api_ticker_returns_503_when_fetcher_missing(tmp_path):
    storage = DataStorage(tmp_path / "market.db")
    now_ms = int(time.time() * 1000)
    storage.save_ticker_snapshot(
        Ticker(
            inst_id="BTC-USDT",
            last=30123.5,
            last_sz=0.2,
            ask_px=30124.0,
            ask_sz=0.3,
            bid_px=30123.0,
            bid_sz=0.4,
            open_24h=29800.0,
            high_24h=30500.0,
            low_24h=29750.0,
            vol_24h=2000.0,
            vol_ccy_24h=60000000.0,
            timestamp=now_ms,
        ),
        inst_type="SPOT",
    )

    with pytest.raises(HTTPException) as exc:
        await market_api.get_ticker(
            "BTC-USDT",
            inst_type=market_api.InstTypeEnum.SPOT,
            fetcher=None,
            storage=storage,
        )

    assert exc.value.status_code == 503
    assert "行情抓取器不可用" in exc.value.detail


@pytest.mark.asyncio
async def test_market_api_tickers_and_trades_return_503_when_fetcher_missing(tmp_path):
    storage = DataStorage(tmp_path / "market.db")
    now_ms = int(time.time() * 1000)
    storage.save_ticker_snapshot(
        Ticker(
            inst_id="ETH-USDT",
            last=2050.5,
            last_sz=1.0,
            ask_px=2051.0,
            ask_sz=2.0,
            bid_px=2050.0,
            bid_sz=1.5,
            open_24h=2000.0,
            high_24h=2100.0,
            low_24h=1980.0,
            vol_24h=5000.0,
            vol_ccy_24h=10250000.0,
            timestamp=now_ms,
        ),
        inst_type="SPOT",
    )
    storage.save_recent_trades(
        [
            MarketTrade(
                inst_id="ETH-USDT",
                trade_id="eth-1",
                price=2050.5,
                size=0.4,
                side="buy",
                timestamp=now_ms,
            )
        ],
        inst_type="SPOT",
    )

    with pytest.raises(HTTPException) as tickers_exc:
        await market_api.get_tickers(
            inst_type=market_api.InstTypeEnum.SPOT,
            fetcher=None,
            storage=storage,
        )
    with pytest.raises(HTTPException) as trades_exc:
        await market_api.get_recent_trades(
            "ETH-USDT",
            limit=30,
            inst_type=market_api.InstTypeEnum.SPOT,
            fetcher=None,
            storage=storage,
        )

    assert tickers_exc.value.status_code == 503
    assert "行情抓取器不可用" in tickers_exc.value.detail
    assert trades_exc.value.status_code == 503
    assert "行情抓取器不可用" in trades_exc.value.detail
