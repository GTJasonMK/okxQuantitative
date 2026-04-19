import pytest

from app.core.data_guardian import (
    MarketDataGuardian,
    WatchTarget,
    build_default_guardian_settings,
    normalize_guardian_settings,
)


class FakeStorage:
    def __init__(self, records=None):
        self.records = records or {}

    def get_sync_record(self, inst_id, timeframe, inst_type="SPOT"):
        return self.records.get((inst_id, timeframe, inst_type))

    def update_sync_record(self, inst_id, timeframe, inst_type="SPOT", **kwargs):
        key = (inst_id, timeframe, inst_type)
        if key not in self.records:
            self.records[key] = {}
        self.records[key].update(kwargs)


class FakeManager:
    def __init__(self):
        self.calls = []

    def _result(self, mode, inst_id, timeframe):
        return {
            "mode": mode,
            "fetched_count": 12,
            "saved_count": 12,
            "batches": 1,
            "api_calls": 1,
            "candle_count": 120,
            "history_complete": mode == "full",
            "last_sync_mode": mode,
            "last_sync_time": "2026-03-27T00:00:00+00:00",
        }

    def sync_candles_window(self, inst_id, timeframe, *, days, inst_type):
        self.calls.append(("window", inst_id, timeframe, days, inst_type))
        return self._result("window", inst_id, timeframe)

    def sync_candles_incremental(self, inst_id, timeframe, *, days, inst_type):
        self.calls.append(("incremental", inst_id, timeframe, days, inst_type))
        return self._result("incremental", inst_id, timeframe)

    def sync_candles_full(self, inst_id, timeframe, *, days, inst_type):
        self.calls.append(("full", inst_id, timeframe, days, inst_type))
        return self._result("full", inst_id, timeframe)


class FakeFetcherWrapper:
    def __init__(self, available=True):
        self.fetcher = object() if available else None


class FakeCtx:
    def __init__(self, storage, manager, *, fetcher_available=True):
        self._storage = storage
        self._manager = manager
        self._fetcher = FakeFetcherWrapper(fetcher_available)

    def storage(self):
        return self._storage

    def manager(self):
        return self._manager

    def fetcher(self):
        return self._fetcher


def build_guardian(storage=None, manager=None, *, fetcher_available=True, settings=None):
    guardian = MarketDataGuardian(
        FakeCtx(storage or FakeStorage(), manager or FakeManager(), fetcher_available=fetcher_available),
    )
    if settings is not None:
        guardian.apply_settings(settings, persist=False)
    return guardian


def build_settings(plan_overrides):
    settings = build_default_guardian_settings()
    overrides_by_timeframe = {item["timeframe"]: item for item in plan_overrides}
    for plan in settings["plans"]:
        override = overrides_by_timeframe.get(plan["timeframe"])
        if override:
            plan.update(override)
        else:
            plan["enabled"] = False
    return settings


def test_normalize_guardian_settings_supports_camel_case_and_defaults():
    defaults = build_default_guardian_settings()
    normalized = normalize_guardian_settings({
        "enabled": False,
        "scanIntervalSeconds": 45,
        "maxFullBackfillJobsPerCycle": 99,
        "plans": [
            {
                "timeframe": "1m",
                "enabled": True,
                "bootstrapDays": 30,
                "archiveMode": "full",
            },
            {
                "timeframe": "5m",
                "enabled": False,
                "bootstrapDays": 7,
                "archiveMode": "rolling",
            },
        ],
    })

    assert normalized["enabled"] is False
    assert normalized["scan_interval_seconds"] == 60
    assert normalized["max_full_backfill_jobs_per_cycle"] == 20
    assert normalized["plans"][0]["timeframe"] == "1m"
    assert normalized["plans"][0]["archive_mode"] == "full"
    assert normalized["plans"][0]["bootstrap_days"] == 30
    assert normalized["plans"][1]["timeframe"] == "5m"
    assert normalized["plans"][1]["enabled"] is False
    assert any(plan["timeframe"] == "1D" for plan in normalized["plans"])
    assert len(normalized["plans"]) == len(defaults["plans"])


def test_build_watch_targets_uses_market_type_and_deduplicates(monkeypatch):
    guardian = build_guardian()
    monkeypatch.setattr(guardian, "_load_watched_symbols", lambda: [])

    targets, inst_type = guardian._build_watch_targets({
        "selectedSymbols": ["doge-usdt", "DOGE-USDT", "sui-usdt-swap"],
        "activeSymbol": "doge-usdt",
        "customSymbols": ["PEPE-USDT", ""],
        "marketInstType": "SWAP",
    })

    assert inst_type == "SWAP"
    assert [target.symbol for target in targets] == ["DOGE-USDT", "SUI-USDT", "PEPE-USDT"]
    assert [target.inst_id for target in targets] == [
        "DOGE-USDT-SWAP",
        "SUI-USDT-SWAP",
        "PEPE-USDT-SWAP",
    ]


def test_build_watch_targets_prefers_watched_symbols_and_builds_spot_swap_pairs():
    guardian = build_guardian()

    targets, inst_type = guardian._build_watch_targets(
        {"selectedSymbols": ["OLD-USDT"], "marketInstType": "SPOT"},
        watched_symbols=[
            {"symbol": "BTC-USDT"},
            {"symbol": "ETH-USDT"},
            {"symbol": "BTC-USDT"},
        ],
    )

    assert inst_type == "MIXED"
    assert [(target.symbol, target.inst_type, target.inst_id) for target in targets] == [
        ("BTC-USDT", "SPOT", "BTC-USDT"),
        ("BTC-USDT", "SWAP", "BTC-USDT-SWAP"),
        ("ETH-USDT", "SPOT", "ETH-USDT"),
        ("ETH-USDT", "SWAP", "ETH-USDT-SWAP"),
    ]


def test_build_watch_targets_respects_watch_sync_preferences():
    guardian = build_guardian()

    targets, inst_type = guardian._build_watch_targets(
        {"selectedSymbols": ["OLD-USDT"], "marketInstType": "SPOT"},
        watched_symbols=[
            {"symbol": "BTC-USDT", "sync_spot": True, "sync_swap": False},
            {"symbol": "ETH-USDT", "sync_spot": False, "sync_swap": True},
        ],
    )

    assert inst_type == "MIXED"
    assert [(target.symbol, target.inst_type, target.inst_id) for target in targets] == [
        ("BTC-USDT", "SPOT", "BTC-USDT"),
        ("ETH-USDT", "SWAP", "ETH-USDT-SWAP"),
    ]


def test_build_watch_targets_returns_empty_when_explicit_watchlist_is_empty():
    guardian = build_guardian()

    targets, inst_type = guardian._build_watch_targets(
        {"selectedSymbols": ["DOGE-USDT"], "marketInstType": "SWAP"},
        watched_symbols=[],
    )

    assert targets == []
    assert inst_type == "MIXED"


def test_build_cycle_actions_uses_backfill_queue_and_defers_excess_full_jobs():
    storage = FakeStorage(records={
        ("DOGE-USDT-SWAP", "1H", "SWAP"): {"candle_count": 320, "history_complete": False},
        ("PEPE-USDT-SWAP", "1H", "SWAP"): {"candle_count": 180, "history_complete": False},
    })
    settings = build_settings([
        {"timeframe": "1H", "enabled": True, "bootstrap_days": 180, "archive_mode": "full"},
    ])
    settings["max_full_backfill_jobs_per_cycle"] = 1
    guardian = build_guardian(
        storage=storage,
        settings=settings,
    )

    watch_targets = [
        WatchTarget(symbol="DOGE-USDT", inst_id="DOGE-USDT-SWAP", inst_type="SWAP"),
        WatchTarget(symbol="PEPE-USDT", inst_id="PEPE-USDT-SWAP", inst_type="SWAP"),
    ]
    actions = guardian._build_cycle_actions(watch_targets)

    # 限流 max=1：仅 1 个 full 被选中执行，另 1 个被跳过（不降级）
    assert len(actions) == 1
    assert actions[0].desired_mode == "full"
    assert actions[0].selected_mode == "full"

    status = guardian.get_status()
    assert status["backfill_queue_size"] == 2
    assert len(status["backfill_queue_preview"]) == 2
    assert sum(1 for item in status["backfill_queue_preview"] if item["selected_this_cycle"]) == 1


@pytest.mark.asyncio
async def test_run_scan_cycle_updates_status_and_dispatches_modes(monkeypatch):
    storage = FakeStorage(records={
        ("DOGE-USDT-SWAP", "1H", "SWAP"): {"candle_count": 320, "history_complete": False},
        ("DOGE-USDT-SWAP", "1m", "SWAP"): {"candle_count": 800, "history_complete": False},
    })
    manager = FakeManager()
    guardian = build_guardian(
        storage=storage,
        manager=manager,
        settings=build_settings([
            {"timeframe": "1D", "enabled": True, "bootstrap_days": 365, "archive_mode": "full"},
            {"timeframe": "1H", "enabled": True, "bootstrap_days": 180, "archive_mode": "full"},
            {"timeframe": "1m", "enabled": True, "bootstrap_days": 3, "archive_mode": "rolling"},
        ]),
    )

    monkeypatch.setattr(
        guardian,
        "reload_settings",
        lambda: guardian.get_settings(),
    )
    monkeypatch.setattr(
        guardian,
        "_load_market_settings",
        lambda: {
            "selectedSymbols": ["DOGE-USDT"],
            "customSymbols": [],
            "marketInstType": "SWAP",
        },
    )
    monkeypatch.setattr(
        guardian,
        "_load_watched_symbols",
        lambda: [{"symbol": "DOGE-USDT"}],
    )

    await guardian._run_scan_cycle()

    assert manager.calls == [
        ("window", "DOGE-USDT", "1m", 3, "SPOT"),
        ("window", "DOGE-USDT", "1H", 180, "SPOT"),
        ("window", "DOGE-USDT", "1D", 365, "SPOT"),
        ("incremental", "DOGE-USDT-SWAP", "1m", 3, "SWAP"),
        ("full", "DOGE-USDT-SWAP", "1H", 180, "SWAP"),
        ("window", "DOGE-USDT-SWAP", "1D", 365, "SWAP"),
    ]

    status = guardian.get_status()
    assert status["watched_symbols"] == ["DOGE-USDT"]
    assert status["watched_instruments"] == ["DOGE-USDT", "DOGE-USDT-SWAP"]
    assert status["watched_count"] == 1
    assert status["last_run_summary"]["success_count"] == 6
    assert status["last_run_summary"]["error_count"] == 0
    assert len(status["last_sync_results"]) == 6
    assert any(item["selected_mode"] == "incremental" for item in status["last_sync_results"])
