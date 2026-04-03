# 行情数据API路由
# 提供K线数据、实时行情、技术指标等接口

import asyncio
from typing import Optional, List, Dict, Any
import numpy as np
from fastapi import APIRouter, Query, HTTPException, Depends
from pydantic import BaseModel, Field

from ..agent.queries import AgentQueryService
from ..agent.schemas import AgentDataHealthQueryRequest

from ..utils.datetimes import parse_iso_datetime
from ..models.schemas import (
    CandleModel,
    CandleListResponse,
    TickerModel,
    TickerResponse,
    TickerListResponse,
    InstrumentListResponse,
    IndicatorRequest,
    IndicatorResponse,
    SyncRequest,
    SyncStatusResponse,
    SyncJobStatusResponse,
    SyncJobListResponse,
    WatchedSymbolModel,
    WatchedSymbolListResponse,
    WatchedSymbolCreateRequest,
    WatchedSymbolCreateResponse,
    WatchedSymbolCreatePayload,
    WatchedSymbolDeleteResponse,
    WatchedSymbolDeletePayload,
    AvailableSymbolsResponse,
    DataResponse,
    TimeframeEnum,
    InstTypeEnum,
    SyncModeEnum,
)
from ..core import (
    DataStorage,
    IndicatorCalculator,
    InstType,
    CachedDataManager,
    CachedDataFetcher,
)
from ..core.app_context import AppContext
from ..core.data_guardian import (
    DEFAULT_TIMEFRAME_PLANS,
    get_data_guardian,
    normalize_guardian_settings,
)
from ..core.market_sync_tasks import get_market_sync_task_manager
from ..core.price_alerts import price_alert_store
from .deps import get_ctx
from ..utils.timeframes import calculate_candle_count
from ..utils.watched_symbols_store import (
    add_watched_symbol,
    get_watched_symbol,
    load_watched_symbols,
    normalize_watched_symbol,
    remove_watched_symbol,
    save_watched_symbols,
)


router = APIRouter(prefix="/market", tags=["行情数据"])


class CorrelationRequest(BaseModel):
    """相关性分析请求"""
    symbols: List[str] = Field(default_factory=list, description="交易对列表")
    timeframe: TimeframeEnum = Field(default=TimeframeEnum.H1, description="时间周期")
    days: int = Field(default=30, ge=1, le=365, description="分析天数")
    limit: int = Field(default=300, ge=20, le=1000, description="最大K线数量")
    inst_type: InstTypeEnum = Field(default=InstTypeEnum.SPOT, description="交易类型")


class PriceAlertRequest(BaseModel):
    """价格提醒创建请求"""
    inst_id: str = Field(..., description="交易对，如 BTC-USDT 或 BTC-USDT-SWAP")
    inst_type: InstTypeEnum = Field(default=InstTypeEnum.SPOT, description="交易类型")
    symbol: str = Field(default="", description="基础交易对，如 BTC-USDT")
    alert_type: str = Field(default="price", description="提醒类型：price/change")
    direction: str = Field(default="above", description="方向：above/below")
    target_price: Optional[float] = Field(default=None, description="目标价格")
    change_percent: Optional[float] = Field(default=None, description="目标涨跌幅百分比")
    note: str = Field(default="", description="备注")
    enabled: bool = Field(default=True, description="是否启用")
    trigger_once: bool = Field(default=True, description="触发后是否自动关闭")
    cooldown_seconds: int = Field(default=300, ge=0, le=86400, description="重复提醒冷却秒数")


class PriceAlertUpdateRequest(BaseModel):
    """价格提醒更新请求"""
    inst_id: Optional[str] = None
    inst_type: Optional[InstTypeEnum] = None
    symbol: Optional[str] = None
    alert_type: Optional[str] = None
    direction: Optional[str] = None
    target_price: Optional[float] = None
    change_percent: Optional[float] = None
    note: Optional[str] = None
    enabled: Optional[bool] = None
    trigger_once: Optional[bool] = None
    cooldown_seconds: Optional[int] = Field(default=None, ge=0, le=86400)


class DataGuardianPlanConfigRequest(BaseModel):
    """数据守护器单个周期配置"""
    timeframe: str = Field(..., description="时间周期，如 1m / 5m / 1H")
    enabled: bool = Field(default=True, description="是否启用该周期")
    bootstrap_days: int = Field(default=30, ge=1, le=3650, description="窗口初始化天数")
    archive_mode: str = Field(default="rolling", description="rolling/full")


class DataGuardianConfigRequest(BaseModel):
    """数据守护器配置请求"""
    enabled: bool = Field(default=True, description="是否启用后台数据守护器")
    scan_interval_seconds: int = Field(default=300, ge=60, le=3600, description="扫描周期")
    max_full_backfill_jobs_per_cycle: int = Field(default=1, ge=1, le=20, description="每轮最多执行的全量回补任务数")
    plans: List[DataGuardianPlanConfigRequest] = Field(default_factory=list, description="周期归档策略")


def _build_full_sync_runner(
    manager: CachedDataManager,
    *,
    inst_id: str,
    timeframe: str,
    days: int,
    inst_type: str,
):
    return lambda progress_callback: manager.sync_candles_full(
        inst_id,
        timeframe,
        days,
        inst_type,
        progress_callback=progress_callback,
    )


def _build_window_sync_runner(
    manager: CachedDataManager,
    *,
    inst_id: str,
    timeframe: str,
    days: int,
    inst_type: str,
):
    return lambda progress_callback: manager.sync_candles_window(
        inst_id,
        timeframe,
        days,
        inst_type,
        progress_callback=progress_callback,
    )


def _resolve_watch_sync_plans() -> List[Dict[str, Any]]:
    guardian = get_data_guardian()
    settings = guardian.get_settings()
    plans = settings.get("plans") if isinstance(settings, dict) else None
    if not isinstance(plans, list) or not plans:
        plans = DEFAULT_TIMEFRAME_PLANS

    normalized_plans: List[Dict[str, Any]] = []
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        timeframe = str(plan.get("timeframe") or "").strip()
        if not timeframe:
            continue
        if not bool(plan.get("enabled", True)):
            continue
        archive_mode = str(plan.get("archive_mode") or "rolling").strip().lower()
        if archive_mode not in {"rolling", "full"}:
            archive_mode = "rolling"
        normalized_plans.append({
            "timeframe": timeframe,
            "bootstrap_days": max(int(plan.get("bootstrap_days", 30) or 30), 1),
            "archive_mode": archive_mode,
        })
    return normalized_plans


def _start_watchlist_sync_jobs(
    manager: CachedDataManager,
    watched_symbol: Dict[str, Any],
    *,
    sync_spot: bool,
    sync_swap: bool,
) -> List[Dict[str, Any]]:
    task_manager = get_market_sync_task_manager()
    sync_jobs: List[Dict[str, Any]] = []
    sync_targets = []

    if sync_spot:
        sync_targets.append(("SPOT", watched_symbol.get("spot_inst_id") or watched_symbol["symbol"]))
    if sync_swap:
        sync_targets.append(("SWAP", watched_symbol.get("swap_inst_id") or f"{watched_symbol['symbol']}-SWAP"))

    plans = _resolve_watch_sync_plans()
    if not plans:
        return []

    for inst_type, inst_id in sync_targets:
        for plan in plans:
            sync_mode = "full" if plan.get("archive_mode") == "full" else "window"
            sync_jobs.append(
                task_manager.start_job(
                    inst_id=inst_id,
                    inst_type=inst_type,
                    timeframe=plan["timeframe"],
                    mode=sync_mode,
                    days=plan["bootstrap_days"],
                    runner=(
                        _build_full_sync_runner(
                            manager,
                            inst_id=inst_id,
                            timeframe=plan["timeframe"],
                            days=plan["bootstrap_days"],
                            inst_type=inst_type,
                        )
                        if sync_mode == "full"
                        else _build_window_sync_runner(
                            manager,
                            inst_id=inst_id,
                            timeframe=plan["timeframe"],
                            days=plan["bootstrap_days"],
                            inst_type=inst_type,
                        )
                    ),
                )
            )
    return sync_jobs


def _resolve_related_inst_ids(symbol: str) -> List[str]:
    normalized_symbol = normalize_watched_symbol(symbol)
    if not normalized_symbol:
        return []
    return [normalized_symbol, f"{normalized_symbol}-SWAP"]


def _resolve_inst_type_value(inst_id: str, inst_type: Optional[InstTypeEnum]) -> str:
    if inst_type is not None:
        return inst_type.value
    return "SWAP" if str(inst_id or "").upper().endswith("-SWAP") else "SPOT"


def _request_guardian_run_now_safely(source: str) -> None:
    try:
        guardian = get_data_guardian()
        guardian.request_run_now()
    except Exception as exc:
        print(f"[market] guardian.request_run_now 失败({source}): {exc}")


def _restore_watched_symbols_snapshot(records: List[Dict[str, Any]]) -> None:
    if not save_watched_symbols(records):
        raise RuntimeError("恢复关注币种快照失败")


def _cancel_related_sync_jobs(symbol: str, *, reason: str) -> List[Dict[str, Any]]:
    inst_ids = _resolve_related_inst_ids(symbol)
    if not inst_ids:
        return []
    task_manager = get_market_sync_task_manager()
    return task_manager.cancel_jobs(inst_ids=inst_ids, reason=reason)


def _list_related_active_jobs(symbol: str) -> List[Dict[str, Any]]:
    related_inst_ids = set(_resolve_related_inst_ids(symbol))
    if not related_inst_ids:
        return []

    task_manager = get_market_sync_task_manager()
    jobs = task_manager.list_jobs(only_active=True, limit=200)
    return [job for job in jobs if job.get("inst_id") in related_inst_ids]


def _build_inventory_response(storage: DataStorage) -> Dict[str, Any]:
    watched_items = load_watched_symbols()
    watched_symbols = {item["symbol"] for item in watched_items}
    rows = storage.get_symbol_data_inventory()

    table_totals = {
        "candles": 0,
        "sync_records": 0,
        "market_ticker_snapshots": 0,
        "market_recent_trades": 0,
        "local_fills": 0,
        "live_order_records": 0,
        "backtest_results": 0,
        "cost_basis": 0,
        "total": 0,
    }
    total_candles = 0
    total_timeframe_records = 0
    orphan_count = 0
    covered_watched_count = 0

    normalized_rows: List[Dict[str, Any]] = []
    for row in rows:
        symbol = normalize_watched_symbol(row.get("symbol"))
        watched = symbol in watched_symbols
        orphan = not watched
        if watched:
            covered_watched_count += 1
        if orphan:
            orphan_count += 1

        storage_counts = dict(row.get("storage_counts") or {})
        for key in table_totals:
            table_totals[key] += int(storage_counts.get(key, 0) or 0)

        total_candles += int(row.get("candle_count", 0) or 0)
        total_timeframe_records += int(row.get("timeframe_record_count", 0) or 0)

        normalized_rows.append({
            **row,
            "symbol": symbol,
            "watched": watched,
            "orphan": orphan,
        })

    return {
        "summary": {
            "symbol_count": len(normalized_rows),
            "watched_symbol_count": covered_watched_count,
            "watched_list_count": len(watched_symbols),
            "orphan_symbol_count": orphan_count,
            "total_candles": total_candles,
            "total_timeframe_records": total_timeframe_records,
            "table_totals": table_totals,
        },
        "rows": normalized_rows,
    }


# ==================== 依赖注入（使用单例缓存） ====================


def get_storage(ctx: AppContext = Depends(get_ctx)) -> DataStorage:
    """获取数据存储实例（单例）"""
    try:
        return ctx.storage()
    except Exception as e:
        print(f"[依赖注入] 获取存储实例失败: {e}")
        raise HTTPException(status_code=503, detail=f"存储服务初始化失败: {str(e)}")


def get_fetcher(ctx: AppContext = Depends(get_ctx)) -> Optional[CachedDataFetcher]:
    """获取数据获取器实例（单例）"""
    try:
        return ctx.fetcher()
    except Exception as e:
        print(f"[依赖注入] 获取数据获取器失败: {e}")
        return None


def get_manager(ctx: AppContext = Depends(get_ctx)) -> CachedDataManager:
    """获取数据管理器实例（单例）"""
    try:
        return ctx.manager()
    except Exception as e:
        print(f"[依赖注入] 获取数据管理器失败: {e}")
        raise HTTPException(status_code=503, detail=f"数据管理器初始化失败: {str(e)}")


def get_query_service(ctx: AppContext = Depends(get_ctx)) -> AgentQueryService:
    """获取给前端复用的只读查询服务。"""
    return AgentQueryService(ctx)


# ==================== 实时行情接口 ====================

@router.get("/ticker/{inst_id}", response_model=TickerResponse, summary="获取单个交易对行情")
async def get_ticker(
    inst_id: str,
    inst_type: Optional[InstTypeEnum] = Query(default=None, description="交易类型，不传时按交易对自动推断"),
    fresh: bool = Query(default=False, description="是否绕过本地缓存，直接获取最新行情"),
    fetcher: Optional[CachedDataFetcher] = Depends(get_fetcher),
    storage: DataStorage = Depends(get_storage),
):
    """
    获取指定交易对的实时行情

    - **inst_id**: 交易对，如 BTC-USDT
    """
    resolved_inst_type = _resolve_inst_type_value(inst_id, inst_type)
    ticker = None
    fetch_error = None

    if fetcher and fresh:
        try:
            direct_fetcher = getattr(fetcher, "fetcher", None)
            if direct_fetcher is None:
                raise RuntimeError("行情抓取器不可用")
            ticker = await asyncio.to_thread(
                direct_fetcher.get_ticker,
                inst_id,
            )
            if ticker:
                await asyncio.to_thread(
                    storage.save_ticker_snapshot,
                    ticker,
                    resolved_inst_type,
                    "rest",
                )
                await asyncio.to_thread(
                    fetcher.prime_ticker_cache,
                    ticker,
                    inst_type=resolved_inst_type,
                )
        except Exception as exc:
            fetch_error = exc
            print(f"[market] get_ticker 实时获取失败 {inst_id}: {exc}")

    if fetcher and not ticker:
        try:
            ticker = await asyncio.to_thread(
                fetcher.get_ticker_cached,
                inst_id,
                resolved_inst_type,
            )
        except Exception as exc:
            fetch_error = exc
            print(f"[market] get_ticker 缓存获取失败 {inst_id}: {exc}")

    if not ticker:
        try:
            ticker = await asyncio.to_thread(
                storage.get_latest_ticker,
                inst_id,
                inst_type=resolved_inst_type,
            )
        except Exception as exc:
            if fetch_error is None:
                fetch_error = exc
            print(f"[market] get_ticker 本地回退失败 {inst_id}: {exc}")

    if not ticker:
        if fetch_error and not fetcher:
            raise HTTPException(status_code=503, detail=f"获取行情失败: {str(fetch_error)}")
        raise HTTPException(status_code=404, detail=f"未找到交易对 {inst_id}，可能是API未配置或网络问题")

    return TickerResponse(
        data=TickerModel(
            inst_id=ticker.inst_id,
            last=ticker.last,
            last_sz=ticker.last_sz,
            ask_px=ticker.ask_px,
            bid_px=ticker.bid_px,
            open_24h=ticker.open_24h,
            high_24h=ticker.high_24h,
            low_24h=ticker.low_24h,
            vol_24h=ticker.vol_24h,
            change_24h=ticker.change_24h,
            timestamp=ticker.timestamp,
        )
    )


@router.get("/tickers", response_model=TickerListResponse, summary="获取所有行情")
async def get_tickers(
    inst_type: InstTypeEnum = Query(default=InstTypeEnum.SPOT, description="交易类型"),
    fetcher: Optional[CachedDataFetcher] = Depends(get_fetcher),
    storage: DataStorage = Depends(get_storage),
):
    """
    获取指定类型所有交易对的行情

    - **inst_type**: 交易类型 (SPOT/SWAP/FUTURES/OPTION)
    """
    tickers: Dict[str, Any] = {}
    fetch_error = None

    if fetcher:
        try:
            tickers = await asyncio.to_thread(fetcher.get_tickers_cached, inst_type.value)
        except Exception as exc:
            fetch_error = exc
            print(f"[market] get_tickers 缓存获取失败 {inst_type.value}: {exc}")

    if not tickers:
        try:
            local_tickers = await asyncio.to_thread(
                storage.get_latest_tickers,
                inst_type=inst_type.value,
            )
            tickers = {ticker.inst_id: ticker for ticker in local_tickers}
        except Exception as exc:
            if fetch_error is None:
                fetch_error = exc
            print(f"[market] get_tickers 本地回退失败 {inst_type.value}: {exc}")

    if fetch_error and not tickers and not fetcher:
        raise HTTPException(status_code=503, detail=f"获取行情列表失败: {str(fetch_error)}")

    return TickerListResponse(
        data=[
            TickerModel(
                inst_id=t.inst_id,
                last=t.last,
                last_sz=t.last_sz,
                ask_px=t.ask_px,
                bid_px=t.bid_px,
                open_24h=t.open_24h,
                high_24h=t.high_24h,
                low_24h=t.low_24h,
                vol_24h=t.vol_24h,
                change_24h=t.change_24h,
                timestamp=t.timestamp,
            )
            for t in tickers.values()
        ]
    )


@router.get("/trades/{inst_id}", response_model=DataResponse, summary="获取最新逐笔成交")
async def get_recent_trades(
    inst_id: str,
    limit: int = Query(default=30, ge=1, le=100, description="返回数量"),
    inst_type: Optional[InstTypeEnum] = Query(default=None, description="交易类型，不传时按交易对自动推断"),
    fetcher: Optional[CachedDataFetcher] = Depends(get_fetcher),
    storage: DataStorage = Depends(get_storage),
):
    """
    获取交易对最新公共逐笔成交。

    - **inst_id**: 交易对，如 BTC-USDT 或 BTC-USDT-SWAP
    - **limit**: 返回数量，最大 100
    """
    resolved_inst_type = _resolve_inst_type_value(inst_id, inst_type)
    trades = []
    fetch_error = None

    if fetcher:
        try:
            trades = await asyncio.to_thread(
                fetcher.get_recent_trades_local_first,
                inst_id,
                limit,
                inst_type=resolved_inst_type,
            )
        except Exception as exc:
            fetch_error = exc
            print(f"[market] get_recent_trades 缓存获取失败 {inst_id}: {exc}")

    if not trades:
        try:
            trades = await asyncio.to_thread(
                storage.get_recent_trades,
                inst_id,
                limit=limit,
                inst_type=resolved_inst_type,
            )
        except Exception as exc:
            if fetch_error is None:
                fetch_error = exc
            print(f"[market] get_recent_trades 本地回退失败 {inst_id}: {exc}")

    if fetch_error and not trades and not fetcher:
        raise HTTPException(status_code=503, detail=f"获取逐笔成交失败: {str(fetch_error)}")

    return DataResponse(data=[trade.to_dict() for trade in trades])


@router.get("/orderbook/{inst_id}", response_model=DataResponse, summary="获取盘口深度")
async def get_orderbook(
    inst_id: str,
    size: int = Query(default=20, ge=1, le=500, description="返回档位数量"),
    fetcher: Optional[CachedDataFetcher] = Depends(get_fetcher),
):
    """
    获取交易对盘口深度。

    - **inst_id**: 交易对，如 BTC-USDT 或 BTC-USDT-SWAP
    - **size**: 返回档位数量，最大 500；超过 400 时后端会自动切到 books-full，失败时降级到 400 档
    """
    if not fetcher:
        raise HTTPException(status_code=503, detail="数据获取器不可用，无法获取盘口深度")

    try:
        orderbook = await asyncio.to_thread(fetcher.get_orderbook, inst_id, size)
    except Exception as exc:
        print(f"[market] get_orderbook 获取失败 {inst_id}: {exc}")
        raise HTTPException(status_code=503, detail=f"获取盘口深度失败: {str(exc)}") from exc

    if not orderbook:
        raise HTTPException(status_code=503, detail=f"未获取到 {inst_id} 的盘口深度")

    return DataResponse(data=orderbook)


# ==================== K线数据接口 ====================

@router.get("/candles/{inst_id}", response_model=CandleListResponse, summary="获取K线数据")
async def get_candles(
    inst_id: str,
    timeframe: TimeframeEnum = Query(default=TimeframeEnum.H1, description="时间周期"),
    limit: int = Query(default=100, ge=1, le=5000, description="数量限制"),
    start_time: Optional[str] = Query(default=None, description="开始时间 (ISO格式)"),
    end_time: Optional[str] = Query(default=None, description="结束时间 (ISO格式)"),
    inst_type: InstTypeEnum = Query(default=InstTypeEnum.SPOT, description="交易类型"),
    manager: CachedDataManager = Depends(get_manager)
):
    """
    获取K线数据

    - **inst_id**: 交易对
    - **timeframe**: 时间周期
    - **limit**: 返回数量
    """
    # 解析时间参数（带校验）
    start_dt = None
    end_dt = None
    if start_time:
        try:
            start_dt = parse_iso_datetime(start_time)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的开始时间格式: {start_time}，请使用ISO格式（如2024-01-01T00:00:00）")
    if end_time:
        try:
            end_dt = parse_iso_datetime(end_time)
        except ValueError:
            raise HTTPException(status_code=400, detail=f"无效的结束时间格式: {end_time}，请使用ISO格式（如2024-01-01T00:00:00）")

    # 统一走“本地库优先”；首次缺失会先全量初始化，后续按需增量刷新。
    candles = await asyncio.to_thread(
        manager.get_local_candles,
        inst_id,
        timeframe.value,
        limit=limit,
        start_time=start_dt,
        end_time=end_dt,
        auto_sync=True,
        inst_type=inst_type.value,
    )

    candle_models = [
        CandleModel(
            timestamp=c.timestamp,
            datetime=c.datetime.isoformat(),
            open=c.open,
            high=c.high,
            low=c.low,
            close=c.close,
            volume=c.volume,
            volume_ccy=c.volume_ccy,
        )
        for c in candles
    ]

    return CandleListResponse(data=candle_models, total=len(candle_models))


# ==================== 技术指标接口 ====================

@router.post("/indicators", response_model=IndicatorResponse, summary="计算技术指标")
async def calculate_indicators(
    request: IndicatorRequest,
    manager: CachedDataManager = Depends(get_manager)
):
    """
    计算技术指标

    支持的指标:
    - ma5, ma10, ma20, ma60: 移动平均线
    - ema12, ema26: 指数移动平均
    - macd: MACD指标
    - rsi: RSI指标
    - bollinger: 布林带
    - kdj: KDJ指标
    - atr: ATR指标
    - volume_ma: 成交量均线
    """
    # 获取K线数据（使用 asyncio.to_thread 避免阻塞事件循环，可能触发网络同步）
    candles = await asyncio.to_thread(
        manager.get_candles_with_sync,
        request.inst_id,
        request.timeframe.value,
        request.limit,
        True,
        inst_type=request.inst_type.value,
    )

    if not candles:
        raise HTTPException(status_code=404, detail="未找到K线数据")

    # 计算指标
    calculator = IndicatorCalculator(candles)

    indicators = {}
    for name in request.indicators:
        name_lower = name.lower()
        if name_lower.startswith("ma") and name_lower[2:].isdigit():
            period = int(name_lower[2:])
            indicators[name] = calculator.sma(period)
        elif name_lower.startswith("ema") and name_lower[3:].isdigit():
            period = int(name_lower[3:])
            indicators[name] = calculator.ema(period)
        elif name_lower == "macd":
            indicators[name] = calculator.macd()
        elif name_lower == "rsi":
            indicators[name] = calculator.rsi()
        elif name_lower == "bollinger":
            indicators[name] = calculator.bollinger()
        elif name_lower == "kdj":
            indicators[name] = calculator.kdj()
        elif name_lower == "atr":
            indicators[name] = calculator.atr()
        elif name_lower == "volume_ma":
            indicators[name] = calculator.volume_ma()

    # 转换K线数据
    candle_models = [
        CandleModel(
            timestamp=c.timestamp,
            datetime=c.datetime.isoformat(),
            open=c.open,
            high=c.high,
            low=c.low,
            close=c.close,
            volume=c.volume,
            volume_ccy=c.volume_ccy,
        )
        for c in candles
    ]

    return IndicatorResponse(data=indicators, candles=candle_models)


# ==================== 数据同步接口 ====================

@router.post("/sync", response_model=DataResponse, summary="同步K线数据")
async def sync_candles(
    request: SyncRequest,
    manager: CachedDataManager = Depends(get_manager)
):
    """
    从交易所同步K线数据到本地

    - **inst_id**: 交易对
    - **timeframe**: 时间周期
    - **days**: 窗口同步或增量 bootstrap 的天数
    - **mode**:
      - window: 同步最近 N 天
      - incremental: 仅补本地最新 K 线之后的缺口
      - full: 向过去分页回补到最早可获取历史，并补齐最新缺口
    """
    if not manager.fetcher:
        raise HTTPException(status_code=503, detail="交易所数据服务不可用")

    try:
        # 使用 asyncio.to_thread 避免阻塞事件循环（同步操作包含网络请求和 time.sleep）
        if request.mode == SyncModeEnum.FULL:
            result = await asyncio.to_thread(
                manager.sync_candles_full,
                request.inst_id,
                request.timeframe.value,
                request.days,
                request.inst_type.value,
            )
        elif request.mode == SyncModeEnum.INCREMENTAL:
            result = await asyncio.to_thread(
                manager.sync_candles_incremental,
                request.inst_id,
                request.timeframe.value,
                request.days,
                request.inst_type.value,
            )
        else:
            result = await asyncio.to_thread(
                manager.sync_candles_window,
                request.inst_id,
                request.timeframe.value,
                request.days,
                request.inst_type.value,
            )
        return DataResponse(data=result)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.post("/sync/jobs", response_model=SyncJobStatusResponse, summary="启动后台K线同步任务")
async def start_sync_job(
    request: SyncRequest,
    manager: CachedDataManager = Depends(get_manager),
):
    """启动后台同步任务，立即返回 task_id，适合全量回补等长任务。"""
    if not manager.fetcher:
        raise HTTPException(status_code=503, detail="交易所数据服务不可用")

    task_manager = get_market_sync_task_manager()

    def _build_runner():
        if request.mode == SyncModeEnum.FULL:
            return lambda progress_callback: manager.sync_candles_full(
                request.inst_id,
                request.timeframe.value,
                request.days,
                request.inst_type.value,
                progress_callback=progress_callback,
            )
        if request.mode == SyncModeEnum.INCREMENTAL:
            return lambda progress_callback: manager.sync_candles_incremental(
                request.inst_id,
                request.timeframe.value,
                request.days,
                request.inst_type.value,
                progress_callback=progress_callback,
            )
        return lambda progress_callback: manager.sync_candles_window(
            request.inst_id,
            request.timeframe.value,
            request.days,
            request.inst_type.value,
            progress_callback=progress_callback,
        )

    try:
        job_data = task_manager.start_job(
            inst_id=request.inst_id,
            inst_type=request.inst_type.value,
            timeframe=request.timeframe.value,
            mode=request.mode.value,
            days=request.days,
            runner=_build_runner(),
        )
        return SyncJobStatusResponse(data=job_data)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"启动后台同步任务失败: {str(e)}")


@router.get("/sync/jobs", response_model=SyncJobListResponse, summary="获取后台K线同步任务列表")
async def list_sync_jobs(
    active_only: bool = Query(default=False, description="是否仅返回运行中的任务"),
    limit: int = Query(default=20, ge=1, le=200, description="返回数量"),
    task_ids: str = Query(default="", description="逗号分隔的 task_id 列表"),
):
    """获取后台同步任务列表。"""
    task_manager = get_market_sync_task_manager()
    task_id_list = [item.strip() for item in task_ids.split(",") if item.strip()]
    jobs = task_manager.list_jobs(
        only_active=active_only,
        limit=limit,
        task_ids=task_id_list or None,
    )

    return SyncJobListResponse(data=jobs)


@router.get("/sync/jobs/{task_id}", response_model=SyncJobStatusResponse, summary="获取后台K线同步任务详情")
async def get_sync_job(task_id: str):
    """获取单个后台同步任务详情。"""
    task_manager = get_market_sync_task_manager()
    job = task_manager.get_job(task_id)
    if not job:
        raise HTTPException(status_code=404, detail="同步任务不存在")
    return SyncJobStatusResponse(data=job)


@router.get("/sync/status", response_model=SyncStatusResponse, summary="获取同步状态")
async def get_sync_status(
    storage: DataStorage = Depends(get_storage)
):
    """获取所有交易对的数据同步状态"""
    status = await asyncio.to_thread(storage.get_sync_status)
    return SyncStatusResponse(data=status)


@router.get("/data-guardian/status", response_model=DataResponse, summary="获取数据守护器状态")
async def get_data_guardian_status():
    """返回后台本地数据守护器当前状态。"""
    guardian = get_data_guardian()
    return DataResponse(data=guardian.get_status())


@router.get("/data-guardian/config", response_model=DataResponse, summary="获取数据守护器配置")
async def get_data_guardian_config():
    """返回当前数据守护器配置与默认配置。"""
    guardian = get_data_guardian()
    return DataResponse(data={
        "settings": guardian.get_settings(),
        "defaults": guardian.get_default_settings(),
    })


@router.put("/data-guardian/config", response_model=DataResponse, summary="更新数据守护器配置")
async def update_data_guardian_config(request: DataGuardianConfigRequest):
    """保存数据守护器配置，并立即热更新到运行中的后台守护器。"""
    guardian = get_data_guardian()
    settings = normalize_guardian_settings(request.model_dump())
    applied = await asyncio.to_thread(lambda: guardian.apply_settings(settings, persist=True))
    _request_guardian_run_now_safely("update_data_guardian_config")
    return DataResponse(data={
        "settings": applied,
        "defaults": guardian.get_default_settings(),
        "status": guardian.get_status(),
    })


@router.post("/data-guardian/run-now", response_model=DataResponse, summary="立即触发数据守护器扫描")
async def trigger_data_guardian_scan():
    """手动请求后台数据守护器立即执行下一轮扫描。"""
    guardian = get_data_guardian()
    return DataResponse(data=guardian.request_run_now())


# ==================== 交易产品接口 ====================

@router.get("/instruments", response_model=InstrumentListResponse, summary="获取交易产品列表")
async def get_instruments(
    inst_type: InstTypeEnum = Query(default=InstTypeEnum.SPOT, description="交易类型"),
    fetcher: Optional[CachedDataFetcher] = Depends(get_fetcher)
):
    """
    获取交易所支持的交易产品列表

    - **inst_type**: 交易类型
    """
    if not fetcher:
        raise HTTPException(status_code=503, detail="数据服务不可用")

    # 使用 asyncio.to_thread 避免阻塞事件循环
    instruments = await asyncio.to_thread(fetcher.get_instruments, InstType(inst_type.value))
    return InstrumentListResponse(data=instruments)


@router.get("/symbols", response_model=AvailableSymbolsResponse, summary="获取本地已有数据的交易对")
async def get_available_symbols(
    storage: DataStorage = Depends(get_storage)
):
    """获取本地数据库中已有数据的交易对列表"""
    symbols = await asyncio.to_thread(storage.get_available_symbols)
    return AvailableSymbolsResponse(data=symbols)


@router.get("/watched-symbols", response_model=WatchedSymbolListResponse, summary="获取关注币种列表")
async def get_watched_symbols():
    """返回当前作为主数据源的关注币种列表。"""
    symbols = await asyncio.to_thread(load_watched_symbols)
    return WatchedSymbolListResponse(
        data=[WatchedSymbolModel.model_validate(item) for item in symbols]
    )


@router.post("/watched-symbols", response_model=WatchedSymbolCreateResponse, summary="新增关注币种并启动全量同步")
async def create_watched_symbol(
    request: WatchedSymbolCreateRequest,
    manager: CachedDataManager = Depends(get_manager),
):
    """新增关注币种，保存后立即为该币启动现货/永续的多周期全量回补任务。"""
    normalized_symbol = normalize_watched_symbol(request.symbol)
    if not normalized_symbol:
        raise HTTPException(status_code=400, detail="无效币种，请输入 BTC 或 BTC-USDT 这类交易对")
    if not request.sync_spot and not request.sync_swap:
        raise HTTPException(status_code=400, detail="至少需要选择一种同步目标（现货或永续）")

    existing = await asyncio.to_thread(get_watched_symbol, normalized_symbol)
    existing_sync_spot = bool(existing.get("sync_spot", True)) if existing else False
    existing_sync_swap = bool(existing.get("sync_swap", True)) if existing else False

    try:
        watched_symbol, existed = await asyncio.to_thread(
            add_watched_symbol,
            normalized_symbol,
            sync_spot=request.sync_spot,
            sync_swap=request.sync_swap,
            archive_all_history=request.archive_all_history,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"新增关注币种失败: {str(exc)}")

    manager_storage = getattr(manager, "storage", None)
    if manager_storage:
        await asyncio.to_thread(manager_storage.unblock_symbol_writes, normalized_symbol)

    sync_jobs: List[Dict[str, Any]] = []
    sync_deferred = False
    sync_message = ""
    sync_spot = request.sync_spot if not existed else (request.sync_spot and not existing_sync_spot)
    sync_swap = request.sync_swap if not existed else (request.sync_swap and not existing_sync_swap)

    if existed and not sync_spot and not sync_swap:
        _request_guardian_run_now_safely("create_watched_symbol")
        return WatchedSymbolCreateResponse(
            data=WatchedSymbolCreatePayload(
                watched_symbol=WatchedSymbolModel.model_validate(watched_symbol),
                existed=True,
                sync_jobs=[],
                sync_deferred=False,
                sync_message="",
            )
        )

    if not manager.fetcher:
        sync_deferred = True
        sync_message = "交易所连接当前不可用，已加入关注列表；待连接恢复后会由后台守护器自动同步。"
    else:
        try:
            sync_jobs = await asyncio.to_thread(
                _start_watchlist_sync_jobs,
                manager,
                watched_symbol,
                sync_spot=sync_spot,
                sync_swap=sync_swap,
            )
            if (sync_spot or sync_swap) and not sync_jobs:
                sync_deferred = True
                sync_message = "当前数据守护器未启用任何周期，已加入关注列表；启用周期后会再启动同步。"
        except Exception as exc:
            sync_deferred = True
            sync_message = f"已加入关注列表，但启动同步任务失败：{str(exc)}；后台守护器会在后续自动重试。"
            print(f"[watchlist] 启动关注币同步任务失败: {normalized_symbol} -> {exc}")

    _request_guardian_run_now_safely("create_watched_symbol")
    return WatchedSymbolCreateResponse(
        data=WatchedSymbolCreatePayload(
            watched_symbol=WatchedSymbolModel.model_validate(watched_symbol),
            existed=existed,
            sync_jobs=sync_jobs,
            sync_deferred=sync_deferred,
            sync_message=sync_message,
        )
    )


@router.post("/watched-symbols/{symbol}/repair", response_model=DataResponse, summary="重新发起关注币种数据回补")
async def repair_watched_symbol(
    symbol: str,
    sync_spot: bool = Query(default=True, description="是否重新发起现货回补"),
    sync_swap: bool = Query(default=True, description="是否重新发起永续回补"),
    manager: CachedDataManager = Depends(get_manager),
):
    """
    依据当前关注币种配置，重新为该币种发起后台回补任务。

    - 会复用数据守护器当前启用的周期配置
    - 同一 inst_id / timeframe / mode / days 的运行中任务会自动复用，不会重复创建
    """
    normalized_symbol = normalize_watched_symbol(symbol)
    if not normalized_symbol:
        raise HTTPException(status_code=400, detail="无效币种")
    if not sync_spot and not sync_swap:
        raise HTTPException(status_code=400, detail="至少需要选择一种修复目标（现货或永续）")

    watched_record = await asyncio.to_thread(get_watched_symbol, normalized_symbol)
    if not watched_record:
        raise HTTPException(status_code=404, detail="关注币种不存在")
    if not manager.fetcher:
        raise HTTPException(status_code=503, detail="交易所数据服务不可用")

    effective_sync_spot = bool(sync_spot and watched_record.get("sync_spot", True))
    effective_sync_swap = bool(sync_swap and watched_record.get("sync_swap", True))
    if not effective_sync_spot and not effective_sync_swap:
        raise HTTPException(status_code=400, detail="该币当前未启用所选市场的同步配置")

    try:
        sync_jobs = await asyncio.to_thread(
            _start_watchlist_sync_jobs,
            manager,
            watched_record,
            sync_spot=effective_sync_spot,
            sync_swap=effective_sync_swap,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"重新发起回补失败: {str(exc)}")

    _request_guardian_run_now_safely("repair_watched_symbol")
    started_count = sum(1 for job in sync_jobs if not bool(job.get("reused_existing")))
    reused_count = sum(1 for job in sync_jobs if bool(job.get("reused_existing")))
    return DataResponse(data={
        "symbol": watched_record["symbol"],
        "sync_jobs": sync_jobs,
        "requested_markets": {
            "spot": sync_spot,
            "swap": sync_swap,
        },
        "effective_markets": {
            "spot": effective_sync_spot,
            "swap": effective_sync_swap,
        },
        "started_count": started_count,
        "reused_count": reused_count,
    })


@router.delete("/watched-symbols/{symbol}", response_model=WatchedSymbolDeleteResponse, summary="删除关注币种并清理本地数据")
async def delete_watched_symbol(
    symbol: str,
    storage: DataStorage = Depends(get_storage),
):
    """删除关注币种，并清掉该币相关本地历史、快照、成交和回测数据。"""
    normalized_symbol = normalize_watched_symbol(symbol)
    if not normalized_symbol:
        raise HTTPException(status_code=400, detail="无效币种")

    watched_snapshot = await asyncio.to_thread(load_watched_symbols)
    watched_record = await asyncio.to_thread(get_watched_symbol, normalized_symbol)
    if not watched_record:
        raise HTTPException(status_code=404, detail="关注币种不存在")

    await asyncio.to_thread(storage.block_symbol_writes, normalized_symbol)
    affected_jobs = await asyncio.to_thread(
        _cancel_related_sync_jobs,
        normalized_symbol,
        reason="币种已从关注列表移除，后台同步任务已取消",
    )

    try:
        removed_record, removed = await asyncio.to_thread(remove_watched_symbol, normalized_symbol)
        if not removed:
            raise RuntimeError("删除关注币种失败")
    except Exception as exc:
        await asyncio.to_thread(storage.unblock_symbol_writes, normalized_symbol)
        raise HTTPException(status_code=500, detail=f"删除关注币种失败: {str(exc)}")

    try:
        deleted_counts = await asyncio.to_thread(storage.delete_symbol_related_data, normalized_symbol)
    except Exception as exc:
        rollback_error = None
        try:
            await asyncio.to_thread(_restore_watched_symbols_snapshot, watched_snapshot)
            await asyncio.to_thread(storage.unblock_symbol_writes, normalized_symbol)
        except Exception as rollback_exc:
            rollback_error = rollback_exc
        detail = f"清理本地数据失败，已回滚关注列表: {str(exc)}"
        if rollback_error is not None:
            detail = f"清理本地数据失败且回滚关注列表失败: {str(exc)}；回滚错误: {rollback_error}"
        raise HTTPException(status_code=500, detail=detail)

    _request_guardian_run_now_safely("delete_watched_symbol")

    payload = WatchedSymbolDeletePayload(
        symbol=removed_record["symbol"] if removed_record else watched_record["symbol"],
        deleted=True,
        deleted_counts=deleted_counts,
        active_sync_jobs=affected_jobs,
    )
    return WatchedSymbolDeleteResponse(data=payload)


@router.get("/inventory", response_model=DataResponse, summary="获取本地数据库库存总览")
async def get_market_inventory(
    storage: DataStorage = Depends(get_storage),
):
    """返回本地数据库当前实际持有的数据目录，并标记哪些属于未关注孤儿数据。"""
    inventory = await asyncio.to_thread(_build_inventory_response, storage)
    return DataResponse(data=inventory)


@router.get("/data-health", response_model=DataResponse, summary="获取本地数据健康状态")
async def get_market_data_health(
    symbol: str = Query(default="", description="基础币对，如 BTC-USDT；为空时返回全部"),
    include_orphans: bool = Query(default=True, description="是否包含未关注孤儿数据"),
    service: AgentQueryService = Depends(get_query_service),
):
    """复用 AgentQueryService 的数据健康统计，提供给前端页面直接查询。"""
    request = AgentDataHealthQueryRequest(
        symbol=symbol,
        include_orphans=include_orphans,
    )
    try:
        payload = await asyncio.to_thread(service.get_data_health, request)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return DataResponse(data=payload)


@router.delete("/inventory/symbols/{symbol}", response_model=DataResponse, summary="删除单个币种的本地库存")
async def delete_inventory_symbol(
    symbol: str,
    remove_watch: bool = Query(default=False, description="若该币仍在关注列表中，是否一并移除关注"),
    storage: DataStorage = Depends(get_storage),
):
    """删除单币本地库存；若币仍在关注列表中，可选择同时移除关注。"""
    normalized_symbol = normalize_watched_symbol(symbol)
    if not normalized_symbol:
        raise HTTPException(status_code=400, detail="无效币种")

    watched_record = await asyncio.to_thread(get_watched_symbol, normalized_symbol)
    if watched_record and not remove_watch:
        raise HTTPException(status_code=409, detail="该币仍在关注列表中，请先删除关注，或传 remove_watch=true 一并移除")

    watched_snapshot = await asyncio.to_thread(load_watched_symbols)
    await asyncio.to_thread(storage.block_symbol_writes, normalized_symbol)
    affected_jobs = await asyncio.to_thread(
        _cancel_related_sync_jobs,
        normalized_symbol,
        reason="币种库存已删除，后台同步任务已取消",
    )

    removed_from_watch = False
    if watched_record and remove_watch:
        try:
            removed_record, removed = await asyncio.to_thread(remove_watched_symbol, normalized_symbol)
            if not removed:
                raise RuntimeError("移除关注币种失败")
            removed_from_watch = bool(removed_record)
        except Exception as exc:
            await asyncio.to_thread(storage.unblock_symbol_writes, normalized_symbol)
            raise HTTPException(status_code=500, detail=f"移除关注币种失败: {str(exc)}")

    try:
        deleted_counts = await asyncio.to_thread(storage.delete_symbol_related_data, normalized_symbol)
    except Exception as exc:
        rollback_error = None
        if watched_record and remove_watch:
            try:
                await asyncio.to_thread(_restore_watched_symbols_snapshot, watched_snapshot)
            except Exception as rollback_exc:
                rollback_error = rollback_exc
        await asyncio.to_thread(storage.unblock_symbol_writes, normalized_symbol)
        detail = f"删除本地库存失败: {str(exc)}"
        if rollback_error is not None:
            detail = f"删除本地库存失败且恢复关注列表失败: {str(exc)}；回滚错误: {rollback_error}"
        raise HTTPException(status_code=500, detail=detail)

    _request_guardian_run_now_safely("delete_inventory_symbol")

    return DataResponse(data={
        "symbol": normalized_symbol,
        "removed_from_watch": removed_from_watch,
        "deleted_counts": deleted_counts,
        "active_sync_jobs": affected_jobs,
    })


@router.delete("/inventory/orphans", response_model=DataResponse, summary="批量清理未关注孤儿数据")
async def delete_orphan_inventory(
    storage: DataStorage = Depends(get_storage),
):
    """删除所有不在关注列表中的本地库存数据。"""
    inventory = await asyncio.to_thread(_build_inventory_response, storage)
    orphan_rows = [row for row in inventory["rows"] if row.get("orphan")]
    aggregate_deleted_counts = {
        "candles": 0,
        "sync_records": 0,
        "market_ticker_snapshots": 0,
        "market_recent_trades": 0,
        "local_fills": 0,
        "live_order_records": 0,
        "backtest_results": 0,
        "cost_basis": 0,
        "total": 0,
    }
    deleted_symbols: List[str] = []

    for row in orphan_rows:
        symbol = row.get("symbol")
        if not symbol:
            continue
        await asyncio.to_thread(storage.block_symbol_writes, symbol)
        await asyncio.to_thread(
            _cancel_related_sync_jobs,
            symbol,
            reason="孤儿库存已删除，后台同步任务已取消",
        )
        deleted_counts = await asyncio.to_thread(storage.delete_symbol_related_data, symbol)
        deleted_symbols.append(symbol)
        for key in aggregate_deleted_counts:
            aggregate_deleted_counts[key] += int(deleted_counts.get(key, 0) or 0)

    _request_guardian_run_now_safely("delete_orphan_inventory")

    return DataResponse(data={
        "deleted_symbols": deleted_symbols,
        "deleted_symbol_count": len(deleted_symbols),
        "deleted_counts": aggregate_deleted_counts,
    })


# ==================== 价格提醒接口 ====================

@router.get("/alerts", response_model=DataResponse, summary="获取价格提醒列表")
async def get_price_alerts(
    inst_id: str = Query(default="", description="按交易对过滤"),
    inst_type: str = Query(default="", description="按交易类型过滤"),
):
    alerts = await asyncio.to_thread(price_alert_store.list_alerts, inst_id=inst_id, inst_type=inst_type)
    return DataResponse(data=alerts)


@router.post("/alerts", response_model=DataResponse, summary="创建价格提醒")
async def create_price_alert(request: PriceAlertRequest):
    try:
        alert = await asyncio.to_thread(price_alert_store.create_alert, request.model_dump())
        return DataResponse(data=alert)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"创建价格提醒失败: {str(e)}")


@router.patch("/alerts/{alert_id}", response_model=DataResponse, summary="更新价格提醒")
async def update_price_alert(alert_id: str, request: PriceAlertUpdateRequest):
    payload = {key: value for key, value in request.model_dump().items() if value is not None}
    try:
        updated = await asyncio.to_thread(price_alert_store.update_alert, alert_id, payload)
        if not updated:
            raise HTTPException(status_code=404, detail="价格提醒不存在")
        return DataResponse(data=updated)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"更新价格提醒失败: {str(e)}")


@router.delete("/alerts/{alert_id}", response_model=DataResponse, summary="删除价格提醒")
async def delete_price_alert(alert_id: str):
    deleted = await asyncio.to_thread(price_alert_store.delete_alert, alert_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="价格提醒不存在")
    return DataResponse(data={"deleted": True, "id": alert_id})


# ==================== 市场相关性分析 ====================

@router.post("/correlation", response_model=DataResponse, summary="市场相关性分析")
async def analyze_market_correlation(
    request: CorrelationRequest,
    manager: CachedDataManager = Depends(get_manager),
):
    if len(request.symbols) < 2:
        raise HTTPException(status_code=400, detail="至少需要 2 个交易对")

    unique_symbols = []
    seen = set()
    for symbol in request.symbols:
        normalized = (symbol or "").upper().strip()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_symbols.append(normalized)

    if len(unique_symbols) < 2:
        raise HTTPException(status_code=400, detail="有效交易对数量不足")

    candle_count = min(
        request.limit,
        max(20, calculate_candle_count(timeframe=request.timeframe.value, days=request.days))
    )

    async def _load_symbol(symbol: str):
        candles = await asyncio.to_thread(
            manager.get_candles_with_sync,
            symbol,
            request.timeframe.value,
            candle_count,
            True,
            inst_type=request.inst_type.value,
        )
        if len(candles) < 20:
            raise HTTPException(status_code=400, detail=f"{symbol} 可用K线不足，至少需要 20 根")
        return symbol, candles

    results = await asyncio.gather(*[_load_symbol(symbol) for symbol in unique_symbols])

    series_by_symbol: Dict[str, Dict[int, float]] = {}
    for symbol, candles in results:
        series_by_symbol[symbol] = {int(c.timestamp): float(c.close) for c in candles}

    common_timestamps = None
    for series in series_by_symbol.values():
        timestamps = set(series.keys())
        common_timestamps = timestamps if common_timestamps is None else common_timestamps & timestamps

    common_timestamps = sorted(common_timestamps or [])
    if len(common_timestamps) < 20:
        raise HTTPException(status_code=400, detail="交易对之间公共时间轴不足，无法计算稳定相关性")

    returns_by_symbol: Dict[str, np.ndarray] = {}
    for symbol in unique_symbols:
        prices = np.array([series_by_symbol[symbol][ts] for ts in common_timestamps], dtype=float)
        returns = np.diff(prices) / prices[:-1]
        if returns.size < 5:
            raise HTTPException(status_code=400, detail=f"{symbol} 收益率样本不足")
        returns_by_symbol[symbol] = returns

    matrix: List[List[float]] = []
    heatmap: List[List[float]] = []
    pairs: List[Dict[str, Any]] = []

    for row_index, symbol_a in enumerate(unique_symbols):
        row: List[float] = []
        for col_index, symbol_b in enumerate(unique_symbols):
            if row_index == col_index:
                correlation = 1.0
            else:
                correlation = float(np.corrcoef(returns_by_symbol[symbol_a], returns_by_symbol[symbol_b])[0, 1])
                if not np.isfinite(correlation):
                    correlation = 0.0
            correlation = round(correlation, 4)
            row.append(correlation)
            heatmap.append([col_index, row_index, correlation])
            if row_index < col_index:
                pairs.append({
                    "pair": f"{symbol_a} / {symbol_b}",
                    "symbol_a": symbol_a,
                    "symbol_b": symbol_b,
                    "correlation": correlation,
                })
        matrix.append(row)

    pairs_sorted = sorted(pairs, key=lambda item: item["correlation"], reverse=True)
    lowest_pairs = sorted(pairs, key=lambda item: item["correlation"])

    return DataResponse(data={
        "symbols": unique_symbols,
        "matrix": matrix,
        "heatmap": heatmap,
        "aligned_points": len(common_timestamps),
        "timeframe": request.timeframe.value,
        "inst_type": request.inst_type.value,
        "days": request.days,
        "top_positive": pairs_sorted[:5],
        "top_negative": lowest_pairs[:5],
    })
