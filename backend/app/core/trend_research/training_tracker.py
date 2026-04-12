from __future__ import annotations

from dataclasses import replace
from time import time

from .training_run_models import (
    STAGE_ORDER,
    TrendTrainingEpochPoint,
    TrendTrainingRun,
    TrendTrainingStageSnapshot,
    build_new_training_run,
    run_to_dict,
)


class TrendTrainingTracker:
    def __init__(self):
        self._current: TrendTrainingRun | None = None

    def _require_run(self) -> TrendTrainingRun:
        if self._current is None:
            raise RuntimeError("training run has not been started")
        return self._current

    def _replace_run(self, **changes) -> None:
        self._current = replace(self._require_run(), **changes)

    def _stage(self, stage: str) -> TrendTrainingStageSnapshot:
        for snapshot in self._require_run().stages:
            if snapshot.stage == stage:
                return snapshot
        raise KeyError(stage)

    def _replace_stage(self, stage: str, **changes) -> None:
        next_stages = []
        for snapshot in self._require_run().stages:
            if snapshot.stage != stage:
                next_stages.append(snapshot)
                continue
            next_stages.append(
                replace(
                    snapshot,
                    **{
                        **changes,
                        "stats": dict(changes.get("stats", snapshot.stats)),
                    },
                )
            )
        self._replace_run(stages=tuple(next_stages))

    def _stage_progress_bounds(self, stage: str) -> tuple[float, float]:
        stage_index = STAGE_ORDER.index(stage)
        total_steps = max(len(STAGE_ORDER) - 1, 1)
        return (
            (stage_index / total_steps) * 100.0,
            ((stage_index + 1) / total_steps) * 100.0,
        )

    def start_run(self, *, lookback: int, total_epochs: int) -> dict[str, object]:
        self._current = build_new_training_run(
            lookback=lookback,
            total_epochs=total_epochs,
        )
        return self.snapshot()

    def start_stage(self, stage: str, *, message: str) -> None:
        stage_index = STAGE_ORDER.index(stage)
        base_progress = (stage_index / max(len(STAGE_ORDER) - 1, 1)) * 100.0
        self._replace_stage(
            stage,
            status="running",
            message=message,
            started_at=time(),
        )
        self._replace_run(
            status="running",
            current_stage=stage,
            progress_pct=max(self._require_run().progress_pct, base_progress),
            message=message,
        )

    def finish_stage(
        self,
        stage: str,
        *,
        stats: dict[str, object] | None = None,
        message: str = "",
    ) -> None:
        finished_at = time()
        current_stage = self._stage(stage)
        self._replace_stage(
            stage,
            status="completed",
            message=message or current_stage.message,
            finished_at=finished_at,
            duration_seconds=(
                finished_at - current_stage.started_at
                if current_stage.started_at
                else None
            ),
            stats=dict(stats or {}),
        )
        self._replace_run(
            progress_pct=max(
                self._require_run().progress_pct,
                ((STAGE_ORDER.index(stage) + 1) / max(len(STAGE_ORDER) - 1, 1))
                * 100.0,
            )
        )

    def record_epoch(
        self,
        *,
        epoch: int,
        total_epochs: int,
        train_loss: float,
        validation_loss: float,
    ) -> None:
        history = list(self._require_run().epoch_history)
        history.append(
            TrendTrainingEpochPoint(
                epoch=int(epoch),
                total_epochs=int(total_epochs),
                train_loss=float(train_loss),
                validation_loss=float(validation_loss),
                timestamp=time(),
            )
        )
        stage_start_progress, stage_end_progress = self._stage_progress_bounds(
            "train_epochs"
        )
        epoch_ratio = min(max(epoch / max(total_epochs, 1), 0.0), 1.0)
        progress_pct = stage_start_progress + (
            (stage_end_progress - stage_start_progress) * epoch_ratio
        )
        stage_message = f"Epoch {epoch} / {total_epochs}"
        self._replace_stage(
            "train_epochs",
            status="running",
            message=stage_message,
            stats={
                "current_epoch": int(epoch),
                "total_epochs": int(total_epochs),
                "latest_train_loss": float(train_loss),
                "latest_validation_loss": float(validation_loss),
            },
        )
        self._replace_run(
            current_stage="train_epochs",
            progress_pct=max(self._require_run().progress_pct, progress_pct),
            message=stage_message,
            epoch_history=tuple(history),
        )

    def fail_run(self, stage: str, error_message: str) -> None:
        finished_at = time()
        started_at = self._require_run().started_at
        current_stage = self._stage(stage)
        self._replace_stage(
            stage,
            status="failed",
            message=error_message,
            finished_at=finished_at,
            duration_seconds=(
                finished_at - current_stage.started_at
                if current_stage.started_at
                else None
            ),
        )
        self._replace_run(
            status="failed",
            current_stage=stage,
            error_message=error_message,
            message=error_message,
            finished_at=finished_at,
            duration_seconds=(finished_at - started_at) if started_at else None,
        )

    def complete_run(self, *, message: str) -> None:
        finished_at = time()
        started_at = self._require_run().started_at
        self._replace_run(
            status="completed",
            current_stage="activate_model",
            progress_pct=100.0,
            message=message,
            finished_at=finished_at,
            duration_seconds=(finished_at - started_at) if started_at else None,
        )

    def snapshot(self) -> dict[str, object]:
        return run_to_dict(self._current)
