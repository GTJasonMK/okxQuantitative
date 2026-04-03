# 数据模型定义
# 使用Pydantic定义API请求和响应的数据结构

from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field, ConfigDict


# ==================== 枚举类型 ====================

class InstTypeEnum(str, Enum):
    """交易品种类型"""
    SPOT = "SPOT"
    SWAP = "SWAP"
    FUTURES = "FUTURES"
    OPTION = "OPTION"


class TimeframeEnum(str, Enum):
    """K线时间周期"""
    M1 = "1m"
    M3 = "3m"
    M5 = "5m"
    M15 = "15m"
    M30 = "30m"
    H1 = "1H"
    H2 = "2H"
    H4 = "4H"
    H6 = "6H"
    H12 = "12H"
    D1 = "1D"
    W1 = "1W"
    MO1 = "1M"


class SyncModeEnum(str, Enum):
    """数据同步模式"""
    WINDOW = "window"
    INCREMENTAL = "incremental"
    FULL = "full"


# ==================== 基础响应模型 ====================

class BaseResponse(BaseModel):
    """基础响应模型"""
    code: int = Field(default=0, description="状态码，0表示成功")
    message: str = Field(default="success", description="响应消息")


class DataResponse(BaseResponse):
    """带数据的响应模型"""
    data: Any = Field(default=None, description="响应数据")


# ==================== K线数据模型 ====================

class CandleModel(BaseModel):
    """K线数据模型"""
    timestamp: int = Field(..., description="时间戳（毫秒）")
    datetime: str = Field(..., description="日期时间字符串")
    open: float = Field(..., description="开盘价")
    high: float = Field(..., description="最高价")
    low: float = Field(..., description="最低价")
    close: float = Field(..., description="收盘价")
    volume: float = Field(..., description="成交量")
    volume_ccy: float = Field(default=0, description="成交额")

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "timestamp": 1704067200000,
                "datetime": "2024-01-01T00:00:00",
                "open": 42000.5,
                "high": 42500.0,
                "low": 41800.0,
                "close": 42300.0,
                "volume": 1234.56,
                "volume_ccy": 52000000.0,
            }
        }
    )


class CandleListResponse(BaseResponse):
    """K线列表响应"""
    data: List[CandleModel] = Field(default_factory=list, description="K线数据列表")
    total: int = Field(default=0, description="数据总数")


# ==================== 行情数据模型 ====================

class TickerModel(BaseModel):
    """实时行情模型"""
    inst_id: str = Field(..., description="交易对")
    last: float = Field(..., description="最新价")
    last_sz: float = Field(default=0, description="最新一笔成交量")
    ask_px: float = Field(default=0, description="卖一价")
    bid_px: float = Field(default=0, description="买一价")
    open_24h: float = Field(default=0, description="24小时开盘价")
    high_24h: float = Field(default=0, description="24小时最高价")
    low_24h: float = Field(default=0, description="24小时最低价")
    vol_24h: float = Field(default=0, description="24小时成交量")
    change_24h: float = Field(default=0, description="24小时涨跌幅(%)")
    timestamp: int = Field(..., description="时间戳")


class TickerResponse(BaseResponse):
    """行情响应"""
    data: Optional[TickerModel] = None


class TickerListResponse(BaseResponse):
    """行情列表响应"""
    data: List[TickerModel] = Field(default_factory=list, description="行情列表")


# ==================== 交易对模型 ====================

class InstrumentModel(BaseModel):
    """交易产品信息"""
    inst_id: str = Field(..., description="交易对ID")
    base_ccy: str = Field(default="", description="基础货币")
    quote_ccy: str = Field(default="", description="计价货币")
    tick_sz: str = Field(default="", description="最小价格单位")
    lot_sz: str = Field(default="", description="最小交易数量")
    min_sz: str = Field(default="", description="最小下单数量")
    state: str = Field(default="", description="状态")


class InstrumentListResponse(BaseResponse):
    """交易产品列表响应"""
    data: List[InstrumentModel] = Field(default_factory=list, description="交易产品列表")


# ==================== 技术指标模型 ====================

class IndicatorRequest(BaseModel):
    """指标计算请求"""
    inst_id: str = Field(..., description="交易对")
    inst_type: InstTypeEnum = Field(default=InstTypeEnum.SPOT, description="交易类型")
    timeframe: TimeframeEnum = Field(default=TimeframeEnum.H1, description="时间周期")
    indicators: List[str] = Field(
        default_factory=lambda: ["ma5", "ma20", "macd"],
        description="要计算的指标列表"
    )
    limit: int = Field(default=100, ge=1, le=1000, description="K线数量")


class IndicatorData(BaseModel):
    """指标数据"""
    name: str = Field(..., description="指标名称")
    values: List[Optional[float]] = Field(..., description="指标值")
    params: Dict[str, Any] = Field(default_factory=dict, description="指标参数")


class IndicatorResponse(BaseResponse):
    """指标响应"""
    data: Dict[str, Any] = Field(default_factory=dict, description="指标数据")
    candles: List[CandleModel] = Field(default_factory=list, description="K线数据")


# ==================== 数据同步模型 ====================

class SyncRequest(BaseModel):
    """数据同步请求"""
    inst_id: str = Field(..., description="交易对")
    timeframe: TimeframeEnum = Field(default=TimeframeEnum.H1, description="时间周期")
    days: int = Field(default=30, ge=1, le=365, description="同步天数")
    inst_type: InstTypeEnum = Field(default=InstTypeEnum.SPOT, description="交易类型")
    mode: SyncModeEnum = Field(
        default=SyncModeEnum.WINDOW,
        description="同步模式：window=最近N天，incremental=仅补最新缺口，full=回补到最早可获取历史",
    )


class SyncStatusModel(BaseModel):
    """同步状态"""
    inst_id: str
    inst_type: str
    timeframe: str
    last_sync_time: Optional[str]
    oldest_time: Optional[str]
    newest_time: Optional[str]
    candle_count: int
    history_complete: bool = False
    last_sync_mode: str = "window"


class SyncStatusResponse(BaseResponse):
    """同步状态响应"""
    data: List[SyncStatusModel] = Field(default_factory=list, description="同步状态列表")


class SyncJobStatusModel(BaseModel):
    """后台同步任务状态"""
    task_id: str
    inst_id: str
    inst_type: str
    timeframe: str
    mode: str
    days: int
    status: str
    progress: int = 0
    message: str = ""
    created_at: str
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: str = ""
    fetched_count: int = 0
    saved_count: int = 0
    batches: int = 0
    api_calls: int = 0
    candle_count: int = 0
    history_complete: bool = False
    last_sync_mode: str = "window"
    last_sync_time: Optional[str] = None
    oldest_time: Optional[str] = None
    newest_time: Optional[str] = None
    reused_existing: bool = False


class SyncJobStatusResponse(BaseResponse):
    """单个后台同步任务响应"""
    data: Optional[SyncJobStatusModel] = None


class SyncJobListResponse(BaseResponse):
    """后台同步任务列表响应"""
    data: List[SyncJobStatusModel] = Field(default_factory=list, description="任务列表")


# ==================== 关注币种模型 ====================

class WatchedSymbolModel(BaseModel):
    """关注币种模型"""
    symbol: str = Field(..., description="基础交易对，如 BTC-USDT")
    base_ccy: str = Field(default="", description="基础币种")
    spot_inst_id: str = Field(default="", description="现货 instId")
    swap_inst_id: str = Field(default="", description="永续 instId")
    sync_spot: bool = Field(default=True, description="是否维护现货数据")
    sync_swap: bool = Field(default=True, description="是否维护永续数据")
    archive_all_history: bool = Field(default=False, description="是否全量归档（从发行至今所有历史）")
    created_at: Optional[str] = Field(default=None, description="创建时间")
    updated_at: Optional[str] = Field(default=None, description="更新时间")


class WatchedSymbolCreateRequest(BaseModel):
    """新增关注币种请求"""
    symbol: str = Field(..., description="基础交易对或币种代码，如 BTC / BTC-USDT / BTC-USDT-SWAP")
    sync_spot: bool = Field(default=True, description="是否同时初始化现货数据")
    sync_swap: bool = Field(default=True, description="是否同时初始化永续数据")
    archive_all_history: bool = Field(default=False, description="是否全量归档（从发行至今所有历史）")


class WatchedSymbolCreatePayload(BaseModel):
    """新增关注币种响应数据"""
    watched_symbol: WatchedSymbolModel
    existed: bool = Field(default=False, description="是否已存在")
    sync_jobs: List[SyncJobStatusModel] = Field(default_factory=list, description="已创建的后台同步任务")
    sync_deferred: bool = Field(default=False, description="是否暂未启动同步任务")
    sync_message: str = Field(default="", description="同步状态说明")


class WatchedSymbolListResponse(BaseResponse):
    """关注币种列表响应"""
    data: List[WatchedSymbolModel] = Field(default_factory=list, description="关注币种列表")


class WatchedSymbolCreateResponse(BaseResponse):
    """新增关注币种响应"""
    data: Optional[WatchedSymbolCreatePayload] = None


class WatchedSymbolDeletePayload(BaseModel):
    """删除关注币种响应数据"""
    symbol: str = Field(..., description="被删除的基础交易对")
    deleted: bool = Field(default=True, description="是否删除成功")
    deleted_counts: Dict[str, int] = Field(default_factory=dict, description="本地数据删除统计")
    active_sync_jobs: List[SyncJobStatusModel] = Field(default_factory=list, description="删除时仍在运行的相关同步任务")


class WatchedSymbolDeleteResponse(BaseResponse):
    """删除关注币种响应"""
    data: Optional[WatchedSymbolDeletePayload] = None


# ==================== 可用交易对模型 ====================

class AvailableSymbolModel(BaseModel):
    """已有数据的交易对"""
    inst_id: str = Field(..., description="交易对")
    inst_type: str = Field(..., description="交易类型")
    timeframes: List[str] = Field(default_factory=list, description="可用时间周期")


class AvailableSymbolsResponse(BaseResponse):
    """可用交易对响应"""
    data: List[AvailableSymbolModel] = Field(default_factory=list, description="交易对列表")


# ==================== 交易日志模型 ====================

class JournalEntryCreate(BaseModel):
    """创建日志条目"""
    title: str = Field(default="", description="标题")
    content: str = Field(default="", description="内容/笔记")
    mode: str = Field(default="simulated", description="交易模式")
    inst_id: str = Field(default="", description="交易对")
    inst_type: str = Field(default="SPOT", description="交易类型")
    trade_ids: List[str] = Field(default_factory=list, description="关联成交ID")
    order_ids: List[str] = Field(default_factory=list, description="关联订单ID")
    tags: List[str] = Field(default_factory=list, description="标签")
    strategy_id: str = Field(default="", description="策略ID")
    strategy_name: str = Field(default="", description="策略名称")
    rating: int = Field(default=0, ge=0, le=5, description="自评分 1-5")
    emotion: str = Field(default="", description="情绪标记")
    screenshots: List[str] = Field(default_factory=list, description="截图（base64 或路径）")
    pnl_snapshot: float = Field(default=0.0, description="盈亏快照")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="扩展数据")


class JournalEntryUpdate(BaseModel):
    """更新日志条目（所有字段可选）"""
    title: Optional[str] = None
    content: Optional[str] = None
    mode: Optional[str] = None
    inst_id: Optional[str] = None
    inst_type: Optional[str] = None
    trade_ids: Optional[List[str]] = None
    order_ids: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    strategy_id: Optional[str] = None
    strategy_name: Optional[str] = None
    rating: Optional[int] = Field(default=None, ge=0, le=5)
    emotion: Optional[str] = None
    screenshots: Optional[List[str]] = None
    pnl_snapshot: Optional[float] = None
    metadata: Optional[Dict[str, Any]] = None
