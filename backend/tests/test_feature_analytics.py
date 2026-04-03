import asyncio
import math
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.backtest.engine import BacktestResult
from app.core.data_storage import DataStorage
from app.core.price_alerts import PriceAlertStore
from app.strategies.base import OrderSide, Trade


@pytest.fixture(autouse=True)
def _avoid_asyncio_default_executor_hang(monkeypatch):
    async def _to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", _to_thread, raising=True)


def test_price_alert_store_triggers_once_and_disables(tmp_path: Path):
    store = PriceAlertStore(tmp_path / "alerts.json")
    alert = store.create_alert({
        "inst_id": "BTC-USDT",
        "inst_type": "SPOT",
        "alert_type": "price",
        "direction": "above",
        "target_price": 100.0,
        "trigger_once": True,
        "cooldown_seconds": 0,
    })

    triggered = store.evaluate_ticker(
        inst_id="BTC-USDT",
        inst_type="SPOT",
        last_price=101.0,
        change_24h=1.2,
        ticker_ts=1,
    )
    assert len(triggered) == 1
    assert triggered[0]["id"] == alert["id"]

    alerts = store.list_alerts(inst_id="BTC-USDT")
    assert alerts[0]["enabled"] is False

    triggered_again = store.evaluate_ticker(
        inst_id="BTC-USDT",
        inst_type="SPOT",
        last_price=105.0,
        change_24h=2.1,
        ticker_ts=2,
    )
    assert triggered_again == []


def test_data_storage_trade_performance_summary(tmp_path: Path):
    storage = DataStorage(tmp_path / "market.db")

    storage.save_fill("buy-1", "BTC-USDT", "buy", 100.0, 1.0, 1704067200000, "simulated")
    storage.save_fill("sell-1", "BTC-USDT", "sell", 120.0, 0.4, 1704067260000, "simulated")
    storage.save_fill("sell-2", "BTC-USDT", "sell", 90.0, 0.6, 1704153600000, "simulated")

    report = storage.get_trade_performance(mode="simulated", inst_id="BTC-USDT", group_by="day")
    summary = report["summary"]

    assert summary["trade_count"] == 2
    assert summary["winning_trades"] == 1
    assert summary["losing_trades"] == 1
    assert summary["realized_pnl"] == 2.0
    assert summary["win_rate"] == 50.0
    assert summary["profit_factor"] == 1.33
    assert summary["max_drawdown_amount"] == 6.0
    assert summary["max_drawdown_pct"] == 75.0
    assert len(report["periods"]) == 2


def test_backtest_result_to_dict_includes_trade_reason_and_metadata():
    result = BacktestResult(
        strategy_name="TestStrategy",
        symbol="BTC-USDT",
        timeframe="1H",
        start_time="2024-01-01T00:00:00",
        end_time="2024-01-02T00:00:00",
        duration_days=2,
        initial_capital=10000,
        trades=[
            Trade(
                timestamp=1704067200000,
                side=OrderSide.BUY,
                price=101.25,
                quantity=0.5,
                commission=0.05,
                reason="金叉确认买入",
                metadata={
                    "ma_short": 101.1,
                    "ma_long": 100.8,
                    "signal_type": "golden_cross",
                },
            )
        ],
    )

    payload = result.to_dict()

    assert payload["trades"][0]["reason"] == "金叉确认买入"
    assert payload["trades"][0]["metadata"]["signal_type"] == "golden_cross"
    assert payload["trades"][0]["metadata"]["ma_short"] == 101.1


@pytest.mark.asyncio
async def test_backtest_scan_returns_ranked_results(monkeypatch):
    import app.api.backtest as backtest_mod

    class FakeStrategy:
        @classmethod
        def validate_params(cls, params):
            if params["short_period"] >= params["long_period"]:
                raise ValueError("short must be < long")

        @classmethod
        def create_instance(cls, **kwargs):
            return SimpleNamespace(
                name="FakeStrategy",
                strategy_id="fake",
                scan_params={
                    "short_period": kwargs["short_period"],
                    "long_period": kwargs["long_period"],
                },
            )

    class FakeResult:
        def __init__(self, total_return, sharpe_ratio, max_drawdown):
            self._payload = {
                "strategy_name": "FakeStrategy",
                "symbol": "BTC-USDT",
                "timeframe": "1H",
                "start_time": "2024-01-01T00:00:00",
                "end_time": "2024-01-10T00:00:00",
                "duration_days": 10,
                "initial_capital": 10000,
                "final_capital": 10000 * (1 + total_return / 100),
                "total_return": total_return,
                "annual_return": total_return,
                "max_drawdown": max_drawdown,
                "sharpe_ratio": sharpe_ratio,
                "sortino_ratio": sharpe_ratio,
                "calmar_ratio": sharpe_ratio,
                "win_rate": 50,
                "profit_factor": 1.5,
                "total_trades": 10,
                "winning_trades": 5,
                "losing_trades": 5,
                "avg_profit": 10,
                "avg_loss": -8,
                "largest_profit": 20,
                "largest_loss": -15,
                "total_commission": 5,
                "equity_curve": [],
                "trades": [],
            }

        def to_dict(self):
            return self._payload

    class FakeManager:
        def get_candles_with_sync(self, *args, **kwargs):
            return [
                SimpleNamespace(
                    timestamp=i,
                    open=100 + i,
                    high=101 + i,
                    low=99 + i,
                    close=100 + i,
                    volume=10 + i,
                )
                for i in range(30)
            ]

    class FakeStorage:
        def __init__(self):
            self.saved = []

        def save_backtest_result(self, *args, **kwargs):
            self.saved.append({
                "args": args,
                "kwargs": kwargs,
            })
            return 1

    class FakeCtx:
        def __init__(self):
            self._storage = FakeStorage()

        def manager(self):
            return FakeManager()

        def storage(self):
            return self._storage

    def fake_run(self, strategy, candles):
        short_period = strategy.scan_params["short_period"]
        long_period = strategy.scan_params["long_period"]
        total_return = short_period * 10 - long_period
        sharpe_ratio = short_period - long_period / 100
        max_drawdown = long_period - short_period
        return FakeResult(total_return=total_return, sharpe_ratio=sharpe_ratio, max_drawdown=max_drawdown)

    monkeypatch.setattr(backtest_mod, "discover_strategies", lambda: 1)
    monkeypatch.setattr(backtest_mod, "get_strategy", lambda strategy_id: FakeStrategy)
    monkeypatch.setattr(backtest_mod.BacktestEngine, "run", fake_run, raising=True)

    ctx = FakeCtx()
    response = await backtest_mod.scan_strategy_parameters(
        "fake",
        backtest_mod.BacktestScanRequest(
            symbol="BTC-USDT",
            inst_type="SWAP",
            timeframe="1H",
            scan_params={
                "short_period": [5, 7],
                "long_period": [20, 30],
            },
            metric="total_return",
            persist_results=True,
        ),
        ctx=ctx,
    )

    assert response.code == 0
    assert response.data["completed"] == 4
    assert response.data["best_result"]["params"]["short_period"] == 7
    assert response.data["best_result"]["params"]["long_period"] == 20
    assert len(ctx.storage().saved) == 4
    first_saved = ctx.storage().saved[0]["kwargs"]["result_dict"]
    assert first_saved["inst_type"] == "SWAP"
    assert first_saved["strategy_id"] == "fake"
    assert len(first_saved["candles"]) == 30
    assert first_saved["sample_step"] == 1


@pytest.mark.asyncio
async def test_backtest_run_returns_visualization_payload(monkeypatch):
    import app.api.backtest as backtest_mod

    class FakeStrategy:
        name = "FakeStrategy"
        strategy_id = "fake_visual"

        @classmethod
        def validate_params(cls, params):
            return None

        @classmethod
        def create_instance(cls, **kwargs):
            return cls()

        def calculate_indicators(self, candles):
            closes = [float(item.close) for item in candles]
            return {
                "ma_short": closes,
                "histogram": [math.nan, -1.2, 0.5, 1.1],
            }

    class FakeResult:
        def to_dict(self):
            return {
                "strategy_name": "FakeStrategy",
                "symbol": "BTC-USDT",
                "timeframe": "1H",
                "start_time": "2024-01-01T00:00:00",
                "end_time": "2024-01-02T00:00:00",
                "duration_days": 2,
                "initial_capital": 10000,
                "final_capital": 10100,
                "total_return": 1.0,
                "annual_return": 12.0,
                "max_drawdown": 2.5,
                "sharpe_ratio": 1.2,
                "sortino_ratio": 1.4,
                "calmar_ratio": 1.1,
                "win_rate": 50.0,
                "profit_factor": 1.3,
                "total_trades": 2,
                "winning_trades": 1,
                "losing_trades": 1,
                "avg_profit": 20.0,
                "avg_loss": -10.0,
                "largest_profit": 25.0,
                "largest_loss": -15.0,
                "total_commission": 3.0,
                "equity_curve": [],
                "trades": [],
            }

    class FakeManager:
        def get_candles_with_sync(self, *args, **kwargs):
            candles = []
            for index in range(10):
                candles.append(SimpleNamespace(
                    timestamp=1704067200000 + index * 3600000,
                    open=100 + index,
                    high=101 + index,
                    low=99 + index,
                    close=100.5 + index,
                    volume=10 + index,
                ))
            return candles

    class FakeStorage:
        def __init__(self):
            self.saved_result = None

        def save_backtest_result(self, result_dict, strategy_id="", params=None):
            self.saved_result = {
                "result_dict": result_dict,
                "strategy_id": strategy_id,
                "params": params,
            }
            return 1

    class FakeCtx:
        def __init__(self):
            self._storage = FakeStorage()

        def manager(self):
            return FakeManager()

        def storage(self):
            return self._storage

    monkeypatch.setattr(backtest_mod, "discover_strategies", lambda: 1)
    monkeypatch.setattr(backtest_mod, "get_strategy", lambda strategy_id: FakeStrategy)
    monkeypatch.setattr(backtest_mod.BacktestEngine, "run", lambda self, strategy, candles: FakeResult(), raising=True)

    ctx = FakeCtx()
    response = await backtest_mod.backtest_strategy(
        "fake_visual",
        backtest_mod.UnifiedBacktestRequest(
            symbol="BTC-USDT",
            timeframe="1H",
            days=3,
            initial_capital=10000,
            params={},
        ),
        ctx=ctx,
    )

    assert response.code == 0
    assert len(response.data["candles"]) == 10
    assert response.data["indicators"]["ma_short"] == [
        100.5, 101.5, 102.5, 103.5, 104.5,
        105.5, 106.5, 107.5, 108.5, 109.5,
    ]
    assert response.data["indicators"]["histogram"][0] is None
    assert ctx.storage().saved_result["result_dict"]["candles"] == response.data["candles"]


def test_backtest_storage_persists_inst_type_and_visualization_detail(tmp_path: Path):
    storage = DataStorage(tmp_path / "market.db")

    result_id = storage.save_backtest_result(
        {
            "strategy_name": "Demo Strategy",
            "symbol": "BTC-USDT-SWAP",
            "inst_type": "SWAP",
            "timeframe": "1H",
            "duration_days": 15,
            "initial_capital": 10000,
            "final_capital": 11200,
            "candles": [
                {
                    "timestamp": 1704067200000,
                    "open": 100.0,
                    "high": 101.0,
                    "low": 99.0,
                    "close": 100.5,
                    "volume": 12.0,
                }
            ],
            "indicators": {
                "ma5": [100.5],
            },
            "sample_step": 1,
        },
        strategy_id="demo_strategy",
        params={"window": 5},
    )

    history_rows = storage.get_backtest_results(limit=5, symbol="BTC-USDT-SWAP")
    detail = storage.get_backtest_result_detail(result_id)

    assert history_rows[0]["inst_type"] == "SWAP"
    assert detail["inst_type"] == "SWAP"
    assert detail["candles"][0]["timestamp"] == 1704067200000
    assert detail["indicators"]["ma5"] == [100.5]


@pytest.mark.asyncio
async def test_market_correlation_returns_perfect_positive_matrix():
    import app.api.market as market_mod

    class FakeManager:
        def get_candles_with_sync(self, inst_id, timeframe, count, auto_sync, inst_type="SPOT"):
            base = 100 if inst_id == "BTC-USDT" else 200
            return [
                SimpleNamespace(timestamp=i, close=base + i * (1 if inst_id == "BTC-USDT" else 2))
                for i in range(30)
            ]

    response = await market_mod.analyze_market_correlation(
        market_mod.CorrelationRequest(
            symbols=["BTC-USDT", "ETH-USDT"],
            timeframe="1H",
            days=5,
            limit=30,
            inst_type="SPOT",
        ),
        manager=FakeManager(),
    )

    assert response.code == 0
    assert response.data["symbols"] == ["BTC-USDT", "ETH-USDT"]
    assert response.data["matrix"][0][1] == 1.0
    assert response.data["matrix"][1][0] == 1.0
