# 行情数据API路由
# 提供K线数据、实时行情、技术指标等接口

import asyncio
from typing import Optional, List
from datetime import datetime, timedelta
from fastapi import APIRouter, Query, HTTPException, Depends

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
    AvailableSymbolsResponse,
    DataResponse,
    TimeframeEnum,
    InstTypeEnum,
)
from ..core import (
    DataFetcher,
    DataStorage,
    IndicatorCalculator,
    InstType,
    CachedDataManager,
)
from ..core.app_context import AppContext
from .deps import get_ctx
from ..config import config, DATA_DIR


router = APIRouter(prefix="/market", tags=["行情数据"])


# ==================== 依赖注入（使用单例缓存） ====================


def get_storage(ctx: AppContext = Depends(get_ctx)) -> DataStorage:
    """获取数据存储实例（单例）"""
    try:
        return ctx.storage()
    except Exception as e:
        print(f"[依赖注入] 获取存储实例失败: {e}")
        raise HTTPException(status_code=503, detail=f"存储服务初始化失败: {str(e)}")


def get_fetcher(ctx: AppContext = Depends(get_ctx)) -> Optional[DataFetcher]:
    """获取数据获取器实例（单例）"""
    try:
        cached_fetcher = ctx.fetcher()
        return cached_fetcher.fetcher if cached_fetcher else None
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


# ==================== 实时行情接口 ====================

@router.get("/ticker/{inst_id}", response_model=TickerResponse, summary="获取单个交易对行情")
async def get_ticker(
    inst_id: str,
    fetcher: Optional[DataFetcher] = Depends(get_fetcher)
):
    """
    获取指定交易对的实时行情

    - **inst_id**: 交易对，如 BTC-USDT
    """
    if not fetcher:
        raise HTTPException(status_code=503, detail="数据服务不可用，请检查OKX API配置")

    try:
        # 使用 asyncio.to_thread 避免阻塞事件循环
        ticker = await asyncio.to_thread(fetcher.get_ticker, inst_id)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"获取行情失败: {str(e)}")

    if not ticker:
        raise HTTPException(status_code=404, detail=f"未找到交易对 {inst_id}，可能是API未配置或网络问题")

    return TickerResponse(
        data=TickerModel(
            inst_id=ticker.inst_id,
            last=ticker.last,
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
    fetcher: Optional[DataFetcher] = Depends(get_fetcher)
):
    """
    获取指定类型所有交易对的行情

    - **inst_type**: 交易类型 (SPOT/SWAP/FUTURES/OPTION)
    """
    if not fetcher:
        raise HTTPException(status_code=503, detail="数据服务不可用，请检查OKX API配置")

    try:
        # 使用 asyncio.to_thread 避免阻塞事件循环
        tickers = await asyncio.to_thread(fetcher.get_tickers, InstType(inst_type.value))
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"获取行情列表失败: {str(e)}")

    return TickerListResponse(
        data=[
            TickerModel(
                inst_id=t.inst_id,
                last=t.last,
                ask_px=t.ask_px,
                bid_px=t.bid_px,
                open_24h=t.open_24h,
                high_24h=t.high_24h,
                low_24h=t.low_24h,
                vol_24h=t.vol_24h,
                change_24h=t.change_24h,
                timestamp=t.timestamp,
            )
            for t in tickers
        ]
    )


# ==================== K线数据接口 ====================

@router.get("/candles/{inst_id}", response_model=CandleListResponse, summary="获取K线数据")
async def get_candles(
    inst_id: str,
    timeframe: TimeframeEnum = Query(default=TimeframeEnum.H1, description="时间周期"),
    limit: int = Query(default=100, ge=1, le=1000, description="数量限制"),
    start_time: Optional[str] = Query(default=None, description="开始时间 (ISO格式)"),
    end_time: Optional[str] = Query(default=None, description="结束时间 (ISO格式)"),
    source: str = Query(default="local", description="数据源: local/exchange"),
    inst_type: InstTypeEnum = Query(default=InstTypeEnum.SPOT, description="交易类型"),
    manager: CachedDataManager = Depends(get_manager)
):
    """
    获取K线数据

    - **inst_id**: 交易对
    - **timeframe**: 时间周期
    - **limit**: 返回数量
    - **source**: 数据源，local从本地获取，exchange从交易所获取
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

    if source == "local":
        # 从本地数据库获取
        if start_dt or end_dt:
            candles = await asyncio.to_thread(
                manager.storage.get_candles,
                inst_id=inst_id,
                timeframe=timeframe.value,
                start_time=start_dt,
                end_time=end_dt,
                limit=limit,
                inst_type=inst_type.value,
            )
        else:
            candles = await asyncio.to_thread(
                manager.storage.get_latest_candles,
                inst_id=inst_id,
                timeframe=timeframe.value,
                count=limit,
                inst_type=inst_type.value,
            )
    else:
        # 从交易所获取（使用 asyncio.to_thread 避免阻塞事件循环）
        if not manager.fetcher:
            raise HTTPException(status_code=503, detail="交易所数据服务不可用")
        candles = await asyncio.to_thread(
            manager.fetcher.get_candles,
            inst_id,
            timeframe.value,
            limit
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
    - **days**: 同步最近多少天的数据
    """
    if not manager.fetcher:
        raise HTTPException(status_code=503, detail="交易所数据服务不可用")

    try:
        # 使用 asyncio.to_thread 避免阻塞事件循环（同步操作包含网络请求和 time.sleep）
        count = await asyncio.to_thread(
            manager.sync_candles,
            request.inst_id,
            request.timeframe.value,
            request.days,
            request.inst_type.value
        )
        return DataResponse(data={"synced_count": count})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"同步失败: {str(e)}")


@router.get("/sync/status", response_model=SyncStatusResponse, summary="获取同步状态")
async def get_sync_status(
    storage: DataStorage = Depends(get_storage)
):
    """获取所有交易对的数据同步状态"""
    status = await asyncio.to_thread(storage.get_sync_status)
    return SyncStatusResponse(data=status)


# ==================== 交易产品接口 ====================

@router.get("/instruments", response_model=InstrumentListResponse, summary="获取交易产品列表")
async def get_instruments(
    inst_type: InstTypeEnum = Query(default=InstTypeEnum.SPOT, description="交易类型"),
    fetcher: Optional[DataFetcher] = Depends(get_fetcher)
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
