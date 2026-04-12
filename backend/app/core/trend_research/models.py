from dataclasses import dataclass

from .direct_models import DirectExtremaMetrics, DirectExtremaModelBundle, DirectExtremaModelConfig


@dataclass(frozen=True)
class FeatureBar1s:
    """统一 1 秒特征条的最小模型。"""

    inst_id: str
    ts_exchange: float
    ts_local: float
    second_bucket: int
    mid_price: float
    mark_price: float
    index_price: float
    spread_bps: float
    signed_trade_notional: float
    trade_count: int
    oi_delta: float
    basis_zscore: float
    data_quality: str
    bid_price: float = 0.0
    ask_price: float = 0.0
    bid_size: float = 0.0
    ask_size: float = 0.0
    buy_notional: float = 0.0
    sell_notional: float = 0.0
    buy_count: int = 0
    sell_count: int = 0
    max_trade_notional: float = 0.0
    buy_burst_count: int = 0
    sell_burst_count: int = 0
    buy_burst_notional: float = 0.0
    sell_burst_notional: float = 0.0
    open_price: float = 0.0
    high_price: float = 0.0
    low_price: float = 0.0
    close_price: float = 0.0
    microprice: float = 0.0
    basis_bps: float = 0.0
    open_interest: float = 0.0
    funding_rate: float = 0.0
    funding_delta: float = 0.0
    premium: float = 0.0
    book_level_count: int = 0
    multi_level_book_imbalance: float = 0.0
    book_slope: float = 0.0


@dataclass(frozen=True)
class TradeTickEvent:
    """逐笔成交事件。"""

    inst_id: str
    ts_exchange: float
    ts_local: float
    price: float
    size: float
    side: str


@dataclass(frozen=True)
class BookTopEvent:
    """盘口顶层事件。"""

    inst_id: str
    ts_exchange: float
    ts_local: float
    bid_price: float
    ask_price: float
    bid_size: float
    ask_size: float
    bid_levels: tuple[tuple[float, float], ...] = ()
    ask_levels: tuple[tuple[float, float], ...] = ()


@dataclass(frozen=True)
class ContractStateSnapshot:
    """合约状态快照。"""

    inst_id: str
    ts_exchange: float
    ts_local: float
    mark_price: float
    index_price: float
    open_interest: float
    funding_rate: float
    premium: float


@dataclass(frozen=True)
class SwingLabel:
    """离线波段标签的最小模型。"""

    inst_id: str
    second_bucket: int
    trend_state: str
    swing_top_confirmed: bool
    swing_bottom_confirmed: bool
    time_to_top: int
    time_to_bottom: int


@dataclass(frozen=True)
class ExtremaTarget:
    """未来窗口的顶底事件标签。"""

    inst_id: str
    second_bucket: int
    horizon_minutes: int
    realized_volatility: float
    reversal_threshold: float
    top_event: bool
    bottom_event: bool
    time_to_top_seconds: int | None
    time_to_bottom_seconds: int | None
    top_forward_return: float
    bottom_forward_return: float
    top_reversal_return: float
    bottom_reversal_return: float


@dataclass(frozen=True)
class CandidateFactorSeries:
    """单个候选因子的序列样本。"""

    inst_id: str
    factor_name: str
    values: list[float]
    category: str = ""
    tier: int = 0


@dataclass(frozen=True)
class FactorScore:
    """单因子排序结果。"""

    inst_id: str
    factor_name: str
    spearman_ic: float | None
    stability_score: float | None
    redundancy_cluster: str
    category: str = ""
    tier: int = 0
    available: bool = True
    unavailable_reason: str = ""


@dataclass(frozen=True)
class SelectedFeatureStats:
    """入模特征及其训练期统计量。"""

    name: str
    category: str
    mean: float
    std: float
    coverage: float
    spearman_ic: float
    stability_score: float


@dataclass(frozen=True)
class FeatureSelectionResult:
    """特征筛选输出。"""

    features: tuple[SelectedFeatureStats, ...]

    @property
    def feature_names(self) -> tuple[str, ...]:
        return tuple(feature.name for feature in self.features)

    @property
    def train_means(self) -> tuple[float, ...]:
        return tuple(feature.mean for feature in self.features)

    @property
    def train_stds(self) -> tuple[float, ...]:
        return tuple(feature.std for feature in self.features)


@dataclass(frozen=True)
class LogisticModelHead:
    """二分类逻辑回归单头。"""

    weights: tuple[float, ...]
    intercept: float
    positive_class_weight: float
    negative_class_weight: float


@dataclass(frozen=True)
class BinaryClassificationMetrics:
    """二分类验证指标。"""

    accuracy: float
    log_loss: float
    positive_rate: float


@dataclass(frozen=True)
class TimeOrderedSplit:
    """按时间顺序切分的训练/验证/测试索引。"""

    train_indices: tuple[int, ...]
    validation_indices: tuple[int, ...]
    test_indices: tuple[int, ...]


@dataclass(frozen=True)
class TrendModelBundle:
    """趋势研究双头模型 bundle。"""

    trained_at: str
    horizon_minutes: int
    reversal_threshold_floor: float
    feature_names: tuple[str, ...]
    train_means: tuple[float, ...]
    train_stds: tuple[float, ...]
    top_head: LogisticModelHead
    bottom_head: LogisticModelHead
    top_validation: BinaryClassificationMetrics
    bottom_validation: BinaryClassificationMetrics
    top_test: BinaryClassificationMetrics
    bottom_test: BinaryClassificationMetrics


@dataclass(frozen=True)
class TrendInferenceSnapshot:
    """实时趋势推断快照。"""

    inst_id: str
    second_bucket: int
    trend_score: float
    trend_state: str
    confidence: float
    data_quality: str
    current_price: float = 0.0
    predicted_top_eta_seconds: int | None = None
    predicted_bottom_eta_seconds: int | None = None
    predicted_top_price: float | None = None
    predicted_bottom_price: float | None = None
    predicted_top_return: float | None = None
    predicted_bottom_return: float | None = None
    top_time_distribution: tuple[float, ...] = ()
    bottom_time_distribution: tuple[float, ...] = ()
    top_probability: float = 0.0
    bottom_probability: float = 0.0


@dataclass(frozen=True)
class FeatureBuilderRuntimeSnapshot:
    """单个 builder 当前的采集运行态快照。"""

    inst_id: str
    has_trade_input: bool
    has_book_input: bool
    has_contract_state: bool
    pending_trade_count: int
    last_trade_ts_local: float | None
    last_book_ts_local: float | None
    last_state_ts_local: float | None
    last_trade_price: float
    last_trade_side: str
