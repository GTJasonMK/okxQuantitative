from __future__ import annotations

from dataclasses import asdict, dataclass, field
from time import time
from uuid import uuid4


STAGE_ORDER = (
    "queued",
    "collect_bars",
    "resolve_shared_features",
    "build_samples",
    "split_dataset",
    "train_epochs",
    "evaluate_validation",
    "save_bundle",
    "activate_model",
)


@dataclass(frozen=True)
class TrendTrainingEpochPoint:
    epoch: int
    total_epochs: int
    train_loss: float
    validation_loss: float
    timestamp: float


@dataclass(frozen=True)
class TrendTrainingStageSnapshot:
    stage: str
    status: str = "pending"
    started_at: float | None = None
    finished_at: float | None = None
    duration_seconds: float | None = None
    message: str = ""
    stats: dict[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class TrendTrainingRun:
    run_id: str
    status: str
    lookback: int
    total_epochs: int
    current_stage: str
    progress_pct: float
    message: str
    started_at: float | None
    finished_at: float | None
    duration_seconds: float | None
    error_message: str
    stages: tuple[TrendTrainingStageSnapshot, ...]
    epoch_history: tuple[TrendTrainingEpochPoint, ...]


def build_new_training_run(*, lookback: int, total_epochs: int) -> TrendTrainingRun:
    return TrendTrainingRun(
        run_id=uuid4().hex,
        status="queued",
        lookback=int(lookback),
        total_epochs=int(total_epochs),
        current_stage="queued",
        progress_pct=0.0,
        message="queued",
        started_at=time(),
        finished_at=None,
        duration_seconds=None,
        error_message="",
        stages=tuple(TrendTrainingStageSnapshot(stage=stage) for stage in STAGE_ORDER),
        epoch_history=(),
    )


def run_to_dict(run: TrendTrainingRun | None) -> dict[str, object]:
    return asdict(run) if run is not None else {}


def build_training_summary(run: TrendTrainingRun | dict[str, object] | None) -> dict[str, object]:
    if run is None:
        return {
            "status": "idle",
            "current_stage": "",
            "progress_pct": 0.0,
            "run_id": "",
            "current_epoch": 0,
            "total_epochs": 0,
        }

    if isinstance(run, dict):
        epoch_history = run.get("epoch_history") or []
        latest_epoch = epoch_history[-1] if epoch_history else {}
        return {
            "status": run.get("status", "idle"),
            "current_stage": run.get("current_stage", ""),
            "progress_pct": float(run.get("progress_pct", 0.0) or 0.0),
            "run_id": run.get("run_id", ""),
            "current_epoch": int(latest_epoch.get("epoch", 0) or 0),
            "total_epochs": int(latest_epoch.get("total_epochs", 0) or 0),
        }

    latest_epoch = run.epoch_history[-1] if run.epoch_history else None
    return {
        "status": run.status,
        "current_stage": run.current_stage,
        "progress_pct": run.progress_pct,
        "run_id": run.run_id,
        "current_epoch": latest_epoch.epoch if latest_epoch is not None else 0,
        "total_epochs": latest_epoch.total_epochs if latest_epoch is not None else 0,
    }
