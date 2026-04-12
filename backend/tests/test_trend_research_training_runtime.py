from types import SimpleNamespace
from unittest.mock import patch

from app.core.trend_research.training_runtime import retrain_model_from_storage


def test_retrain_runtime_emits_running_and_completed_for_validation_and_save():
    progress_events = []
    bundle = SimpleNamespace(
        metrics=SimpleNamespace(
            joint_hit_rate=0.42,
            top_time_mae_minutes=4.0,
            bottom_time_mae_minutes=5.0,
        ),
        config=SimpleNamespace(feature_names=("queue_imbalance", "basis_bps")),
    )

    with (
        patch(
            "app.core.trend_research.training_runtime._collect_training_bars",
            return_value={"BTC-USDT-SWAP": ["bar"] * 256},
        ),
        patch(
            "app.core.trend_research.training_runtime._shared_feature_names",
            return_value=("queue_imbalance", "basis_bps"),
        ),
        patch(
            "app.core.trend_research.training_runtime._build_training_samples",
            return_value=["sample"] * 64,
        ),
        patch(
            "app.core.trend_research.training_runtime.build_time_splits",
            return_value=SimpleNamespace(
                train_indices=tuple(range(40)),
                validation_indices=tuple(range(40, 52)),
                test_indices=tuple(range(52, 64)),
            ),
        ),
        patch(
            "app.core.trend_research.training_runtime.train_direct_extrema_model",
            return_value=bundle,
        ),
        patch("app.core.trend_research.training_runtime.save_direct_model_bundle"),
    ):
        result = retrain_model_from_storage(
            storage=object(),
            whitelist=("BTC-USDT-SWAP",),
            lookback=7200,
            progress_callback=progress_events.append,
        )

    assert result is bundle
    assert [
        event["status"]
        for event in progress_events
        if event.get("kind") == "stage" and event.get("stage") == "evaluate_validation"
    ] == ["running", "completed"]
    assert [
        event["status"]
        for event in progress_events
        if event.get("kind") == "stage" and event.get("stage") == "save_bundle"
    ] == ["running", "completed"]
