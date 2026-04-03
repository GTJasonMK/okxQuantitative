from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from app.api import market as market_api


@pytest.mark.asyncio
async def test_market_data_health_endpoint_delegates_to_query_service(monkeypatch):
    captured = {}

    class FakeQueryService:
        def __init__(self, ctx):
            captured["ctx"] = ctx

        def get_data_health(self, request):
            captured["symbol"] = request.symbol
            captured["include_orphans"] = request.include_orphans
            return {
                "summary": {"symbol_count": 1},
                "rows": [
                    {
                        "symbol": request.symbol,
                        "status": "healthy",
                        "health_score": 96,
                    }
                ],
            }

    monkeypatch.setattr(market_api, "AgentQueryService", FakeQueryService, raising=True)

    ctx = SimpleNamespace()
    service = market_api.get_query_service(ctx)
    response = await market_api.get_market_data_health(
        symbol="BTC-USDT",
        include_orphans=False,
        service=service,
    )

    assert captured["ctx"] is ctx
    assert captured["symbol"] == "BTC-USDT"
    assert captured["include_orphans"] is False
    assert response.data["rows"][0]["symbol"] == "BTC-USDT"
    assert response.data["rows"][0]["status"] == "healthy"


@pytest.mark.asyncio
async def test_market_data_health_endpoint_maps_query_errors(monkeypatch):
    class FailingQueryService:
        def __init__(self, ctx):
            self.ctx = ctx

        def get_data_health(self, request):
            raise RuntimeError("数据健康查询失败")

    monkeypatch.setattr(market_api, "AgentQueryService", FailingQueryService, raising=True)

    service = market_api.get_query_service(SimpleNamespace())

    with pytest.raises(HTTPException) as exc_info:
        await market_api.get_market_data_health(
            symbol="ETH-USDT",
            include_orphans=True,
            service=service,
        )

    assert exc_info.value.status_code == 400
    assert "查询失败" in exc_info.value.detail
