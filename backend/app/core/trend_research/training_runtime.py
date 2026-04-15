from __future__ import annotations

from types import SimpleNamespace

from .direct_models import DirectExtremaModelConfig
from .direct_training import build_time_splits, train_direct_extrema_model
from .model_store import save_direct_model_bundle
from .research_runtime import build_raw_factor_columns
from .sequence_dataset import build_sequence_samples
from .training_constants import DEFAULT_EPOCHS


DEFAULT_MODEL_INPUT_MINUTES = 120
DEFAULT_MODEL_HORIZON_MINUTES = 60
DEFAULT_BUCKET_SECONDS = 60
DEFAULT_HIDDEN_CHANNELS = (32, 64, 64)
DEFAULT_DROPOUT = 0.1
MIN_TRAINING_SAMPLE_COUNT = 16


def _chronological_bars(storage, inst_id: str, lookback: int):
    return list(reversed(storage.list_feature_bars_1s(inst_id, limit=max(int(lookback or 0), 1))))


def _available_feature_names(bars) -> tuple[str, ...]:
    return tuple(definition.name for definition, _ in build_raw_factor_columns(bars))


def _collect_training_bars(service, lookback: int) -> dict[str, list]:
    minimum_bars = DEFAULT_MODEL_INPUT_MINUTES + DEFAULT_MODEL_HORIZON_MINUTES
    collected = {}
    for inst_id in service.whitelist:
        bars = _chronological_bars(service.storage, inst_id, lookback)
        if len(bars) >= minimum_bars:
            collected[inst_id] = bars
    return collected


def _shared_feature_names(inst_bars: dict[str, list]) -> tuple[str, ...]:
    shared_names = None
    for bars in inst_bars.values():
        available_names = set(_available_feature_names(bars))
        shared_names = available_names if shared_names is None else shared_names & available_names
    if not shared_names:
        return ()
    return tuple(sorted(shared_names))


def _build_training_samples(inst_bars: dict[str, list], feature_names: tuple[str, ...]):
    samples = []
    for bars in inst_bars.values():
        samples.extend(
            build_sequence_samples(
                bars,
                feature_names=feature_names,
                input_minutes=DEFAULT_MODEL_INPUT_MINUTES,
                horizon_minutes=DEFAULT_MODEL_HORIZON_MINUTES,
            )
        )
    return samples


def _emit_stage(
    progress_callback,
    *,
    stage: str,
    status: str,
    message: str,
    stats: dict[str, object] | None = None,
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        {
            "kind": "stage",
            "stage": stage,
            "status": status,
            "message": message,
            "stats": dict(stats or {}),
        }
    )


def retrain_model_from_storage(storage, whitelist, *, lookback: int, progress_callback=None):
    runtime_context = SimpleNamespace(storage=storage, whitelist=tuple(whitelist))
    _emit_stage(
        progress_callback,
        stage="collect_bars",
        status="running",
        message="collecting feature bars",
    )
    inst_bars = _collect_training_bars(runtime_context, lookback)
    _emit_stage(
        progress_callback,
        stage="collect_bars",
        status="completed",
        message="bars ready",
        stats={
            "eligible_inst_count": len(inst_bars),
            "whitelist_count": len(runtime_context.whitelist),
        },
    )
    if not inst_bars:
        _emit_stage(
            progress_callback,
            stage="collect_bars",
            status="failed",
            message="insufficient local bars for direct extrema training",
        )
        raise RuntimeError("insufficient local bars for direct extrema training")

    _emit_stage(
        progress_callback,
        stage="resolve_shared_features",
        status="running",
        message="resolving shared features",
    )
    feature_names = _shared_feature_names(inst_bars)
    _emit_stage(
        progress_callback,
        stage="resolve_shared_features",
        status="completed",
        message="shared factor set ready",
        stats={"shared_feature_count": len(feature_names)},
    )
    if not feature_names:
        _emit_stage(
            progress_callback,
            stage="resolve_shared_features",
            status="failed",
            message="no shared factor set available for direct extrema training",
        )
        raise RuntimeError("no shared factor set available for direct extrema training")

    _emit_stage(
        progress_callback,
        stage="build_samples",
        status="running",
        message="building sequence samples",
    )
    samples = _build_training_samples(inst_bars, feature_names)
    _emit_stage(
        progress_callback,
        stage="build_samples",
        status="completed",
        message="sequence samples ready",
        stats={"sample_count": len(samples)},
    )
    if len(samples) < MIN_TRAINING_SAMPLE_COUNT:
        _emit_stage(
            progress_callback,
            stage="build_samples",
            status="failed",
            message="insufficient local bars for direct extrema training",
        )
        raise RuntimeError("insufficient local bars for direct extrema training")

    _emit_stage(
        progress_callback,
        stage="split_dataset",
        status="running",
        message="splitting train/validation/test",
    )
    splits = build_time_splits(len(samples))
    _emit_stage(
        progress_callback,
        stage="split_dataset",
        status="completed",
        message="dataset split ready",
        stats={
            "train_count": len(splits.train_indices),
            "validation_count": len(splits.validation_indices),
            "test_count": len(splits.test_indices),
        },
    )

    _emit_stage(
        progress_callback,
        stage="train_epochs",
        status="running",
        message="Epoch 0 / 20",
    )
    bundle = train_direct_extrema_model(
        samples,
        config=DirectExtremaModelConfig(
            architecture="tcn",
            input_minutes=DEFAULT_MODEL_INPUT_MINUTES,
            horizon_minutes=DEFAULT_MODEL_HORIZON_MINUTES,
            bucket_seconds=DEFAULT_BUCKET_SECONDS,
            hidden_channels=DEFAULT_HIDDEN_CHANNELS,
            dropout=DEFAULT_DROPOUT,
            feature_names=feature_names,
        ),
        progress_callback=progress_callback,
    )
    _emit_stage(
        progress_callback,
        stage="train_epochs",
        status="completed",
        message=f"Epoch {DEFAULT_EPOCHS} / {DEFAULT_EPOCHS}",
        stats={"epoch_count": DEFAULT_EPOCHS},
    )
    _emit_stage(
        progress_callback,
        stage="evaluate_validation",
        status="running",
        message="evaluating validation metrics",
    )
    _emit_stage(
        progress_callback,
        stage="evaluate_validation",
        status="completed",
        message="validation metrics ready",
        stats={
            "joint_hit_rate": bundle.metrics.joint_hit_rate,
            "top_time_mae_minutes": bundle.metrics.top_time_mae_minutes,
            "bottom_time_mae_minutes": bundle.metrics.bottom_time_mae_minutes,
        },
    )
    _emit_stage(
        progress_callback,
        stage="save_bundle",
        status="running",
        message="saving trained bundle",
    )
    save_direct_model_bundle(bundle)
    _emit_stage(
        progress_callback,
        stage="save_bundle",
        status="completed",
        message="bundle saved",
        stats={"selected_feature_count": len(bundle.config.feature_names)},
    )
    return bundle
