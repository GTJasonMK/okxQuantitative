from dataclasses import dataclass
from datetime import datetime

import app.agent.queries as agent_queries
from app.agent.queries import AgentQueryService
from app.agent.schemas import (
    AgentAlignmentQueryRequest,
    AgentCandleQueryRequest,
    AgentCorrelationQueryRequest,
    AgentDataHealthQueryRequest,
    AgentIndicatorQueryRequest,
    AgentLevelSnapshotListRequest,
    AgentLevelSnapshotRequest,
    AgentMarketStructureRequest,
    AgentMarketQueryRequest,
    AgentOpportunityPatrolRequest,
    AgentOrderBookQueryRequest,
    AgentOrderDraftConfirmRequest,
    AgentOrderDraftListRequest,
    AgentOrderDraftRequest,
    AgentPatrolRunListRequest,
    AgentPositionQueryRequest,
    AgentPriceProjectionRequest,
    AgentPythonAnalysisRequest,
    AgentRiskBudgetRequest,
    AgentRecentTradesQueryRequest,
    AgentSupportResistanceRequest,
    AgentTradeSetupRequest,
    AgentTradingContextRequest,
    AgentWatchlistScanRequest,
)
from app.core.data_storage import DataStorage


@dataclass
class FakeCandle:
    timestamp: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    volume_ccy: float = 0.0

    @property
    def datetime(self):
        return datetime.fromtimestamp(self.timestamp / 1000)


class FakeTicker:
    def __init__(self, inst_id: str = "BTC-USDT", last: float = 123.0, open_24h: float = 120.0, vol_24h: float = 999.0):
        self.inst_id = inst_id
        self.last = last
        self.last_sz = 0.5
        self.ask_px = last + 0.2
        self.bid_px = last - 0.2
        self.open_24h = open_24h
        self.high_24h = max(last + 2.0, open_24h + 2.0)
        self.low_24h = min(last - 2.0, open_24h - 2.0)
        self.vol_24h = vol_24h
        self.timestamp = 1704067200000

    @property
    def change_24h(self):
        return (self.last - self.open_24h) / self.open_24h * 100

    def to_dict(self):
        return {
            "inst_id": self.inst_id,
            "last": self.last,
            "last_sz": self.last_sz,
            "ask_px": self.ask_px,
            "bid_px": self.bid_px,
            "open_24h": self.open_24h,
            "high_24h": self.high_24h,
            "low_24h": self.low_24h,
            "vol_24h": self.vol_24h,
            "change_24h": self.change_24h,
            "timestamp": self.timestamp,
        }


class FakeTrade:
    def __init__(self, price: float, size: float, side: str, inst_id: str = "BTC-USDT"):
        self.inst_id = inst_id
        self.trade_id = f"{price}-{size}-{side}"
        self.price = price
        self.size = size
        self.side = side
        self.timestamp = 1704067200000

    def to_dict(self):
        return {
            "inst_id": self.inst_id,
            "trade_id": self.trade_id,
            "price": self.price,
            "size": self.size,
            "side": self.side,
            "timestamp": self.timestamp,
        }


class FakeManager:
    def get_local_candles(self, inst_id, timeframe, limit=100, start_time=None, end_time=None, auto_sync=True, inst_type="SPOT"):
        symbol_bias = 20.0 if "ETH" in inst_id else 100.0
        timeframe_bias = 10.0 if timeframe == "5m" else 0.0
        base = symbol_bias + timeframe_bias
        return [
            FakeCandle(timestamp=1704067200000 + index * 3600000, open=base + index, high=base + index + 1, low=base + index - 1, close=base + index + 0.5, volume=10 + index)
            for index in range(30)
        ][:limit]


class FakeFetcher:
    def get_ticker_cached(self, inst_id, inst_type=None):
        if "ETH" in inst_id:
            return FakeTicker(inst_id=inst_id, last=88.0, open_24h=92.0, vol_24h=666.0)
        if "SWAP" in inst_id:
            return FakeTicker(inst_id=inst_id, last=223.0, open_24h=217.0, vol_24h=1500.0)
        return FakeTicker(inst_id=inst_id)

    def get_tickers_cached(self, inst_type="SPOT"):
        if inst_type == "SWAP":
            return {
                "BTC-USDT-SWAP": FakeTicker(inst_id="BTC-USDT-SWAP", last=223.0, open_24h=217.0, vol_24h=1500.0),
                "ETH-USDT-SWAP": FakeTicker(inst_id="ETH-USDT-SWAP", last=188.0, open_24h=194.0, vol_24h=1111.0),
            }
        return {
            "BTC-USDT": FakeTicker(inst_id="BTC-USDT", last=123.0, open_24h=120.0, vol_24h=999.0),
            "ETH-USDT": FakeTicker(inst_id="ETH-USDT", last=88.0, open_24h=92.0, vol_24h=666.0),
        }

    def get_orderbook(self, inst_id, size=20):
        return {
            "inst_id": inst_id,
            "bids": [{"price": 122.8, "size": 5.0, "total": 5.0, "order_count": 2}],
            "asks": [{"price": 123.2, "size": 6.0, "total": 6.0, "order_count": 1}],
            "best_bid": 122.8,
            "best_ask": 123.2,
            "spread": 0.4,
            "timestamp": 1704067200000,
        }

    def get_recent_trades_local_first(self, inst_id, limit=50, inst_type="SPOT"):
        base = 123.0 if "BTC" in inst_id else 88.0
        return [
            FakeTrade(base, 1.2, "buy", inst_id=inst_id),
            FakeTrade(base - 0.5, 0.7, "sell", inst_id=inst_id),
        ][:limit]


class FakeStorage:
    def get_latest_ticker(self, inst_id, inst_type="SPOT", max_age_ms=None):
        return FakeFetcher().get_ticker_cached(inst_id, inst_type)

    def get_recent_trades(self, inst_id, limit=50, inst_type="SPOT", max_age_ms=None):
        return FakeFetcher().get_recent_trades_local_first(inst_id, limit, inst_type=inst_type)

    def get_cost_basis(self, mode):
        return {
            "BTC": {
                "avg_cost": 100.0,
                "total_cost": 110.0,
                "total_fee": 1.5,
            },
            "ETH": {
                "avg_cost": 80.0,
                "total_cost": 160.0,
                "total_fee": 1.1,
            }
        }

    def get_symbol_data_inventory(self):
        return [
            {
                "symbol": "BTC-USDT",
                "candle_count": 60,
                "timeframe_record_count": 2,
                "storage_counts": {
                    "candles": 60,
                    "sync_records": 2,
                    "market_ticker_snapshots": 1,
                    "market_recent_trades": 2,
                    "local_fills": 0,
                    "live_order_records": 0,
                    "backtest_results": 0,
                    "cost_basis": 1,
                    "total": 66,
                },
                "markets": {
                    "SPOT": {
                        "inst_id": "BTC-USDT",
                        "inst_type": "SPOT",
                        "timeframe_count": 2,
                        "candle_count": 60,
                        "history_complete_count": 1,
                        "oldest_time": "2024-01-01T00:00:00+00:00",
                        "newest_time": "2024-01-10T00:00:00+00:00",
                        "last_sync_time": "2024-01-10T00:05:00+00:00",
                        "timeframes": [
                            {
                                "timeframe": "1H",
                                "candle_count": 30,
                                "history_complete": True,
                                "last_sync_mode": "full",
                                "last_sync_time": "2024-01-10T00:05:00+00:00",
                                "oldest_time": "2024-01-01T00:00:00+00:00",
                                "newest_time": "2024-01-10T00:00:00+00:00",
                            },
                            {
                                "timeframe": "4H",
                                "candle_count": 30,
                                "history_complete": False,
                                "last_sync_mode": "incremental",
                                "last_sync_time": "2024-01-10T00:10:00+00:00",
                                "oldest_time": "2024-01-03T00:00:00+00:00",
                                "newest_time": "2024-01-10T00:00:00+00:00",
                            },
                        ],
                    },
                },
            },
            {
                "symbol": "ETH-USDT",
                "candle_count": 30,
                "timeframe_record_count": 1,
                "storage_counts": {
                    "candles": 30,
                    "sync_records": 1,
                    "market_ticker_snapshots": 1,
                    "market_recent_trades": 2,
                    "local_fills": 0,
                    "live_order_records": 0,
                    "backtest_results": 0,
                    "cost_basis": 1,
                    "total": 35,
                },
                "markets": {
                    "SPOT": {
                        "inst_id": "ETH-USDT",
                        "inst_type": "SPOT",
                        "timeframe_count": 1,
                        "candle_count": 30,
                        "history_complete_count": 0,
                        "oldest_time": "2024-01-05T00:00:00+00:00",
                        "newest_time": "2024-01-10T00:00:00+00:00",
                        "last_sync_time": "2024-01-10T00:05:00+00:00",
                        "timeframes": [
                            {
                                "timeframe": "1H",
                                "candle_count": 30,
                                "history_complete": False,
                                "last_sync_mode": "window",
                                "last_sync_time": "2024-01-10T00:05:00+00:00",
                                "oldest_time": "2024-01-05T00:00:00+00:00",
                                "newest_time": "2024-01-10T00:00:00+00:00",
                            },
                        ],
                    },
                },
            },
        ]


class FakeAccount:
    is_available = True

    def get_balance(self):
        return {
            "totalEq": "1500",
            "details": [
                {
                    "ccy": "BTC",
                    "availBal": "1.0",
                    "frozenBal": "0.1",
                },
                {
                    "ccy": "ETH",
                    "availBal": "2.0",
                    "frozenBal": "0.0",
                },
                {
                    "ccy": "USDT",
                    "availBal": "500",
                    "frozenBal": "0",
                }
            ]
        }

    def get_contract_positions(self, inst_type="SWAP", inst_id=""):
        return [{"pos": "2", "notionalUsd": "300", "upl": "15"}]


class FakeCtx:
    def manager(self):
        return FakeManager()

    def fetcher(self):
        return FakeFetcher()

    def storage(self):
        return FakeStorage()

    def account(self, mode):
        return FakeAccount()

    def default_mode(self):
        return "simulated"


class StrictSwapManager:
    def __init__(self):
        self.calls = []

    def get_local_candles(self, inst_id, timeframe, limit=100, start_time=None, end_time=None, auto_sync=True, inst_type="SPOT"):
        self.calls.append({
            "inst_id": inst_id,
            "timeframe": timeframe,
            "limit": limit,
            "inst_type": inst_type,
        })
        if inst_id != "RAVE-USDT-SWAP" or inst_type != "SWAP":
            return []
        return FakeManager().get_local_candles(
            inst_id,
            timeframe,
            limit=limit,
            start_time=start_time,
            end_time=end_time,
            auto_sync=auto_sync,
            inst_type=inst_type,
        )


class StrictSwapFetcher:
    def __init__(self):
        self.ticker_calls = []
        self.orderbook_calls = []
        self.trade_calls = []

    def get_ticker_cached(self, inst_id, inst_type=None):
        self.ticker_calls.append((inst_id, inst_type))
        if inst_id != "RAVE-USDT-SWAP" or inst_type != "SWAP":
            return None
        return FakeTicker(inst_id=inst_id, last=66.0, open_24h=61.0, vol_24h=777.0)

    def get_orderbook(self, inst_id, size=20):
        self.orderbook_calls.append((inst_id, size))
        if inst_id != "RAVE-USDT-SWAP":
            raise ValueError(f"unexpected inst_id: {inst_id}")
        return {
            "inst_id": inst_id,
            "bids": [{"price": 65.8, "size": 5.0, "total": 5.0, "order_count": 2}],
            "asks": [{"price": 66.2, "size": 6.0, "total": 6.0, "order_count": 1}],
            "best_bid": 65.8,
            "best_ask": 66.2,
            "spread": 0.4,
            "timestamp": 1704067200000,
        }

    def get_recent_trades_local_first(self, inst_id, limit=50, inst_type="SPOT"):
        self.trade_calls.append((inst_id, limit, inst_type))
        if inst_id != "RAVE-USDT-SWAP" or inst_type != "SWAP":
            return []
        return [
            FakeTrade(66.0, 1.2, "buy", inst_id=inst_id),
            FakeTrade(65.5, 0.7, "sell", inst_id=inst_id),
        ][:limit]


class StrictSwapStorage:
    def __init__(self):
        self.ticker_calls = []
        self.trade_calls = []

    def get_latest_ticker(self, inst_id, inst_type="SPOT", max_age_ms=None):
        self.ticker_calls.append((inst_id, inst_type))
        if inst_id != "RAVE-USDT-SWAP" or inst_type != "SWAP":
            return None
        return FakeTicker(inst_id=inst_id, last=66.0, open_24h=61.0, vol_24h=777.0)

    def get_recent_trades(self, inst_id, limit=50, inst_type="SPOT", max_age_ms=None):
        self.trade_calls.append((inst_id, limit, inst_type))
        if inst_id != "RAVE-USDT-SWAP" or inst_type != "SWAP":
            return []
        return [
            FakeTrade(66.0, 1.2, "buy", inst_id=inst_id),
            FakeTrade(65.5, 0.7, "sell", inst_id=inst_id),
        ][:limit]

    def get_cost_basis(self, mode):
        return {}

    def get_symbol_data_inventory(self):
        return []


class StrictSwapCtx:
    def __init__(self):
        self.manager_instance = StrictSwapManager()
        self.fetcher_instance = StrictSwapFetcher()
        self.storage_instance = StrictSwapStorage()

    def manager(self):
        return self.manager_instance

    def fetcher(self):
        return self.fetcher_instance

    def storage(self):
        return self.storage_instance

    def account(self, mode):
        return FakeAccount()

    def default_mode(self):
        return "simulated"


class FakeGuardian:
    def get_status(self):
        return {
            "enabled": True,
            "running": True,
            "current_phase": "syncing",
            "watched_count": 2,
            "timeframes": ["1H", "4H", "1D"],
            "last_run_started_at": "2024-01-10T00:00:00+00:00",
            "last_run_finished_at": "2024-01-10T00:10:00+00:00",
            "last_successful_run_at": "2024-01-10T00:10:00+00:00",
            "last_run_summary": {"success_count": 2, "error_count": 0, "total_units": 4},
            "last_errors": [],
        }


def test_agent_query_service_returns_market_snapshot():
    service = AgentQueryService(FakeCtx())

    result = service.get_market_snapshot(AgentMarketQueryRequest(inst_id="BTC-USDT", inst_type="SPOT"))

    assert result["inst_id"] == "BTC-USDT"
    assert result["ticker"]["last"] == 123.0
    assert result["price_summary"]["spread_bps"] > 0


def test_agent_query_service_resolves_swap_market_snapshot_inst_id():
    service = AgentQueryService(StrictSwapCtx())

    result = service.get_market_snapshot(AgentMarketQueryRequest(inst_id="RAVE-USDT", inst_type="SWAP"))

    assert result["inst_id"] == "RAVE-USDT-SWAP"
    assert result["ticker"]["inst_id"] == "RAVE-USDT-SWAP"
    assert service.ctx.fetcher_instance.ticker_calls == [("RAVE-USDT-SWAP", "SWAP")]


def test_agent_query_service_returns_multi_timeframe_candles_and_indicators():
    service = AgentQueryService(FakeCtx())

    candles = service.get_multi_timeframe_candles(
        AgentCandleQueryRequest(inst_id="BTC-USDT", inst_type="SPOT", timeframes=["1h", "5m"], limit=20)
    )
    indicators = service.get_indicator_snapshot(
        AgentIndicatorQueryRequest(inst_id="BTC-USDT", inst_type="SPOT", timeframe="1h", indicators=["ma5", "macd"], limit=20)
    )

    assert set(candles["timeframes"].keys()) == {"1H", "5m"}
    assert candles["timeframes"]["1H"]["count"] == 20
    assert indicators["indicator_snapshots"]["ma5"]["latest"] is not None
    assert "dif" in indicators["indicator_snapshots"]["macd"]["latest"]


def test_agent_query_service_supports_indicator_aliases():
    service = AgentQueryService(FakeCtx())

    indicators = service.get_indicator_snapshot(
        AgentIndicatorQueryRequest(
            inst_id="BTC-USDT",
            inst_type="SPOT",
            timeframe="1h",
            indicators=["VMA5", "BOLL"],
            limit=20,
        )
    )

    assert indicators["indicator_snapshots"]["VMA5"]["latest"] is not None
    assert "upper" in indicators["indicator_snapshots"]["BOLL"]["latest"]


def test_agent_query_service_supports_vwap_in_trading_context():
    service = AgentQueryService(FakeCtx())

    context = service.get_trading_context(
        AgentTradingContextRequest(
            inst_id="BTC-USDT",
            inst_type="SPOT",
            timeframes=["1h"],
            indicators=["VWAP"],
            include_orderbook=False,
            include_recent_trades=False,
            include_position=False,
        )
    )

    snapshot = context["timeframes"]["1H"]["indicator_snapshots"]["VWAP"]

    assert snapshot["latest"] is not None
    assert snapshot["params"]["mode"] == "cumulative"
    assert snapshot["params"]["source"] == "hlc3"


def test_agent_query_service_returns_orderbook_trades_position_and_analysis_dataset():
    service = AgentQueryService(FakeCtx())

    orderbook = service.get_orderbook_snapshot(
        AgentOrderBookQueryRequest(inst_id="BTC-USDT", inst_type="SPOT", depth=20)
    )
    trades = service.get_recent_trades_snapshot(
        AgentRecentTradesQueryRequest(inst_id="BTC-USDT", inst_type="SPOT", limit=20)
    )
    position = service.get_position_snapshot(AgentPositionQueryRequest(mode="simulated"))
    dataset = service.build_analysis_dataset(
        AgentPythonAnalysisRequest(
            inst_id="BTC-USDT",
            inst_type="SPOT",
            timeframes=["1h", "4h"],
            candles_limit=30,
            indicators=["ma5", "rsi"],
            include_market_snapshot=True,
            include_orderbook=True,
            include_recent_trades=True,
            include_position=True,
            code="""
def analyze(data, helpers):
    return {"summary": "noop"}
""",
        )
    )

    assert orderbook["available"] is True
    assert trades["summary"]["trade_count"] == 2
    assert position["available"] is True
    assert "market_snapshot" in dataset
    assert "orderbook" in dataset
    assert "recent_trades" in dataset
    assert "position" in dataset
    assert set(dataset["candles"].keys()) == {"1H", "4H"}
    assert set(dataset["indicators"].keys()) == {"1H", "4H"}


def test_agent_query_service_builds_trading_context_and_alignment(monkeypatch):
    monkeypatch.setattr(agent_queries, "load_watched_symbols", lambda: [{"symbol": "BTC-USDT"}, {"symbol": "ETH-USDT"}], raising=True)
    monkeypatch.setattr(agent_queries, "get_data_guardian", lambda ctx=None: FakeGuardian(), raising=True)
    service = AgentQueryService(FakeCtx())

    context = service.get_trading_context(
        AgentTradingContextRequest(
            inst_id="BTC-USDT",
            inst_type="SPOT",
            timeframes=["5m", "1h", "4h"],
            include_position=True,
        )
    )
    alignment = service.analyze_multi_timeframe_alignment(
        AgentAlignmentQueryRequest(
            inst_id="BTC-USDT",
            inst_type="SPOT",
            timeframes=["1h", "4h"],
            limit=20,
        )
    )

    assert context["market_snapshot"]["price_summary"]["last"] == 123.0
    assert set(context["timeframes"].keys()) == {"5m", "1H", "4H"}
    assert context["data_health"]["symbol"] == "BTC-USDT"
    assert context["position"]["summary"]["holding_count"] >= 1
    assert alignment["alignment"] in {"bullish", "mixed", "neutral"}
    assert set(alignment["timeframe_signals"].keys()) == {"1H", "4H"}


def test_agent_query_service_resolves_swap_inst_id_across_trading_context():
    service = AgentQueryService(StrictSwapCtx())

    context = service.get_trading_context(
        AgentTradingContextRequest(
            inst_id="RAVE-USDT",
            inst_type="SWAP",
            timeframes=["1h", "4h"],
            candles_limit=20,
            indicators=["ma5", "VWAP"],
            include_orderbook=True,
            include_recent_trades=True,
            include_position=False,
        )
    )

    assert context["inst_id"] == "RAVE-USDT-SWAP"
    assert context["market_snapshot"]["inst_id"] == "RAVE-USDT-SWAP"
    assert context["orderbook"]["available"] is True
    assert context["orderbook"]["inst_id"] == "RAVE-USDT-SWAP"
    assert context["recent_trades"]["summary"]["trade_count"] == 2
    assert context["recent_trades"]["inst_id"] == "RAVE-USDT-SWAP"
    assert context["timeframes"]["1H"]["count"] == 20
    assert context["timeframes"]["1H"]["indicator_snapshots"]["VWAP"]["latest"] is not None
    assert context["alignment"]["inst_id"] == "RAVE-USDT-SWAP"
    assert all(call["inst_id"] == "RAVE-USDT-SWAP" for call in service.ctx.manager_instance.calls)
    assert all(inst_id == "RAVE-USDT-SWAP" for inst_id, _ in service.ctx.fetcher_instance.ticker_calls)
    assert all(inst_id == "RAVE-USDT-SWAP" for inst_id, _ in service.ctx.fetcher_instance.orderbook_calls)
    assert all(inst_id == "RAVE-USDT-SWAP" for inst_id, _, _ in service.ctx.fetcher_instance.trade_calls)


def test_agent_query_service_scans_watchlist_and_returns_data_health(monkeypatch):
    monkeypatch.setattr(
        agent_queries,
        "load_watched_symbols",
        lambda: [
            {"symbol": "BTC-USDT", "spot_inst_id": "BTC-USDT", "swap_inst_id": "BTC-USDT-SWAP", "sync_spot": True, "sync_swap": True},
            {"symbol": "ETH-USDT", "spot_inst_id": "ETH-USDT", "swap_inst_id": "ETH-USDT-SWAP", "sync_spot": True, "sync_swap": False},
        ],
        raising=True,
    )
    monkeypatch.setattr(agent_queries, "get_data_guardian", lambda ctx=None: FakeGuardian(), raising=True)
    service = AgentQueryService(FakeCtx())

    scan = service.scan_watchlist_context(
        AgentWatchlistScanRequest(inst_type="SPOT", timeframes=["1h", "4h"], limit=10)
    )
    health = service.get_data_health(AgentDataHealthQueryRequest(symbol="BTC-USDT"))

    assert scan["summary"]["scan_count"] == 2
    assert scan["rows"][0]["symbol"] in {"BTC-USDT", "ETH-USDT"}
    assert "signal_score" in scan["rows"][0]
    assert health["rows"][0]["symbol"] == "BTC-USDT"
    assert health["summary"]["enabled_timeframes"] == ["1H", "4H", "1D"]


def test_agent_query_service_scan_watchlist_exposes_failures_without_fabricated_rows(monkeypatch):
    monkeypatch.setattr(
        agent_queries,
        "load_watched_symbols",
        lambda: [
            {"symbol": "BTC-USDT", "spot_inst_id": "BTC-USDT", "swap_inst_id": "BTC-USDT-SWAP", "sync_spot": True, "sync_swap": True},
        ],
        raising=True,
    )
    monkeypatch.setattr(agent_queries, "get_data_guardian", lambda ctx=None: FakeGuardian(), raising=True)

    class FailingManager(FakeManager):
        def get_local_candles(self, *args, **kwargs):
            raise RuntimeError("candles unavailable")

    class FailingCtx(FakeCtx):
        def manager(self):
            return FailingManager()

    service = AgentQueryService(FailingCtx())

    scan = service.scan_watchlist_context(
        AgentWatchlistScanRequest(inst_type="SPOT", timeframes=["1h", "4h"], limit=10)
    )

    assert scan["summary"]["scan_count"] == 1
    row = scan["rows"][0]
    assert row["available"] is False
    assert "candles unavailable" in row["error"]
    assert "signal_score" not in row
    assert "ticker" not in row


def test_agent_query_service_builds_market_structure_and_risk_budget(monkeypatch):
    monkeypatch.setattr(agent_queries, "load_watched_symbols", lambda: [{"symbol": "BTC-USDT"}], raising=True)
    monkeypatch.setattr(agent_queries, "get_data_guardian", lambda ctx=None: FakeGuardian(), raising=True)
    service = AgentQueryService(FakeCtx())

    structure = service.analyze_market_structure(
        AgentMarketStructureRequest(inst_id="BTC-USDT", inst_type="SPOT", timeframes=["5m", "1h", "4h"])
    )
    budget = service.build_risk_budget(
        AgentRiskBudgetRequest(
            inst_id="BTC-USDT",
            inst_type="SPOT",
            mode="simulated",
            stop_loss_ratio=0.03,
            proposed_size=1.5,
        )
    )

    assert structure["trend"]["bias"] in {"bullish", "bearish", "neutral"}
    assert "invalidation" in structure["conclusion"]
    assert budget["summary"]["total_equity"] == 1500.0
    assert budget["budget"]["recommended_max_notional"] >= 0
    assert budget["proposed_order_evaluation"]["summary"]["total_equity"] == 1500.0


def test_agent_query_service_detects_levels_projection_and_opportunities(monkeypatch):
    monkeypatch.setattr(
        agent_queries,
        "load_watched_symbols",
        lambda: [
            {"symbol": "BTC-USDT", "spot_inst_id": "BTC-USDT", "swap_inst_id": "BTC-USDT-SWAP", "sync_spot": True, "sync_swap": True},
            {"symbol": "ETH-USDT", "spot_inst_id": "ETH-USDT", "swap_inst_id": "ETH-USDT-SWAP", "sync_spot": True, "sync_swap": False},
        ],
        raising=True,
    )
    monkeypatch.setattr(agent_queries, "get_data_guardian", lambda ctx=None: FakeGuardian(), raising=True)
    service = AgentQueryService(FakeCtx())

    levels = service.detect_support_resistance(
        AgentSupportResistanceRequest(inst_id="BTC-USDT", inst_type="SPOT", timeframes=["1h", "4h"])
    )
    projection = service.generate_price_projection(
        AgentPriceProjectionRequest(inst_id="BTC-USDT", inst_type="SPOT", timeframe="1h", horizon_bars=12)
    )
    patrol = service.patrol_market_opportunities(
        AgentOpportunityPatrolRequest(inst_type="SPOT", candidate_limit=3, timeframes=["1h", "4h"])
    )

    assert "supports" in levels
    assert "resistances" in levels
    assert isinstance(levels["chart_annotations"], list)
    assert projection["selected_scenario"] in {"bullish", "base", "bearish"}
    assert projection["chart_annotations"][0]["type"] == "trendline"
    assert patrol["summary"]["candidate_count"] >= 0
    if patrol["candidates"]:
        assert "key_levels" in patrol["candidates"][0]
        assert "setup_status" in patrol["candidates"][0]
        assert "trade_plan" in patrol["candidates"][0]


def test_agent_query_service_keeps_empty_levels_when_no_confirmed_extrema():
    service = AgentQueryService(FakeCtx())

    levels = service.detect_support_resistance(
        AgentSupportResistanceRequest(inst_id="BTC-USDT", inst_type="SPOT", timeframes=["1h", "4h"])
    )

    assert levels["supports"] == []
    assert levels["resistances"] == []
    assert levels["summary"]["nearest_support"] is None
    assert levels["summary"]["nearest_resistance"] is None


def test_agent_query_service_builds_trade_setup_and_watchlist_correlation(monkeypatch):
    monkeypatch.setattr(
        agent_queries,
        "load_watched_symbols",
        lambda: [
            {"symbol": "BTC-USDT", "spot_inst_id": "BTC-USDT", "swap_inst_id": "BTC-USDT-SWAP", "sync_spot": True, "sync_swap": True},
            {"symbol": "ETH-USDT", "spot_inst_id": "ETH-USDT", "swap_inst_id": "ETH-USDT-SWAP", "sync_spot": True, "sync_swap": True},
        ],
        raising=True,
    )
    monkeypatch.setattr(agent_queries, "get_data_guardian", lambda ctx=None: FakeGuardian(), raising=True)
    service = AgentQueryService(FakeCtx())

    setup = service.build_trade_setup(
        AgentTradeSetupRequest(
            inst_id="BTC-USDT",
            inst_type="SPOT",
            mode="simulated",
            structure_timeframes=["15m", "1h", "4h"],
            level_timeframes=["1h", "4h", "1d"],
            projection_timeframe="1h",
        )
    )
    correlation = service.analyze_watchlist_correlation(
        AgentCorrelationQueryRequest(
            inst_type="SPOT",
            timeframe="1h",
            limit=30,
            use_watchlist_if_empty=True,
        )
    )

    assert setup["setup_status"] in {"ready", "watch", "avoid"}
    assert setup["trade_plan"]["side"] in {"buy", "sell", "flat"}
    assert isinstance(setup["chart_annotations"], list)
    assert "budget_status" in setup["summary"]
    assert correlation["summary"]["symbol_count"] == 2
    assert len(correlation["matrix"]) == 2
    assert correlation["portfolio_hint"]["diversification_score"] >= 0


def test_agent_query_service_manages_order_drafts(tmp_path, monkeypatch):
    storage = DataStorage(tmp_path / "market.db")
    session_id = storage.create_assistant_session(
        title="BTC 订单草案",
        kind="agent",
        mode="simulated",
        inst_id="BTC-USDT",
        inst_type="SPOT",
    )

    class DraftCtx:
        def storage(self):
            return storage

        def fetcher(self):
            return FakeFetcher()

        def account(self, mode):
            return FakeAccount()

        def default_mode(self):
            return "simulated"

    service = AgentQueryService(DraftCtx())
    monkeypatch.setattr(
        service,
        "build_trade_setup",
        lambda request: {
            "setup_status": "ready",
            "bias": "bullish",
            "confidence": 0.78,
            "component_scores": {"structure_confidence": 0.82},
            "trade_plan": {
                "side": "buy",
                "entry_reference": 123.4,
                "stop_loss": {"price": 119.7},
                "targets": [
                    {"label": "T1", "price": 129.5, "reward_risk": 1.65},
                    {"label": "T2", "price": 134.0, "reward_risk": 2.88},
                ],
                "risk_budget": {
                    "reference_price": 123.4,
                    "budget": {
                        "status": "available",
                        "suggested_max_size": 2.5,
                    },
                },
            },
            "key_levels": {"supports": [], "resistances": []},
            "projection": {"selected_scenario": "bullish", "projection_summary": {}},
            "checklist": ["等待回踩确认。"],
            "chart_annotations": [{"type": "horizontal", "role": "entry", "price": 123.4}],
            "summary": {"budget_status": "available"},
        },
        raising=True,
    )

    created = service.create_order_draft(
        AgentOrderDraftRequest(
            session_id=session_id,
            inst_id="BTC-USDT",
            inst_type="SPOT",
            mode="simulated",
            side_preference="buy",
            note="单元测试草案",
        )
    )
    listed = service.list_order_drafts(
        AgentOrderDraftListRequest(session_id=session_id, status="draft", limit=10)
    )
    confirmed = service.confirm_order_draft(
        AgentOrderDraftConfirmRequest(draft_id=created["draft_id"])
    )
    detail = service.get_order_draft(created["draft_id"])

    assert created["status"] == "draft"
    assert created["requires_manual_execution"] is True
    assert created["draft"]["metadata"]["requires_confirmation"] is True
    assert listed["count"] == 1
    assert listed["drafts"][0]["draft_id"] == created["draft_id"]
    assert confirmed["status"] == "confirmed"
    assert confirmed["executed"] is False
    assert detail["draft"]["status"] == "confirmed"


def test_agent_query_service_saves_and_lists_level_snapshots(tmp_path, monkeypatch):
    storage = DataStorage(tmp_path / "market.db")
    session_id = storage.create_assistant_session(
        title="关键位会话",
        kind="agent",
        mode="simulated",
        inst_id="BTC-USDT",
        inst_type="SPOT",
    )

    class SnapshotCtx:
        def storage(self):
            return storage

        def default_mode(self):
            return "simulated"

    service = AgentQueryService(SnapshotCtx())
    monkeypatch.setattr(
        service,
        "detect_support_resistance",
        lambda request: {
            "inst_id": request.inst_id,
            "inst_type": "SPOT",
            "current_price": 123.4,
            "supports": [{"price": 120.0, "strength": 3.2, "timeframes": ["1H"]}],
            "resistances": [{"price": 127.8, "strength": 2.8, "timeframes": ["4H"]}],
            "invalidation_levels": [{"kind": "bullish_invalidation", "price": 120.0}],
            "chart_annotations": [{"type": "horizontal", "role": "support", "price": 120.0}],
            "summary": {"nearest_support": 120.0, "nearest_resistance": 127.8},
        },
        raising=True,
    )

    saved = service.save_support_resistance_snapshot(
        AgentLevelSnapshotRequest(
            session_id=session_id,
            inst_id="BTC-USDT",
            inst_type="SPOT",
            source="assistant",
            note="记录当前关键位",
        )
    )
    listed = service.list_level_snapshots(
        AgentLevelSnapshotListRequest(session_id=session_id, inst_id="BTC-USDT", limit=10)
    )
    detail = service.get_level_snapshot(saved["snapshot_id"])

    assert saved["snapshot"]["metadata"]["note"] == "记录当前关键位"
    assert listed["count"] == 1
    assert listed["snapshots"][0]["snapshot_id"] == saved["snapshot_id"]
    assert detail["snapshot"]["supports"][0]["price"] == 120.0


def test_agent_query_service_lists_patrol_runs(tmp_path):
    storage = DataStorage(tmp_path / "market.db")
    run_id = storage.create_assistant_patrol_run(
        trigger="manual",
        inst_type="SWAP",
        mode="simulated",
        summary={"candidate_count": 1},
        candidates=[{"inst_id": "BTC-USDT-SWAP", "priority_score": 88.0}],
        result={"summary": {"candidate_count": 1}},
        event={"id": "event-1"},
        settings={"candidate_limit": 3},
    )

    class PatrolCtx:
        def storage(self):
            return storage

        def default_mode(self):
            return "simulated"

    service = AgentQueryService(PatrolCtx())
    listed = service.list_patrol_runs(
        AgentPatrolRunListRequest(inst_type="SWAP", mode="simulated", trigger="manual", limit=10)
    )
    detail = service.get_patrol_run(run_id)

    assert listed["count"] == 1
    assert listed["runs"][0]["run_id"] == run_id
    assert detail["run"]["candidates"][0]["inst_id"] == "BTC-USDT-SWAP"
