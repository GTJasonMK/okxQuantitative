from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..models.schemas import InstTypeEnum

AgentInstTypeEnum = InstTypeEnum


class AgentModeEnum(str, Enum):
    SIMULATED = "simulated"
    LIVE = "live"


class AgentCapabilityDescriptor(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., description="能力名称")
    kind: str = Field(..., description="能力类型：query/analysis")
    goal: str = Field(..., description="能力目标")
    side_effect_free: bool = Field(default=True, description="是否无副作用")
    risk_level: str = Field(default="low", description="风险等级")
    input_example: Dict[str, Any] = Field(default_factory=dict, description="输入示例")
    output_summary: Dict[str, Any] = Field(default_factory=dict, description="输出摘要")


class AgentMarketQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inst_id: str = Field(..., description="交易对，如 BTC-USDT 或 BTC-USDT-SWAP")
    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="交易类型")


class AgentCandleQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inst_id: str = Field(..., description="交易对")
    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="交易类型")
    timeframes: List[str] = Field(
        default_factory=lambda: ["1H"],
        description="K线周期列表，如 1m/5m/1H/4H/1D",
    )
    limit: int = Field(default=300, ge=20, le=5000, description="每个周期返回的 K 线数量")
    start_time: Optional[str] = Field(default=None, description="开始时间（ISO8601）")
    end_time: Optional[str] = Field(default=None, description="结束时间（ISO8601）")
    auto_sync: bool = Field(default=True, description="是否允许本地缺失时自动同步")

    @field_validator("timeframes")
    @classmethod
    def validate_timeframes(cls, value: List[str]) -> List[str]:
        cleaned = [str(item or "").strip() for item in value if str(item or "").strip()]
        if not cleaned:
            raise ValueError("timeframes 不能为空")
        return cleaned


class AgentTradingContextRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inst_id: str = Field(..., description="交易对")
    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="交易类型")
    timeframes: List[str] = Field(
        default_factory=lambda: ["5m", "1H", "4H"],
        description="需要聚合的 K 线周期列表",
    )
    candles_limit: int = Field(default=240, ge=20, le=5000, description="每个周期返回的 K 线数量")
    indicators: List[str] = Field(
        default_factory=lambda: ["ma5", "ma20", "macd", "rsi", "volume_ma20"],
        description="每个周期需要预计算的指标列表",
    )
    include_orderbook: bool = Field(default=True, description="是否附带盘口快照")
    orderbook_depth: int = Field(default=50, ge=1, le=500, description="盘口档位数")
    include_recent_trades: bool = Field(default=True, description="是否附带最新逐笔成交")
    recent_trade_limit: int = Field(default=50, ge=1, le=100, description="逐笔成交数量")
    include_position: bool = Field(default=False, description="是否附带账户持仓摘要")
    mode: AgentModeEnum = Field(default=AgentModeEnum.SIMULATED, description="账户模式")
    auto_sync: bool = Field(default=True, description="是否允许本地缺失时自动同步")

    @field_validator("timeframes")
    @classmethod
    def validate_context_timeframes(cls, value: List[str]) -> List[str]:
        cleaned = [str(item or "").strip() for item in value if str(item or "").strip()]
        if not cleaned:
            raise ValueError("timeframes 不能为空")
        return cleaned

    @field_validator("indicators")
    @classmethod
    def validate_context_indicators(cls, value: List[str]) -> List[str]:
        cleaned = [str(item or "").strip() for item in value if str(item or "").strip()]
        if not cleaned:
            raise ValueError("indicators 不能为空")
        return cleaned


class AgentIndicatorQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inst_id: str = Field(..., description="交易对")
    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="交易类型")
    timeframe: str = Field(default="1H", description="K线周期")
    indicators: List[str] = Field(
        default_factory=lambda: ["ma5", "ma20", "macd"],
        description="指标列表，如 ma5、ema12、macd、bollinger、rsi",
    )
    limit: int = Field(default=300, ge=20, le=5000, description="计算指标时使用的 K 线数量")
    auto_sync: bool = Field(default=True, description="是否允许本地缺失时自动同步")

    @field_validator("indicators")
    @classmethod
    def validate_indicators(cls, value: List[str]) -> List[str]:
        cleaned = [str(item or "").strip() for item in value if str(item or "").strip()]
        if not cleaned:
            raise ValueError("indicators 不能为空")
        return cleaned


class AgentWatchlistScanRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="扫描的市场类型")
    limit: int = Field(default=30, ge=1, le=200, description="最多扫描多少个关注币种")
    timeframes: List[str] = Field(
        default_factory=lambda: ["1H", "4H"],
        description="用于趋势扫描的周期列表",
    )
    candles_limit: int = Field(default=200, ge=20, le=2000, description="每个周期读取的 K 线数量")
    indicators: List[str] = Field(
        default_factory=lambda: ["ma20", "rsi", "macd"],
        description="用于扫描的指标列表",
    )
    include_orderbook: bool = Field(default=False, description="是否扫描盘口失衡")
    orderbook_depth: int = Field(default=20, ge=1, le=200, description="盘口档位数")
    sort_by: str = Field(default="signal_score", description="排序字段：signal_score/change_24h/volume_24h")

    @field_validator("timeframes")
    @classmethod
    def validate_scan_timeframes(cls, value: List[str]) -> List[str]:
        cleaned = [str(item or "").strip() for item in value if str(item or "").strip()]
        if not cleaned:
            raise ValueError("timeframes 不能为空")
        return cleaned

    @field_validator("indicators")
    @classmethod
    def validate_scan_indicators(cls, value: List[str]) -> List[str]:
        cleaned = [str(item or "").strip() for item in value if str(item or "").strip()]
        if not cleaned:
            raise ValueError("indicators 不能为空")
        return cleaned

    @field_validator("sort_by")
    @classmethod
    def validate_sort_by(cls, value: str) -> str:
        cleaned = str(value or "").strip() or "signal_score"
        if cleaned not in {"signal_score", "change_24h", "volume_24h"}:
            raise ValueError("sort_by 仅支持 signal_score/change_24h/volume_24h")
        return cleaned


class AgentOrderBookQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inst_id: str = Field(..., description="交易对")
    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="交易类型")
    depth: int = Field(default=50, ge=1, le=500, description="盘口档位数")


class AgentRecentTradesQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inst_id: str = Field(..., description="交易对")
    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="交易类型")
    limit: int = Field(default=50, ge=1, le=100, description="逐笔成交数量")


class AgentPositionQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    mode: AgentModeEnum = Field(default=AgentModeEnum.SIMULATED, description="账户模式")


class AgentDataHealthQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbol: str = Field(default="", description="基础币对，如 BTC-USDT；为空时返回全部")
    include_orphans: bool = Field(default=True, description="是否包含未关注孤儿数据")


class AgentAlignmentQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inst_id: str = Field(..., description="交易对")
    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="交易类型")
    timeframes: List[str] = Field(
        default_factory=lambda: ["1m", "5m", "1H", "4H", "1D"],
        description="参与联动分析的周期列表",
    )
    limit: int = Field(default=240, ge=20, le=5000, description="每个周期读取的 K 线数量")
    auto_sync: bool = Field(default=True, description="是否允许本地缺失时自动同步")

    @field_validator("timeframes")
    @classmethod
    def validate_alignment_timeframes(cls, value: List[str]) -> List[str]:
        cleaned = [str(item or "").strip() for item in value if str(item or "").strip()]
        if not cleaned:
            raise ValueError("timeframes 不能为空")
        return cleaned


class AgentMarketStructureRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inst_id: str = Field(..., description="交易对")
    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="交易类型")
    timeframes: List[str] = Field(
        default_factory=lambda: ["5m", "1H", "4H"],
        description="结构化分析用的周期列表",
    )
    limit: int = Field(default=240, ge=20, le=5000, description="每个周期读取的 K 线数量")
    orderbook_depth: int = Field(default=50, ge=1, le=500, description="盘口档位数")
    recent_trade_limit: int = Field(default=50, ge=1, le=100, description="逐笔成交数量")
    mode: AgentModeEnum = Field(default=AgentModeEnum.SIMULATED, description="账户模式")
    auto_sync: bool = Field(default=True, description="是否允许本地缺失时自动同步")

    @field_validator("timeframes")
    @classmethod
    def validate_market_structure_timeframes(cls, value: List[str]) -> List[str]:
        cleaned = [str(item or "").strip() for item in value if str(item or "").strip()]
        if not cleaned:
            raise ValueError("timeframes 不能为空")
        return cleaned


class AgentSupportResistanceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inst_id: str = Field(..., description="交易对")
    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="交易类型")
    timeframes: List[str] = Field(
        default_factory=lambda: ["1H", "4H", "1D"],
        description="用于识别关键位的周期列表",
    )
    limit: int = Field(default=360, ge=60, le=5000, description="每个周期加载的 K 线数量")
    max_levels_per_side: int = Field(default=4, ge=1, le=8, description="每侧最多返回多少个关键位")
    cluster_tolerance_bps: float = Field(default=35.0, ge=1.0, le=500.0, description="聚类容忍度，单位 bps")
    auto_sync: bool = Field(default=True, description="是否允许本地缺失时自动同步")

    @field_validator("timeframes")
    @classmethod
    def validate_support_resistance_timeframes(cls, value: List[str]) -> List[str]:
        cleaned = [str(item or "").strip() for item in value if str(item or "").strip()]
        if not cleaned:
            raise ValueError("timeframes 不能为空")
        return cleaned


class AgentPriceProjectionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inst_id: str = Field(..., description="交易对")
    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="交易类型")
    timeframe: str = Field(default="1H", description="投影使用的主周期")
    limit: int = Field(default=240, ge=60, le=5000, description="加载的 K 线数量")
    horizon_bars: int = Field(default=24, ge=3, le=240, description="预测前瞻 bar 数")
    auto_sync: bool = Field(default=True, description="是否允许本地缺失时自动同步")


class AgentOpportunityPatrolRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="巡检市场类型")
    scan_limit: int = Field(default=20, ge=1, le=200, description="先扫描多少个关注币种")
    candidate_limit: int = Field(default=5, ge=1, le=20, description="最终输出多少个候选机会")
    timeframes: List[str] = Field(
        default_factory=lambda: ["1H", "4H"],
        description="巡检用的周期列表",
    )
    candles_limit: int = Field(default=240, ge=60, le=2000, description="扫描时每个周期读取的 K 线数量")
    recent_trade_limit: int = Field(default=40, ge=1, le=100, description="逐笔成交数量")
    orderbook_depth: int = Field(default=30, ge=1, le=200, description="盘口档位数")
    mode: AgentModeEnum = Field(default=AgentModeEnum.SIMULATED, description="账户模式")

    @field_validator("timeframes")
    @classmethod
    def validate_opportunity_patrol_timeframes(cls, value: List[str]) -> List[str]:
        cleaned = [str(item or "").strip() for item in value if str(item or "").strip()]
        if not cleaned:
            raise ValueError("timeframes 不能为空")
        return cleaned


class AgentRiskBudgetRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inst_id: str = Field(..., description="交易对")
    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="交易类型")
    mode: AgentModeEnum = Field(default=AgentModeEnum.SIMULATED, description="账户模式")
    side: str = Field(default="buy", description="预期方向 buy/sell")
    entry_price: Optional[float] = Field(default=None, ge=0, description="预期入场价，为空则自动取最新价")
    stop_loss_ratio: Optional[float] = Field(default=None, ge=0, le=1, description="止损比例")
    max_single_loss_ratio: Optional[float] = Field(default=None, ge=0, le=1, description="覆盖默认单笔风险上限")
    max_total_position_ratio: Optional[float] = Field(default=None, ge=0, le=10, description="覆盖默认总仓位上限")
    proposed_size: Optional[float] = Field(default=None, ge=0, description="可选：给定拟下单数量时顺带评估")

    @field_validator("side")
    @classmethod
    def validate_side(cls, value: str) -> str:
        cleaned = str(value or "").strip().lower() or "buy"
        if cleaned not in {"buy", "sell"}:
            raise ValueError("side 仅支持 buy/sell")
        return cleaned


class AgentTradeSetupRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inst_id: str = Field(..., description="交易对")
    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="交易类型")
    mode: AgentModeEnum = Field(default=AgentModeEnum.SIMULATED, description="账户模式")
    side_preference: str = Field(default="auto", description="方向偏好：auto/buy/sell")
    structure_timeframes: List[str] = Field(
        default_factory=lambda: ["15m", "1H", "4H"],
        description="用于结构判断的周期列表",
    )
    level_timeframes: List[str] = Field(
        default_factory=lambda: ["1H", "4H", "1D"],
        description="用于关键位识别的周期列表",
    )
    projection_timeframe: str = Field(default="1H", description="未来路径推演使用的主周期")
    candles_limit: int = Field(default=240, ge=60, le=5000, description="分析使用的 K 线数量")
    orderbook_depth: int = Field(default=50, ge=1, le=500, description="盘口档位数")
    recent_trade_limit: int = Field(default=50, ge=1, le=100, description="逐笔成交数量")
    stop_loss_ratio: Optional[float] = Field(default=None, ge=0, le=1, description="可选：覆盖默认止损比例")
    auto_sync: bool = Field(default=True, description="是否允许本地缺失时自动同步")

    @field_validator("side_preference")
    @classmethod
    def validate_side_preference(cls, value: str) -> str:
        cleaned = str(value or "").strip().lower() or "auto"
        if cleaned not in {"auto", "buy", "sell"}:
            raise ValueError("side_preference 仅支持 auto/buy/sell")
        return cleaned

    @field_validator("structure_timeframes", "level_timeframes")
    @classmethod
    def validate_trade_setup_timeframes(cls, value: List[str]) -> List[str]:
        cleaned = [str(item or "").strip() for item in value if str(item or "").strip()]
        if not cleaned:
            raise ValueError("timeframes 不能为空")
        return cleaned


class AgentCorrelationQueryRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    symbols: List[str] = Field(default_factory=list, description="要分析的交易对列表；为空时可从关注列表自动读取")
    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="交易类型")
    timeframe: str = Field(default="4H", description="计算相关性的周期")
    limit: int = Field(default=240, ge=20, le=5000, description="每个交易对加载的 K 线数量")
    use_watchlist_if_empty: bool = Field(default=True, description="当 symbols 为空时是否自动读取关注列表")
    auto_sync: bool = Field(default=True, description="是否允许本地缺失时自动同步")

    @field_validator("symbols")
    @classmethod
    def validate_symbols(cls, value: List[str]) -> List[str]:
        return [str(item or "").strip() for item in value if str(item or "").strip()]


class AgentOrderDraftRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(default="", description="关联的 assistant 会话 ID，可为空")
    inst_id: str = Field(..., description="交易对")
    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="交易类型")
    mode: AgentModeEnum = Field(default=AgentModeEnum.SIMULATED, description="账户模式")
    side_preference: str = Field(default="auto", description="方向偏好：auto/buy/sell")
    order_type: str = Field(default="limit", description="订单类型：limit/market")
    td_mode: str = Field(default="cash", description="交易模式，如 cash / cross / isolated")
    pos_side: str = Field(default="", description="合约持仓方向 long/short/net")
    reduce_only: bool = Field(default=False, description="是否仅减仓")
    size: Optional[float] = Field(default=None, ge=0, description="草案数量；为空则自动使用预算建议值")
    price: Optional[float] = Field(default=None, ge=0, description="草案委托价；为空则自动参考交易计划")
    stop_loss_ratio: Optional[float] = Field(default=None, ge=0, le=1, description="可选：覆盖默认止损比例")
    title: str = Field(default="", description="草案标题")
    note: str = Field(default="", description="草案备注")
    auto_sync: bool = Field(default=True, description="是否允许本地缺失时自动同步")

    @field_validator("side_preference")
    @classmethod
    def validate_draft_side_preference(cls, value: str) -> str:
        cleaned = str(value or "").strip().lower() or "auto"
        if cleaned not in {"auto", "buy", "sell"}:
            raise ValueError("side_preference 仅支持 auto/buy/sell")
        return cleaned

    @field_validator("order_type")
    @classmethod
    def validate_order_type(cls, value: str) -> str:
        cleaned = str(value or "").strip().lower() or "limit"
        if cleaned not in {"limit", "market"}:
            raise ValueError("order_type 仅支持 limit/market")
        return cleaned


class AgentOrderDraftListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(default="", description="按会话过滤")
    inst_id: str = Field(default="", description="按交易对过滤")
    status: str = Field(default="", description="按状态过滤：draft/confirmed/cancelled")
    limit: int = Field(default=30, ge=1, le=200, description="返回数量上限")


class AgentOrderDraftConfirmRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    draft_id: str = Field(..., description="草案 ID")


class AgentLevelSnapshotRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(default="", description="关联的 assistant 会话 ID，可为空")
    source: str = Field(default="assistant", description="来源，如 assistant/manual")
    title: str = Field(default="", description="快照标题")
    note: str = Field(default="", description="快照备注")
    inst_id: str = Field(..., description="交易对")
    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="交易类型")
    timeframes: List[str] = Field(
        default_factory=lambda: ["1H", "4H", "1D"],
        description="用于识别关键位的周期列表",
    )
    limit: int = Field(default=360, ge=60, le=5000, description="每个周期加载的 K 线数量")
    max_levels_per_side: int = Field(default=4, ge=1, le=8, description="每侧最多返回多少个关键位")
    cluster_tolerance_bps: float = Field(default=35.0, ge=1.0, le=500.0, description="聚类容忍度，单位 bps")
    auto_sync: bool = Field(default=True, description="是否允许本地缺失时自动同步")

    @field_validator("timeframes")
    @classmethod
    def validate_level_snapshot_timeframes(cls, value: List[str]) -> List[str]:
        cleaned = [str(item or "").strip() for item in value if str(item or "").strip()]
        if not cleaned:
            raise ValueError("timeframes 不能为空")
        return cleaned


class AgentLevelSnapshotListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    session_id: str = Field(default="", description="按会话过滤")
    inst_id: str = Field(default="", description="按交易对过滤")
    source: str = Field(default="", description="按来源过滤")
    limit: int = Field(default=30, ge=1, le=200, description="返回数量上限")


class AgentPatrolRunListRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    inst_type: str = Field(default="", description="按市场类型过滤")
    mode: str = Field(default="", description="按 simulated/live 过滤")
    trigger: str = Field(default="", description="按 scheduled/manual 过滤")
    limit: int = Field(default=30, ge=1, le=200, description="返回数量上限")


class AgentPythonAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(default="", description="本次分析目标")
    inst_id: str = Field(..., description="交易对")
    inst_type: AgentInstTypeEnum = Field(default=AgentInstTypeEnum.SPOT, description="交易类型")
    timeframes: List[str] = Field(
        default_factory=lambda: ["1H"],
        description="需要装载的 K 线周期列表",
    )
    candles_limit: int = Field(default=300, ge=20, le=5000, description="每个周期装载的 K 线数量")
    indicators: List[str] = Field(default_factory=list, description="需要预计算的指标列表")
    include_market_snapshot: bool = Field(default=True, description="是否附带最新行情快照")
    include_orderbook: bool = Field(default=True, description="是否附带盘口快照")
    orderbook_depth: int = Field(default=50, ge=1, le=500, description="盘口深度")
    include_recent_trades: bool = Field(default=False, description="是否附带最新逐笔成交")
    recent_trade_limit: int = Field(default=50, ge=1, le=100, description="逐笔成交数量")
    include_position: bool = Field(default=False, description="是否附带账户持仓快照")
    mode: AgentModeEnum = Field(default=AgentModeEnum.SIMULATED, description="账户模式")
    timeout_seconds: int = Field(default=12, ge=3, le=20, description="沙箱执行超时秒数")
    code: str = Field(..., min_length=20, max_length=20000, description="需要定义 analyze(data, helpers) 的 Python 代码")

    @field_validator("timeframes")
    @classmethod
    def validate_analysis_timeframes(cls, value: List[str]) -> List[str]:
        cleaned = [str(item or "").strip() for item in value if str(item or "").strip()]
        if not cleaned:
            raise ValueError("timeframes 不能为空")
        return cleaned


class AgentAnalysisResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    summary: Any = Field(default=None, description="分析摘要")
    metrics: Dict[str, Any] = Field(default_factory=dict, description="结构化指标")
    tables: Dict[str, Any] = Field(default_factory=dict, description="表格数据")
    artifacts: Dict[str, Any] = Field(default_factory=dict, description="附加工件")
    logs: List[str] = Field(default_factory=list, description="执行日志")
    warnings: List[str] = Field(default_factory=list, description="警告信息")
    dataset_overview: Dict[str, Any] = Field(default_factory=dict, description="本次分析使用的数据概览")
