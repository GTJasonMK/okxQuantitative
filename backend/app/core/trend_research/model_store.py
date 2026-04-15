from __future__ import annotations

import importlib
import json
from dataclasses import asdict
from pathlib import Path

from .direct_models import (
    DirectExtremaMetrics,
    DirectExtremaModelBundle,
    DirectExtremaModelConfig,
)
from .models import (
    BinaryClassificationMetrics,
    LogisticModelHead,
    TrendModelBundle,
)


DEFAULT_MODEL_PATH = Path(__file__).resolve().parents[4] / "data" / "trend_research_model.json"
DEFAULT_DIRECT_MODEL_PATH = Path(__file__).resolve().parents[4] / "data" / "trend_research_direct_model.json"


def _resolve_model_path(path: str | Path | None) -> Path:
    return Path(path) if path is not None else DEFAULT_MODEL_PATH


def _resolve_direct_model_path(path: str | Path | None) -> Path:
    return Path(path) if path is not None else DEFAULT_DIRECT_MODEL_PATH


def _load_torch_module():
    try:
        return importlib.import_module("torch")
    except Exception as exc:
        raise RuntimeError("PyTorch is required for direct extrema model persistence") from exc


def save_model_bundle(bundle: TrendModelBundle, path: str | Path | None = None) -> Path:
    resolved_path = _resolve_model_path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    temp_path = resolved_path.with_suffix(f"{resolved_path.suffix}.tmp")
    temp_path.write_text(json.dumps(asdict(bundle), ensure_ascii=False, indent=2), encoding="utf-8")
    temp_path.replace(resolved_path)
    return resolved_path


def load_model_bundle(path: str | Path | None = None) -> TrendModelBundle:
    resolved_path = _resolve_model_path(path)
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    return TrendModelBundle(
        trained_at=payload["trained_at"],
        horizon_minutes=int(payload["horizon_minutes"]),
        reversal_threshold_floor=float(payload["reversal_threshold_floor"]),
        feature_names=tuple(payload["feature_names"]),
        train_means=tuple(float(value) for value in payload["train_means"]),
        train_stds=tuple(float(value) for value in payload["train_stds"]),
        top_head=_load_head(payload["top_head"]),
        bottom_head=_load_head(payload["bottom_head"]),
        top_validation=_load_metrics(payload["top_validation"]),
        bottom_validation=_load_metrics(payload["bottom_validation"]),
        top_test=_load_metrics(payload["top_test"]),
        bottom_test=_load_metrics(payload["bottom_test"]),
    )


def save_direct_model_bundle(bundle: DirectExtremaModelBundle, path: str | Path | None = None) -> Path:
    torch = _load_torch_module()
    resolved_path = _resolve_direct_model_path(path)
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    weights_path = resolved_path.with_suffix(".pt")
    temp_metadata_path = resolved_path.with_suffix(f"{resolved_path.suffix}.tmp")
    temp_weights_path = weights_path.with_suffix(f"{weights_path.suffix}.tmp")
    torch.save(bundle.state_dict, temp_weights_path)
    payload = asdict(bundle)
    payload.pop("state_dict", None)
    payload["weights_file"] = weights_path.name
    temp_metadata_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    Path(temp_weights_path).replace(weights_path)
    temp_metadata_path.replace(resolved_path)
    return resolved_path


def load_direct_model_bundle(path: str | Path | None = None) -> DirectExtremaModelBundle:
    torch = _load_torch_module()
    resolved_path = _resolve_direct_model_path(path)
    payload = json.loads(resolved_path.read_text(encoding="utf-8"))
    weights_file = str(payload.get("weights_file") or resolved_path.with_suffix(".pt").name)
    weights_path = resolved_path.with_name(weights_file)
    return DirectExtremaModelBundle(
        trained_at=str(payload["trained_at"]),
        config=_load_direct_config(payload["config"]),
        normalization_means=tuple(float(value) for value in payload["normalization_means"]),
        normalization_stds=tuple(float(value) for value in payload["normalization_stds"]),
        state_dict=torch.load(weights_path, map_location="cpu"),
        metrics=_load_direct_metrics(payload["metrics"]),
    )


def _load_head(payload: dict) -> LogisticModelHead:
    return LogisticModelHead(
        weights=tuple(float(value) for value in payload["weights"]),
        intercept=float(payload["intercept"]),
        positive_class_weight=float(payload["positive_class_weight"]),
        negative_class_weight=float(payload["negative_class_weight"]),
    )


def _load_metrics(payload: dict) -> BinaryClassificationMetrics:
    return BinaryClassificationMetrics(
        accuracy=float(payload["accuracy"]),
        log_loss=float(payload["log_loss"]),
        positive_rate=float(payload["positive_rate"]),
    )


def _load_direct_config(payload: dict) -> DirectExtremaModelConfig:
    return DirectExtremaModelConfig(
        architecture=str(payload["architecture"]),
        input_minutes=int(payload["input_minutes"]),
        horizon_minutes=int(payload["horizon_minutes"]),
        bucket_seconds=int(payload["bucket_seconds"]),
        hidden_channels=tuple(int(value) for value in payload["hidden_channels"]),
        dropout=float(payload["dropout"]),
        feature_names=tuple(str(value) for value in payload["feature_names"]),
    )


def _load_direct_metrics(payload: dict) -> DirectExtremaMetrics:
    return DirectExtremaMetrics(
        top_time_mae_minutes=float(payload["top_time_mae_minutes"]),
        bottom_time_mae_minutes=float(payload["bottom_time_mae_minutes"]),
        top_price_mae_bps=float(payload["top_price_mae_bps"]),
        bottom_price_mae_bps=float(payload["bottom_price_mae_bps"]),
        joint_hit_rate=float(payload["joint_hit_rate"]),
    )
