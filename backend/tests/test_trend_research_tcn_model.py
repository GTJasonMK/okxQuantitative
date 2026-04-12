import pytest

import app.core.trend_research.tcn_model as tcn_model


def test_direct_extrema_tcn_requires_torch_when_dependency_is_missing():
    if tcn_model.TORCH_AVAILABLE:
        pytest.skip("torch is installed in this environment")

    with pytest.raises(RuntimeError, match="PyTorch is required for direct extrema TCN"):
        tcn_model.DirectExtremaTCN(
            input_dim=6,
            hidden_channels=(32, 64),
            horizon_buckets=60,
            dropout=0.1,
        )


def test_direct_extrema_tcn_outputs_time_logits_and_returns():
    if not tcn_model.TORCH_AVAILABLE:
        pytest.skip("torch is not installed in this environment")

    torch = tcn_model.torch
    model = tcn_model.DirectExtremaTCN(
        input_dim=6,
        hidden_channels=(32, 64),
        horizon_buckets=60,
        dropout=0.1,
    )
    outputs = model(torch.randn(4, 120, 6))

    assert outputs["top_time_logits"].shape == (4, 60)
    assert outputs["bottom_time_logits"].shape == (4, 60)
    assert outputs["top_return"].shape == (4,)
    assert outputs["bottom_return"].shape == (4,)
