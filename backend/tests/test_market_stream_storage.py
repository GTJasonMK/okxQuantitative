from __future__ import annotations

import time
from threading import Lock

import pytest

import app.api.websocket as websocket_api
from app.core.cache import CachedDataFetcher
from app.core.data_fetcher import MarketTrade, Ticker
from app.core.data_storage import DataStorage
from app.core.websocket_manager import CandleData, TickerData


class _DummyRateLimiter:
    def acquire(self, count: int = 1):
        self.last_count = count

    def record_call(self, count: int = 1):
        self.last_count = count


def _build_cached_fetcher(storage: DataStorage, remote_fetcher=None) -> CachedDataFetcher:
    fetcher = object.__new__(CachedDataFetcher)
    fetcher._initialized = True
    fetcher._fetcher = remote_fetcher
    fetcher._storage = storage
    fetcher._ticker_cache = {}
    fetcher._sync_times = {}
    fetcher._cache_lock = Lock()
    fetcher._rate_limiter = _DummyRateLimiter()
    return fetcher


def test_ticker_cached_prefers_local_storage(tmp_path):
    storage = DataStorage(tmp_path / "market.db")
    now_ms = int(time.time() * 1000)
    storage.save_ticker_snapshot(
        Ticker(
            inst_id="BTC-USDT",
            last=101.5,
            last_sz=0.8,
            ask_px=101.6,
            ask_sz=1.2,
            bid_px=101.4,
            bid_sz=0.9,
            open_24h=100.0,
            high_24h=103.0,
            low_24h=98.0,
            vol_24h=12345.0,
            vol_ccy_24h=1234567.0,
            timestamp=now_ms,
        ),
        inst_type="SPOT",
        source="rest",
    )

    class RemoteFetcher:
        def __init__(self):
            self.calls = 0

        def get_ticker(self, inst_id: str):
            self.calls += 1
            return None

    remote = RemoteFetcher()
    fetcher = _build_cached_fetcher(storage, remote)

    ticker = fetcher.get_ticker_cached("BTC-USDT", "SPOT")

    assert ticker is not None
    assert ticker.last == 101.5
    assert remote.calls == 0


def test_recent_trades_initializes_from_remote_and_persists(tmp_path):
    storage = DataStorage(tmp_path / "market.db")
    now_ms = int(time.time() * 1000)

    class RemoteFetcher:
        def __init__(self):
            self.calls = 0

        def get_recent_trades(self, inst_id: str, limit: int):
            self.calls += 1
            return [
                MarketTrade(
                    inst_id=inst_id,
                    trade_id=f"trade-{index}",
                    price=100 + index,
                    size=0.1 + index,
                    side="buy" if index % 2 == 0 else "sell",
                    timestamp=now_ms - index * 1000,
                )
                for index in range(limit)
            ]

    remote = RemoteFetcher()
    fetcher = _build_cached_fetcher(storage, remote)

    trades = fetcher.get_recent_trades_local_first("BTC-USDT", limit=3, inst_type="SPOT")

    assert len(trades) == 3
    assert remote.calls == 1

    stored = storage.get_recent_trades("BTC-USDT", limit=3, inst_type="SPOT")
    assert len(stored) == 3
    assert stored[0].trade_id == "trade-0"


def test_orderbook_fetch_propagates_rate_limit_errors_before_remote_call(tmp_path):
    storage = DataStorage(tmp_path / "market.db")

    class ExplodingLimiter:
        def acquire(self, count: int = 1):
            raise RuntimeError("rate limit exceeded")

        def record_call(self, count: int = 1):  # pragma: no cover
            raise AssertionError("rate limit errors should happen before record_call")

    class RemoteFetcher:
        def __init__(self):
            self.calls = 0

        def get_orderbook(self, inst_id: str, size: int):
            self.calls += 1
            return {"inst_id": inst_id, "size": size}

    remote = RemoteFetcher()
    fetcher = _build_cached_fetcher(storage, remote)
    fetcher._rate_limiter = ExplodingLimiter()

    with pytest.raises(RuntimeError) as exc_info:
        fetcher.get_orderbook("BTC-USDT", 20)

    assert "rate limit exceeded" in str(exc_info.value)
    assert remote.calls == 0


@pytest.mark.asyncio
async def test_ws_ticker_callback_persists_snapshot(tmp_path, monkeypatch):
    storage = DataStorage(tmp_path / "market.db")
    fetcher = _build_cached_fetcher(storage, None)

    class FakeContext:
        def storage(self):
            return storage

        def fetcher(self):
            return fetcher

    monkeypatch.setattr(websocket_api, "get_ctx", lambda: FakeContext())

    manager = websocket_api.ConnectionManager()
    ticker = TickerData(
        inst_id="BTC-USDT",
        inst_type="SPOT",
        last=105.0,
        last_sz=1.0,
        ask_px=105.1,
        ask_sz=2.0,
        bid_px=104.9,
        bid_sz=1.5,
        open_24h=100.0,
        high_24h=108.0,
        low_24h=99.0,
        vol_24h=20000.0,
        vol_ccy_24h=2100000.0,
        timestamp=int(time.time() * 1000),
    )

    await manager._persist_ticker_snapshot("BTC-USDT", ticker)

    stored = storage.get_latest_ticker("BTC-USDT", inst_type="SPOT")
    assert stored is not None
    assert stored.last == 105.0


@pytest.mark.asyncio
async def test_ws_confirmed_candle_only_persists_closed_bar(tmp_path, monkeypatch):
    storage = DataStorage(tmp_path / "market.db")

    class FakeContext:
        def storage(self):
            return storage

        def fetcher(self):
            return _build_cached_fetcher(storage, None)

    monkeypatch.setattr(websocket_api, "get_ctx", lambda: FakeContext())

    manager = websocket_api.ConnectionManager()

    pending_candle = CandleData(
        inst_id="BTC-USDT",
        inst_type="SPOT",
        timeframe="1H",
        timestamp=1_700_000_000_000,
        open=100.0,
        high=106.0,
        low=99.0,
        close=105.0,
        volume=50.0,
        volume_ccy=5000.0,
        volume_quote=5000.0,
        confirm=0,
    )
    await manager._persist_confirmed_candle("BTC-USDT", "1H", pending_candle)
    assert storage.get_latest_candles("BTC-USDT", "1H", 1, inst_type="SPOT") == []

    confirmed_candle = CandleData(
        inst_id="BTC-USDT",
        inst_type="SPOT",
        timeframe="1H",
        timestamp=1_700_000_360_000,
        open=105.0,
        high=110.0,
        low=104.0,
        close=108.0,
        volume=80.0,
        volume_ccy=8000.0,
        volume_quote=8000.0,
        confirm=1,
    )
    await manager._persist_confirmed_candle("BTC-USDT", "1H", confirmed_candle)

    candles = storage.get_latest_candles("BTC-USDT", "1H", 1, inst_type="SPOT")
    assert len(candles) == 1
    assert candles[0].close == 108.0
