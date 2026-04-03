from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

import app.core.data_manager as data_manager_mod
from app.core.data_fetcher import Candle, MarketTrade, Ticker
from app.core.data_storage import DataManager, DataStorage
from app.core.market_sync_tasks import MarketSyncTaskManager, SyncJobState


HOUR_MS = 60 * 60 * 1000


def _candle(timestamp: int, close: float) -> Candle:
    return Candle(
        timestamp=timestamp,
        open=close,
        high=close + 1,
        low=close - 1,
        close=close,
        volume=10,
        volume_ccy=100,
    )


def test_sync_record_preserves_history_metadata_after_new_save(tmp_path):
    storage = DataStorage(tmp_path / "market.db")

    storage.save_candles(
        "BTC-USDT",
        "1H",
        [_candle(1 * HOUR_MS, 100), _candle(2 * HOUR_MS, 101)],
    )
    storage.update_sync_record(
        "BTC-USDT",
        "1H",
        history_complete=True,
        last_sync_mode="full",
    )

    storage.save_candles("BTC-USDT", "1H", [_candle(3 * HOUR_MS, 102)])

    record = storage.get_sync_record("BTC-USDT", "1H")
    assert record is not None
    assert record["history_complete"] is True
    assert record["last_sync_mode"] == "full"
    assert record["candle_count"] == 3
    assert record["oldest_timestamp"] == 1 * HOUR_MS
    assert record["newest_timestamp"] == 3 * HOUR_MS


def test_incremental_sync_starts_after_local_newest_timestamp(tmp_path):
    storage = DataStorage(tmp_path / "market.db")
    storage.save_candles(
        "BTC-USDT",
        "1H",
        [_candle(1 * HOUR_MS, 100), _candle(2 * HOUR_MS, 101)],
    )

    class IncrementalFetcher:
        def __init__(self):
            self.start_time = None

        def get_history_candles(self, inst_id, timeframe, start_time=None, end_time=None, max_candles=1000):
            self.start_time = start_time
            assert inst_id == "BTC-USDT"
            assert timeframe == "1H"
            return [_candle(3 * HOUR_MS, 102)]

    fetcher = IncrementalFetcher()
    manager = DataManager(storage, fetcher)

    result = manager.sync_candles_incremental("BTC-USDT", "1H")

    assert result["mode"] == "incremental"
    assert result["saved_count"] == 1
    assert fetcher.start_time is not None
    assert int(fetcher.start_time.timestamp() * 1000) == 3 * HOUR_MS

    record = storage.get_sync_record("BTC-USDT", "1H")
    assert record is not None
    assert record["last_sync_mode"] == "incremental"
    assert record["history_complete"] is False
    assert record["newest_timestamp"] == 3 * HOUR_MS


def test_full_sync_backfills_until_history_exhausted(tmp_path, monkeypatch):
    storage = DataStorage(tmp_path / "market.db")
    monkeypatch.setattr(data_manager_mod.time, "sleep", lambda *_args, **_kwargs: None, raising=True)

    class FullFetcher:
        def __init__(self):
            self.after_calls = []

        def get_candles(self, inst_id, timeframe, limit=300, after=None, before=None):
            self.after_calls.append(after)
            assert inst_id == "BTC-USDT"
            assert timeframe == "1H"
            if after is None:
                return [_candle(3 * HOUR_MS, 103), _candle(4 * HOUR_MS, 104)]
            if after == 3 * HOUR_MS:
                return [_candle(1 * HOUR_MS, 101), _candle(2 * HOUR_MS, 102)]
            if after == 1 * HOUR_MS:
                return []
            raise AssertionError(f"unexpected pagination cursor: {after}")

        def get_history_candles(self, *args, **kwargs):
            raise AssertionError("full sync on empty storage should not call incremental history fetch")

    fetcher = FullFetcher()
    manager = DataManager(storage, fetcher)

    result = manager.sync_candles_full("BTC-USDT", "1H")

    assert result["mode"] == "full"
    assert result["saved_count"] == 4
    assert result["fetched_count"] == 4
    assert result["batches"] == 2
    assert result["api_calls"] == 3
    assert fetcher.after_calls == [None, 3 * HOUR_MS, 1 * HOUR_MS]

    record = storage.get_sync_record("BTC-USDT", "1H")
    assert record is not None
    assert record["history_complete"] is True
    assert record["last_sync_mode"] == "full"
    assert record["oldest_timestamp"] == 1 * HOUR_MS
    assert record["newest_timestamp"] == 4 * HOUR_MS


def test_task_manager_task_ids_filter_is_applied_before_limit():
    manager = MarketSyncTaskManager()

    with manager._lock:
        for index in range(12):
            task_id = f"job-{index:02d}"
            manager._jobs[task_id] = SyncJobState(
                task_id=task_id,
                inst_id=f"COIN-{index:02d}-USDT",
                inst_type="SPOT",
                timeframe="1H",
                mode="incremental",
                days=30,
                created_at=f"2026-03-27T00:00:{index:02d}",
            )

    jobs = manager.list_jobs(limit=3, task_ids=["job-00", "job-01", "job-02", "job-03"])

    assert [job["task_id"] for job in jobs] == ["job-03", "job-02", "job-01", "job-00"]


def test_blocked_symbol_rejects_candles_streams_and_sync_record_writes(tmp_path):
    storage = DataStorage(tmp_path / "market.db")
    now_ms = 4 * HOUR_MS

    storage.block_symbol_writes("BTC-USDT")

    saved_candles = storage.save_candles(
        "BTC-USDT",
        "1H",
        [_candle(now_ms, 104)],
    )
    storage.update_sync_record("BTC-USDT", "1H")
    saved_ticker = storage.save_ticker_snapshot(
        Ticker(
            inst_id="BTC-USDT",
            last=104.0,
            last_sz=1.0,
            ask_px=104.1,
            ask_sz=1.0,
            bid_px=103.9,
            bid_sz=1.0,
            open_24h=100.0,
            high_24h=110.0,
            low_24h=99.0,
            vol_24h=1000.0,
            vol_ccy_24h=104000.0,
            timestamp=now_ms,
        ),
        inst_type="SPOT",
    )
    saved_trades = storage.save_recent_trades(
        [
            MarketTrade(
                inst_id="BTC-USDT",
                trade_id="trade-1",
                price=104.0,
                size=0.2,
                side="buy",
                timestamp=now_ms,
            )
        ],
        inst_type="SPOT",
    )

    assert saved_candles == 0
    assert saved_ticker is False
    assert saved_trades == 0
    assert storage.get_latest_candles("BTC-USDT", "1H", 10) == []
    assert storage.get_sync_record("BTC-USDT", "1H") is None
    assert storage.get_latest_ticker("BTC-USDT", inst_type="SPOT") is None
    assert storage.get_recent_trades("BTC-USDT", limit=5, inst_type="SPOT") == []


def test_task_manager_dedup_key_distinguishes_mode_and_days():
    manager = MarketSyncTaskManager()
    release = threading.Event()

    def runner(_progress_callback):
        release.wait(timeout=1)
        return {"message": "ok"}

    first = manager.start_job(
        inst_id="BTC-USDT",
        inst_type="SPOT",
        timeframe="1H",
        mode="incremental",
        days=30,
        runner=runner,
    )
    same = manager.start_job(
        inst_id="BTC-USDT",
        inst_type="SPOT",
        timeframe="1H",
        mode="incremental",
        days=30,
        runner=runner,
    )
    second = manager.start_job(
        inst_id="BTC-USDT",
        inst_type="SPOT",
        timeframe="1H",
        mode="full",
        days=365,
        runner=runner,
    )
    third = manager.start_job(
        inst_id="BTC-USDT",
        inst_type="SPOT",
        timeframe="1H",
        mode="incremental",
        days=7,
        runner=runner,
    )

    assert same["task_id"] == first["task_id"]
    assert same["reused_existing"] is True
    assert second["task_id"] != first["task_id"]
    assert third["task_id"] != first["task_id"]
    assert len(manager.list_jobs(only_active=True, limit=10)) == 3

    release.set()


def test_task_manager_cancel_jobs_keeps_cancelled_job_out_of_active_list():
    manager = MarketSyncTaskManager()
    release = threading.Event()

    def runner(progress_callback):
        progress_callback({"progress": 10, "message": "started"})
        release.wait(timeout=1)
        progress_callback({"progress": 60, "message": "after-cancel"})
        return {"message": "done"}

    job = manager.start_job(
        inst_id="BTC-USDT",
        inst_type="SPOT",
        timeframe="1H",
        mode="full",
        days=30,
        runner=runner,
    )

    cancelled = manager.cancel_jobs(inst_ids=["BTC-USDT"], reason="test cancel")
    release.set()

    deadline = time.time() + 1.0
    snapshot = None
    while time.time() < deadline:
        snapshot = manager.get_job(job["task_id"])
        if snapshot and snapshot["status"] == "cancelled":
            break
        time.sleep(0.01)

    assert cancelled
    assert cancelled[0]["task_id"] == job["task_id"]
    assert cancelled[0]["status"] == "cancelled"
    assert snapshot is not None
    assert snapshot["status"] == "cancelled"
    assert snapshot["cancel_requested"] is True
    assert manager.list_jobs(only_active=True, limit=10) == []


def test_get_candles_with_sync_initializes_missing_symbol_with_full_sync(tmp_path, monkeypatch):
    storage = DataStorage(tmp_path / "market.db")
    monkeypatch.setattr(data_manager_mod.time, "sleep", lambda *_args, **_kwargs: None, raising=True)

    class FullInitFetcher:
        def __init__(self):
            self.after_calls = []

        def get_candles(self, inst_id, timeframe, limit=300, after=None, before=None):
            self.after_calls.append(after)
            if after is None:
                return [_candle(3 * HOUR_MS, 103), _candle(4 * HOUR_MS, 104)]
            if after == 3 * HOUR_MS:
                return [_candle(1 * HOUR_MS, 101), _candle(2 * HOUR_MS, 102)]
            if after == 1 * HOUR_MS:
                return []
            raise AssertionError(f"unexpected pagination cursor: {after}")

        def get_history_candles(self, *args, **kwargs):
            raise AssertionError("首次缺失数据应直接走全量初始化，而不是窗口/增量接口")

    manager = DataManager(storage, FullInitFetcher())

    candles = manager.get_candles_with_sync("BTC-USDT", "1H", count=4)

    assert len(candles) == 4
    assert candles[0].timestamp == 1 * HOUR_MS
    assert candles[-1].timestamp == 4 * HOUR_MS

    record = storage.get_sync_record("BTC-USDT", "1H")
    assert record is not None
    assert record["history_complete"] is True
    assert record["last_sync_mode"] == "full"


def test_get_local_candles_backfills_when_requested_history_exceeds_local_range(tmp_path, monkeypatch):
    storage = DataStorage(tmp_path / "market.db")
    storage.save_candles(
        "BTC-USDT",
        "1H",
        [_candle(3 * HOUR_MS, 103), _candle(4 * HOUR_MS, 104)],
    )
    storage.update_sync_record(
        "BTC-USDT",
        "1H",
        history_complete=False,
        last_sync_mode="window",
    )
    monkeypatch.setattr(data_manager_mod.time, "sleep", lambda *_args, **_kwargs: None, raising=True)

    class BackfillFetcher:
        def __init__(self):
            self.after_calls = []
            self.incremental_called = False

        def get_history_candles(self, *args, **kwargs):
            self.incremental_called = True
            return []

        def get_candles(self, inst_id, timeframe, limit=300, after=None, before=None):
            self.after_calls.append(after)
            if after == 3 * HOUR_MS:
                return [_candle(1 * HOUR_MS, 101), _candle(2 * HOUR_MS, 102)]
            if after == 1 * HOUR_MS:
                return []
            raise AssertionError(f"unexpected pagination cursor: {after}")

    manager = DataManager(storage, BackfillFetcher())

    candles = manager.get_local_candles(
        "BTC-USDT",
        "1H",
        limit=4,
        start_time=datetime.fromtimestamp(1 * HOUR_MS / 1000, tz=timezone.utc),
        end_time=datetime.fromtimestamp(4 * HOUR_MS / 1000, tz=timezone.utc),
    )

    assert len(candles) == 4
    assert candles[0].timestamp == 1 * HOUR_MS

    record = storage.get_sync_record("BTC-USDT", "1H")
    assert record is not None
    assert record["history_complete"] is True
    assert record["last_sync_mode"] == "full"
