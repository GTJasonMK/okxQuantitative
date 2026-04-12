import pytest
from fastapi import HTTPException

import app.api.trading as trading_api
from app.core.data_fetcher import DataFetcher


class _BalanceErrorAccount:
    is_available = True

    def __init__(self, result=None, error=None):
        self._result = result
        self._error = error

    def get_balance(self):
        if self._error is not None:
            raise RuntimeError(self._error)
        return self._result


@pytest.mark.asyncio
async def test_holdings_base_returns_503_when_balance_query_raises(monkeypatch):
    monkeypatch.setattr(
        trading_api,
        "get_account",
        lambda mode: _BalanceErrorAccount(error="balance upstream down"),
    )

    with pytest.raises(HTTPException) as exc_info:
        await trading_api.get_holdings_base(mode="simulated")

    assert exc_info.value.status_code == 503
    assert "balance upstream down" in exc_info.value.detail


@pytest.mark.asyncio
async def test_holdings_base_returns_503_when_balance_payload_contains_error(monkeypatch):
    monkeypatch.setattr(
        trading_api,
        "get_account",
        lambda mode: _BalanceErrorAccount(result={"error": "permission denied"}),
    )

    with pytest.raises(HTTPException) as exc_info:
        await trading_api.get_holdings_base(mode="simulated")

    assert exc_info.value.status_code == 503
    assert "permission denied" in exc_info.value.detail


def test_data_fetcher_orderbook_propagates_upstream_failure(monkeypatch):
    fetcher = object.__new__(DataFetcher)

    monkeypatch.setattr(
        DataFetcher,
        "_get_standard_orderbook_payload",
        lambda self, inst_id, size: (_ for _ in ()).throw(RuntimeError("books upstream down")),
        raising=True,
    )

    with pytest.raises(RuntimeError) as exc_info:
        DataFetcher.get_orderbook(fetcher, "BTC-USDT", 20)

    assert "books upstream down" in str(exc_info.value)
