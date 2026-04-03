import asyncio

from fastapi import APIRouter, Depends, HTTPException

from ..agent import (
    AgentQueryService,
    MarketAnalysisError,
    MarketAnalysisSecurityError,
    MarketAnalysisTimeoutError,
    run_market_analysis,
)
from ..agent.schemas import (
    AgentAlignmentQueryRequest,
    AgentCandleQueryRequest,
    AgentCorrelationQueryRequest,
    AgentDataHealthQueryRequest,
    AgentIndicatorQueryRequest,
    AgentMarketStructureRequest,
    AgentMarketQueryRequest,
    AgentOpportunityPatrolRequest,
    AgentOrderBookQueryRequest,
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
from ..models.schemas import DataResponse
from .deps import get_ctx


router = APIRouter(prefix="/agent", tags=["Agent"])


def get_agent_service(ctx=Depends(get_ctx)) -> AgentQueryService:
    return AgentQueryService(ctx)


def _map_query_error(exc: Exception) -> HTTPException:
    detail = str(exc)
    if "未找到" in detail:
        return HTTPException(status_code=404, detail=detail)
    return HTTPException(status_code=400, detail=detail)


@router.get("/capabilities", response_model=DataResponse, summary="列出 Agent 可用能力")
async def get_agent_capabilities(service: AgentQueryService = Depends(get_agent_service)):
    return DataResponse(data=service.list_capabilities())


@router.post("/query/market-snapshot", response_model=DataResponse, summary="读取行情快照")
async def query_market_snapshot(
    request: AgentMarketQueryRequest,
    service: AgentQueryService = Depends(get_agent_service),
):
    try:
        result = await asyncio.to_thread(service.get_market_snapshot, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return DataResponse(data=result)


@router.post("/query/candles", response_model=DataResponse, summary="读取多周期 K 线")
async def query_candles(
    request: AgentCandleQueryRequest,
    service: AgentQueryService = Depends(get_agent_service),
):
    try:
        result = await asyncio.to_thread(service.get_multi_timeframe_candles, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return DataResponse(data=result)


@router.post("/query/indicators", response_model=DataResponse, summary="读取指标快照")
async def query_indicators(
    request: AgentIndicatorQueryRequest,
    service: AgentQueryService = Depends(get_agent_service),
):
    try:
        result = await asyncio.to_thread(service.get_indicator_snapshot, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return DataResponse(data=result)


@router.post("/query/trading-context", response_model=DataResponse, summary="读取统一交易上下文")
async def query_trading_context(
    request: AgentTradingContextRequest,
    service: AgentQueryService = Depends(get_agent_service),
):
    try:
        result = await asyncio.to_thread(service.get_trading_context, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return DataResponse(data=result)


@router.post("/query/watchlist-scan", response_model=DataResponse, summary="扫描关注币种上下文")
async def query_watchlist_scan(
    request: AgentWatchlistScanRequest,
    service: AgentQueryService = Depends(get_agent_service),
):
    try:
        result = await asyncio.to_thread(service.scan_watchlist_context, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return DataResponse(data=result)


@router.post("/query/data-health", response_model=DataResponse, summary="读取数据健康度")
async def query_data_health(
    request: AgentDataHealthQueryRequest,
    service: AgentQueryService = Depends(get_agent_service),
):
    try:
        result = await asyncio.to_thread(service.get_data_health, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return DataResponse(data=result)


@router.post("/query/orderbook", response_model=DataResponse, summary="读取盘口快照")
async def query_orderbook(
    request: AgentOrderBookQueryRequest,
    service: AgentQueryService = Depends(get_agent_service),
):
    result = await asyncio.to_thread(service.get_orderbook_snapshot, request)
    return DataResponse(data=result)


@router.post("/query/recent-trades", response_model=DataResponse, summary="读取逐笔成交快照")
async def query_recent_trades(
    request: AgentRecentTradesQueryRequest,
    service: AgentQueryService = Depends(get_agent_service),
):
    result = await asyncio.to_thread(service.get_recent_trades_snapshot, request)
    return DataResponse(data=result)


@router.post("/query/position", response_model=DataResponse, summary="读取持仓快照")
async def query_position(
    request: AgentPositionQueryRequest,
    service: AgentQueryService = Depends(get_agent_service),
):
    result = await asyncio.to_thread(service.get_position_snapshot, request)
    return DataResponse(data=result)


@router.post("/analysis/multi-timeframe-alignment", response_model=DataResponse, summary="多周期联动分析")
async def analyze_multi_timeframe_alignment(
    request: AgentAlignmentQueryRequest,
    service: AgentQueryService = Depends(get_agent_service),
):
    try:
        result = await asyncio.to_thread(service.analyze_multi_timeframe_alignment, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return DataResponse(data=result)


@router.post("/analysis/market-structure", response_model=DataResponse, summary="结构化市场分析")
async def analyze_market_structure(
    request: AgentMarketStructureRequest,
    service: AgentQueryService = Depends(get_agent_service),
):
    try:
        result = await asyncio.to_thread(service.analyze_market_structure, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return DataResponse(data=result)


@router.post("/analysis/support-resistance", response_model=DataResponse, summary="识别支撑位与压力位")
async def analyze_support_resistance(
    request: AgentSupportResistanceRequest,
    service: AgentQueryService = Depends(get_agent_service),
):
    try:
        result = await asyncio.to_thread(service.detect_support_resistance, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return DataResponse(data=result)


@router.post("/analysis/price-projection", response_model=DataResponse, summary="生成未来路径推演")
async def analyze_price_projection(
    request: AgentPriceProjectionRequest,
    service: AgentQueryService = Depends(get_agent_service),
):
    try:
        result = await asyncio.to_thread(service.generate_price_projection, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return DataResponse(data=result)


@router.post("/analysis/opportunity-patrol", response_model=DataResponse, summary="主动巡检候选机会")
async def analyze_opportunity_patrol(
    request: AgentOpportunityPatrolRequest,
    service: AgentQueryService = Depends(get_agent_service),
):
    try:
        result = await asyncio.to_thread(service.patrol_market_opportunities, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return DataResponse(data=result)


@router.post("/analysis/risk-budget", response_model=DataResponse, summary="构建风险预算建议")
async def analyze_risk_budget(
    request: AgentRiskBudgetRequest,
    service: AgentQueryService = Depends(get_agent_service),
):
    try:
        result = await asyncio.to_thread(service.build_risk_budget, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return DataResponse(data=result)


@router.post("/analysis/trade-setup", response_model=DataResponse, summary="生成单标的交易计划")
async def analyze_trade_setup(
    request: AgentTradeSetupRequest,
    service: AgentQueryService = Depends(get_agent_service),
):
    try:
        result = await asyncio.to_thread(service.build_trade_setup, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return DataResponse(data=result)


@router.post("/analysis/watchlist-correlation", response_model=DataResponse, summary="分析关注列表或指定列表相关性")
async def analyze_watchlist_correlation(
    request: AgentCorrelationQueryRequest,
    service: AgentQueryService = Depends(get_agent_service),
):
    try:
        result = await asyncio.to_thread(service.analyze_watchlist_correlation, request)
    except Exception as exc:
        raise _map_query_error(exc)
    return DataResponse(data=result)


@router.post("/analyze/python", response_model=DataResponse, summary="执行受限 Python 市场分析")
async def analyze_market_with_python(
    request: AgentPythonAnalysisRequest,
    service: AgentQueryService = Depends(get_agent_service),
):
    try:
        dataset = await asyncio.to_thread(service.build_analysis_dataset, request)
        result = await asyncio.to_thread(
            run_market_analysis,
            code=request.code,
            dataset=dataset,
            timeout_seconds=request.timeout_seconds,
        )
    except MarketAnalysisSecurityError as exc:
        raise HTTPException(status_code=400, detail=f"分析代码被安全策略拒绝: {exc}")
    except MarketAnalysisTimeoutError as exc:
        raise HTTPException(status_code=408, detail=str(exc))
    except MarketAnalysisError as exc:
        raise HTTPException(status_code=400, detail=f"分析执行失败: {exc}")
    except Exception as exc:
        raise _map_query_error(exc)

    return DataResponse(data=result)
