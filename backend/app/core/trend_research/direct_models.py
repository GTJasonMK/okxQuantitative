from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class DirectExtremaModelConfig:
    """直接预测未来顶底的模型配置。"""

    architecture: str
    input_minutes: int
    horizon_minutes: int
    bucket_seconds: int
    hidden_channels: tuple[int, ...]
    dropout: float
    feature_names: tuple[str, ...]


@dataclass(frozen=True)
class DirectExtremaMetrics:
    """直接顶底预测模型的核心评估指标。"""

    top_time_mae_minutes: float
    bottom_time_mae_minutes: float
    top_price_mae_bps: float
    bottom_price_mae_bps: float
    joint_hit_rate: float


@dataclass(frozen=True)
class DirectExtremaModelBundle:
    """直接顶底预测模型的持久化 bundle。"""

    trained_at: str
    config: DirectExtremaModelConfig
    normalization_means: tuple[float, ...]
    normalization_stds: tuple[float, ...]
    state_dict: dict
    metrics: DirectExtremaMetrics


@dataclass(frozen=True)
class MinuteFeatureToken:
    """分钟级特征 token。"""

    inst_id: str
    minute_bucket: int
    current_price: float
    high_price: float
    low_price: float
    feature_values: tuple[float, ...]


@dataclass(frozen=True)
class DirectExtremaTarget:
    """未来窗口内最高点/最低点监督标签。"""

    top_time_bucket: int
    bottom_time_bucket: int
    top_price: float
    bottom_price: float
    top_return: float
    bottom_return: float


@dataclass(frozen=True)
class SequenceSample:
    """单个监督序列样本。"""

    inst_id: str
    anchor_minute_bucket: int
    feature_names: tuple[str, ...]
    feature_rows: tuple[tuple[float, ...], ...]
    current_price: float
    target: DirectExtremaTarget


@dataclass(frozen=True)
class OnlineSequenceWindow:
    """在线推断使用的最近分钟级窗口。"""

    inst_id: str
    anchor_minute_bucket: int
    feature_names: tuple[str, ...]
    feature_rows: tuple[tuple[float, ...], ...]
    current_price: float


@dataclass(frozen=True)
class DirectExtremaPrediction:
    """模型前向输出解码后的直接预测结果。"""

    top_time_bucket: int
    bottom_time_bucket: int
    top_return: float
    bottom_return: float
    top_distribution: tuple[float, ...]
    bottom_distribution: tuple[float, ...]
