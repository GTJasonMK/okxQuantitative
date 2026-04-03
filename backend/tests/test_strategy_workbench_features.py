import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException


@pytest.fixture(autouse=True)
def _avoid_asyncio_default_executor_hang(monkeypatch):
    async def _to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", _to_thread, raising=True)


def _external_strategy_source() -> str:
    return """
from typing import Dict, List

from pydantic import BaseModel, Field

from app.strategies.base import BaseStrategy, Signal, SignalType, StrategyConfig


class DemoExternalParams(BaseModel):
    fast_period: int = Field(default=5, ge=2, le=60)


class DemoExternalStrategy(BaseStrategy):
    strategy_id = "demo_external"
    strategy_name = "DemoExternal"
    strategy_description = "demo"
    params_schema = DemoExternalParams

    @classmethod
    def create_instance(
        cls,
        symbol: str = "BTC-USDT",
        timeframe: str = "1H",
        initial_capital: float = 10000,
        position_size: float = 0.1,
        stop_loss: float = 0.05,
        take_profit: float = 0.1,
        inst_type: str = "SPOT",
        **strategy_params,
    ):
        config = StrategyConfig(
            name=cls.strategy_name,
            symbol=symbol,
            timeframe=timeframe,
            inst_type=inst_type,
            initial_capital=initial_capital,
            position_size=position_size,
            stop_loss=stop_loss,
            take_profit=take_profit,
            params=strategy_params,
        )
        return cls(config)

    def calculate_indicators(self, candles: List) -> Dict[str, List[float]]:
        return {"close": [float(item.close) for item in candles]}

    def generate_signal(self, index: int):
        return Signal(
            type=SignalType.HOLD,
            price=float(self._candles[index].close) if self._candles else 0.0,
            timestamp=self._candles[index].timestamp if self._candles else 0,
            reason="hold",
        )
"""


@pytest.mark.asyncio
async def test_external_strategy_file_api_round_trip(tmp_path: Path):
    import app.api.backtest as backtest_mod
    import app.strategies.registry as registry_mod

    old_dir = backtest_mod.config.strategy.external_dir
    old_registry_dir = registry_mod._external_strategy_dir
    old_external_modules = registry_mod._external_modules.copy()

    try:
        backtest_mod.config.strategy.external_dir = tmp_path
        registry_mod._external_strategy_dir = None
        registry_mod._external_modules.clear()

        save_resp = await backtest_mod.save_external_strategy_file(
            backtest_mod.ExternalStrategyFileRequest(
                filename="demo_external.py",
                source=_external_strategy_source(),
            )
        )

        assert save_resp["code"] == 0
        assert (tmp_path / "demo_external.py").exists()
        assert "demo_external" in save_resp["data"]["strategy_ids"]

        list_resp = await backtest_mod.list_external_strategy_files()
        assert list_resp["code"] == 0
        assert list_resp["data"]["files"][0]["filename"] == "demo_external.py"
        assert list_resp["data"]["files"][0]["strategy_ids"] == ["demo_external"]

        file_resp = await backtest_mod.get_external_strategy_file("demo_external.py")
        assert file_resp["data"]["filename"] == "demo_external.py"
        assert "DemoExternalStrategy" in file_resp["data"]["source"]
        assert file_resp["data"]["strategy_ids"] == ["demo_external"]

        delete_resp = await backtest_mod.delete_external_strategy_file("demo_external.py")
        assert delete_resp["code"] == 0
        assert not (tmp_path / "demo_external.py").exists()
    finally:
        for module_name in list(registry_mod._external_modules.values()):
            sys.modules.pop(module_name, None)
        registry_mod._external_modules.clear()
        registry_mod._external_modules.update(old_external_modules)
        registry_mod._external_strategy_dir = old_registry_dir
        backtest_mod.config.strategy.external_dir = old_dir


def test_build_risk_summary_combines_spot_and_contract_exposure():
    from app.core.risk_control import build_risk_summary

    class DummyAccount:
        is_available = True

        def get_balance(self, ccy: str = ""):
            return {
                "totalEq": "1500",
                "details": [
                    {"ccy": "BTC", "availBal": "0.5", "frozenBal": "0"},
                    {"ccy": "USDT", "availBal": "200", "frozenBal": "0"},
                ],
            }

        def get_contract_positions(self, inst_type: str = "SWAP", inst_id: str = ""):
            if inst_type == "SWAP":
                return [{"pos": "2", "notionalUsd": "300", "upl": "15"}]
            return []

    class DummyFetcher:
        def get_tickers_cached(self, inst_type: str = "SPOT"):
            return {"BTC-USDT": SimpleNamespace(last=1000)}

        def get_ticker_cached(self, inst_id: str):
            return SimpleNamespace(last=1000)

    summary = build_risk_summary(account=DummyAccount(), fetcher=DummyFetcher())

    assert summary["available_cash"] == 200
    assert summary["spot_exposure"] == 500
    assert summary["contract_exposure"] == 300
    assert summary["total_exposure"] == 800
    assert summary["floating_pnl"] == 15
    assert summary["exposure_ratio"] == pytest.approx(800 / 1500, rel=1e-6)


@pytest.mark.asyncio
async def test_place_order_blocks_when_risk_control_rejects(monkeypatch):
    import app.api.trading as trading_mod

    class DummyTrader:
        is_available = True

        def place_order(self, *args, **kwargs):  # pragma: no cover
            raise AssertionError("风控拒绝时不应触发真实下单")

    class DummyAccount:
        is_available = True

    monkeypatch.setattr(trading_mod, "get_trader", lambda mode: DummyTrader())
    monkeypatch.setattr(trading_mod, "get_account", lambda mode: DummyAccount())
    monkeypatch.setattr(trading_mod, "get_fetcher", lambda: None)
    monkeypatch.setattr(
        trading_mod,
        "evaluate_order_risk",
        lambda **kwargs: {"allowed": False, "message": "总风险敞口预计为 120.00% ，超过上限 80.00%"},
    )

    old = trading_mod.config.okx.use_simulated
    trading_mod.config.okx.use_simulated = True
    try:
        with pytest.raises(HTTPException) as exc:
            await trading_mod.place_order(
                trading_mod.PlaceOrderRequest(
                    inst_id="BTC-USDT",
                    side="buy",
                    order_type="market",
                    size="1",
                    mode="simulated",
                )
            )

        assert "风控拒绝下单" in str(exc.value.detail)
    finally:
        trading_mod.config.okx.use_simulated = old
