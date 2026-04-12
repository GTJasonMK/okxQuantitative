from __future__ import annotations

from datetime import datetime, timezone

import numpy as np

from .direct_models import (
    DirectExtremaModelBundle,
    DirectExtremaModelConfig,
    DirectExtremaPrediction,
    OnlineSequenceWindow,
    SequenceSample,
)
from .models import TimeOrderedSplit
from .sequence_metrics import build_direct_extrema_metrics
from .tcn_model import DirectExtremaTCN, TORCH_AVAILABLE, TORCH_IMPORT_ERROR, torch


DEFAULT_TRAIN_RATIO = 0.7
DEFAULT_VALIDATION_RATIO = 0.15
DEFAULT_EPOCHS = 20
DEFAULT_LEARNING_RATE = 1e-3
DEFAULT_RETURN_WEIGHT = 1.0


def build_time_splits(
    total_count: int,
    *,
    train_ratio: float = DEFAULT_TRAIN_RATIO,
    validation_ratio: float = DEFAULT_VALIDATION_RATIO,
) -> TimeOrderedSplit:
    if total_count < 3:
        raise ValueError("at least 3 samples are required for train/validation/test splits")
    train_count = max(int(total_count * train_ratio), 1)
    validation_count = max(int(total_count * validation_ratio), 1)
    if train_count + validation_count >= total_count:
        train_count = max(total_count - 2, 1)
        validation_count = 1
    return TimeOrderedSplit(
        train_indices=tuple(range(train_count)),
        validation_indices=tuple(range(train_count, train_count + validation_count)),
        test_indices=tuple(range(train_count + validation_count, total_count)),
    )


def _require_torch_training():
    if TORCH_AVAILABLE:
        return
    raise RuntimeError("PyTorch is required for direct extrema training") from TORCH_IMPORT_ERROR


def _feature_tensor(samples: list[SequenceSample]) -> np.ndarray:
    return np.asarray([sample.feature_rows for sample in samples], dtype=float)


def _fit_standardizer(samples: list[SequenceSample]) -> tuple[tuple[float, ...], tuple[float, ...]]:
    rows = _feature_tensor(samples)
    means = np.mean(rows, axis=(0, 1))
    stds = np.std(rows, axis=(0, 1))
    if np.any(stds <= 0.0):
        raise ValueError("zero variance in training features")
    return tuple(float(value) for value in means), tuple(float(value) for value in stds)


def _standardize(samples: list[SequenceSample], *, means: tuple[float, ...], stds: tuple[float, ...]) -> np.ndarray:
    rows = _feature_tensor(samples)
    return (rows - np.asarray(means, dtype=float)) / np.asarray(stds, dtype=float)


def _slice_samples(samples: list[SequenceSample], indices: tuple[int, ...]) -> list[SequenceSample]:
    return [samples[index] for index in indices]


def _tensorize(samples: list[SequenceSample], *, means: tuple[float, ...], stds: tuple[float, ...]):
    features = torch.as_tensor(_standardize(samples, means=means, stds=stds), dtype=torch.float32)
    return {
        "features": features,
        "top_time_bucket": torch.as_tensor([sample.target.top_time_bucket for sample in samples], dtype=torch.long),
        "bottom_time_bucket": torch.as_tensor([sample.target.bottom_time_bucket for sample in samples], dtype=torch.long),
        "top_return": torch.as_tensor([sample.target.top_return for sample in samples], dtype=torch.float32),
        "bottom_return": torch.as_tensor([sample.target.bottom_return for sample in samples], dtype=torch.float32),
    }


def build_direct_loss(outputs, batch, *, return_weight: float):
    functional = torch.nn.functional
    return (
        functional.cross_entropy(outputs["top_time_logits"], batch["top_time_bucket"])
        + functional.cross_entropy(outputs["bottom_time_logits"], batch["bottom_time_bucket"])
        + return_weight * functional.huber_loss(outputs["top_return"], batch["top_return"])
        + return_weight * functional.huber_loss(outputs["bottom_return"], batch["bottom_return"])
    )


def _evaluate(model, batch) -> dict[str, list[float]]:
    model.eval()
    with torch.no_grad():
        outputs = model(batch["features"])
    return {
        "predicted_top_buckets": outputs["top_time_logits"].argmax(dim=1).cpu().tolist(),
        "predicted_bottom_buckets": outputs["bottom_time_logits"].argmax(dim=1).cpu().tolist(),
        "predicted_top_returns": outputs["top_return"].cpu().tolist(),
        "predicted_bottom_returns": outputs["bottom_return"].cpu().tolist(),
        "target_top_buckets": batch["top_time_bucket"].cpu().tolist(),
        "target_bottom_buckets": batch["bottom_time_bucket"].cpu().tolist(),
        "target_top_returns": batch["top_return"].cpu().tolist(),
        "target_bottom_returns": batch["bottom_return"].cpu().tolist(),
    }


def _emit_epoch_progress(
    progress_callback,
    *,
    epoch: int,
    total_epochs: int,
    train_loss: float,
    validation_loss: float,
) -> None:
    if progress_callback is None:
        return
    progress_callback(
        {
            "kind": "epoch",
            "epoch": int(epoch),
            "total_epochs": int(total_epochs),
            "train_loss": float(train_loss),
            "validation_loss": float(validation_loss),
        }
    )


def train_direct_extrema_model(
    samples: list[SequenceSample],
    *,
    config: DirectExtremaModelConfig,
    epochs: int = DEFAULT_EPOCHS,
    learning_rate: float = DEFAULT_LEARNING_RATE,
    return_weight: float = DEFAULT_RETURN_WEIGHT,
    progress_callback=None,
) -> DirectExtremaModelBundle:
    _require_torch_training()
    if len(samples) < 3:
        raise ValueError("at least 3 samples are required for direct extrema training")
    total_epochs = max(int(epochs), 1)
    splits = build_time_splits(len(samples))
    train_samples = _slice_samples(samples, splits.train_indices)
    validation_samples = _slice_samples(samples, splits.validation_indices)
    test_samples = _slice_samples(samples, splits.test_indices)
    means, stds = _fit_standardizer(train_samples)
    train_batch = _tensorize(train_samples, means=means, stds=stds)
    validation_batch = _tensorize(validation_samples, means=means, stds=stds)
    test_batch = _tensorize(test_samples, means=means, stds=stds)
    model = DirectExtremaTCN(
        input_dim=len(config.feature_names),
        hidden_channels=config.hidden_channels,
        horizon_buckets=config.horizon_minutes,
        dropout=config.dropout,
    )
    optimizer = torch.optim.Adam(model.parameters(), lr=learning_rate)
    for epoch_index in range(total_epochs):
        model.train()
        optimizer.zero_grad()
        train_outputs = model(train_batch["features"])
        loss = build_direct_loss(
            train_outputs,
            train_batch,
            return_weight=return_weight,
        )
        loss.backward()
        optimizer.step()
        validation_outputs = model(validation_batch["features"])
        validation_loss = build_direct_loss(
            validation_outputs,
            validation_batch,
            return_weight=return_weight,
        )
        _emit_epoch_progress(
            progress_callback,
            epoch=epoch_index + 1,
            total_epochs=total_epochs,
            train_loss=loss.detach().cpu().item(),
            validation_loss=validation_loss.detach().cpu().item(),
        )
    metrics = build_direct_extrema_metrics(**_evaluate(model, validation_batch))
    test_metrics = build_direct_extrema_metrics(**_evaluate(model, test_batch))
    if test_metrics.joint_hit_rate < metrics.joint_hit_rate:
        metrics = test_metrics
    return DirectExtremaModelBundle(
        trained_at=datetime.now(timezone.utc).isoformat(),
        config=config,
        normalization_means=means,
        normalization_stds=stds,
        state_dict={key: value.detach().cpu().tolist() for key, value in model.state_dict().items()},
        metrics=metrics,
    )


def _bundle_state_dict(bundle: DirectExtremaModelBundle) -> dict[str, object]:
    return {
        key: torch.as_tensor(value, dtype=torch.float32)
        for key, value in bundle.state_dict.items()
    }


def build_runtime_direct_model(bundle: DirectExtremaModelBundle):
    _require_torch_training()
    model = DirectExtremaTCN(
        input_dim=len(bundle.config.feature_names),
        hidden_channels=bundle.config.hidden_channels,
        horizon_buckets=bundle.config.horizon_minutes,
        dropout=bundle.config.dropout,
    )
    model.load_state_dict(_bundle_state_dict(bundle), strict=True)
    model.eval()
    return model


def _normalize_online_window(window: OnlineSequenceWindow, bundle: DirectExtremaModelBundle):
    rows = np.asarray([window.feature_rows], dtype=float)
    normalized = (rows - np.asarray(bundle.normalization_means, dtype=float)) / np.asarray(bundle.normalization_stds, dtype=float)
    return torch.as_tensor(normalized, dtype=torch.float32)


def run_direct_model(window: OnlineSequenceWindow, bundle: DirectExtremaModelBundle) -> DirectExtremaPrediction:
    model = build_runtime_direct_model(bundle)
    with torch.no_grad():
        outputs = model(_normalize_online_window(window, bundle))
    top_distribution = torch.softmax(outputs["top_time_logits"], dim=1)[0].cpu().tolist()
    bottom_distribution = torch.softmax(outputs["bottom_time_logits"], dim=1)[0].cpu().tolist()
    return DirectExtremaPrediction(
        top_time_bucket=max(range(len(top_distribution)), key=top_distribution.__getitem__),
        bottom_time_bucket=max(range(len(bottom_distribution)), key=bottom_distribution.__getitem__),
        top_return=float(outputs["top_return"][0].cpu().item()),
        bottom_return=float(outputs["bottom_return"][0].cpu().item()),
        top_distribution=tuple(float(value) for value in top_distribution),
        bottom_distribution=tuple(float(value) for value in bottom_distribution),
    )
