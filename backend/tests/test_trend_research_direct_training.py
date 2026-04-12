import pytest

from app.core.trend_research.direct_models import (
    DirectExtremaModelConfig,
    DirectExtremaTarget,
    SequenceSample,
)
from app.core.trend_research.direct_training import TORCH_AVAILABLE, build_time_splits, train_direct_extrema_model


def _build_sample(sample_index: int) -> SequenceSample:
    feature_row = (float(sample_index), float(sample_index) / 10.0)
    return SequenceSample(
        inst_id="BTC-USDT-SWAP",
        anchor_minute_bucket=1000 + sample_index,
        feature_names=("queue_imbalance", "basis_bps"),
        feature_rows=tuple(feature_row for _ in range(120)),
        current_price=100.0,
        target=DirectExtremaTarget(
            top_time_bucket=10,
            bottom_time_bucket=40,
            top_price=110.0,
            bottom_price=90.0,
            top_return=0.09531017980432493,
            bottom_return=-0.10536051565782628,
        ),
    )


def test_build_time_splits_keeps_train_validation_test_ordered():
    splits = build_time_splits(20)

    assert splits.train_indices == tuple(range(14))
    assert splits.validation_indices == (14, 15, 16)
    assert splits.test_indices == (17, 18, 19)


def test_train_direct_extrema_model_requires_torch_when_missing():
    samples = [_build_sample(index) for index in range(8)]
    config = DirectExtremaModelConfig(
        architecture="tcn",
        input_minutes=120,
        horizon_minutes=60,
        bucket_seconds=60,
        hidden_channels=(16, 32),
        dropout=0.1,
        feature_names=("queue_imbalance", "basis_bps"),
    )

    if TORCH_AVAILABLE:
        pytest.skip("torch is installed in this environment")

    with pytest.raises(RuntimeError, match="PyTorch is required for direct extrema training"):
        train_direct_extrema_model(samples, config=config)


def test_train_direct_extrema_model_reports_epoch_progress():
    if not TORCH_AVAILABLE:
        pytest.skip("PyTorch not installed in current Windows env")

    config = DirectExtremaModelConfig(
        architecture="tcn",
        input_minutes=120,
        horizon_minutes=60,
        bucket_seconds=60,
        hidden_channels=(16, 32),
        dropout=0.1,
        feature_names=("queue_imbalance", "basis_bps"),
    )
    events = []

    bundle = train_direct_extrema_model(
        [_build_sample(index) for index in range(20)],
        config=config,
        epochs=2,
        progress_callback=lambda payload: events.append(payload),
    )

    assert bundle.metrics.joint_hit_rate >= 0.0
    assert len(events) == 2
    assert events[0]["kind"] == "epoch"
    assert events[0]["epoch"] == 1
    assert "validation_loss" in events[0]
