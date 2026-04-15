from __future__ import annotations

from dataclasses import asdict

from .constants import (
    BOUNDARY_TARGET_LABEL_DEFINITION_V1,
    INPUT_WINDOW_SECONDS_15M,
    LABEL_WINDOW_SECONDS_15M,
)
from .labeling import build_boundary_target_15m
from .sample_index import build_sample_index_15m


TOTAL_WINDOW_SECONDS = INPUT_WINDOW_SECONDS_15M + LABEL_WINDOW_SECONDS_15M


class BoundaryMaterializer:
    def __init__(
        self,
        *,
        storage,
        stride_seconds: int = LABEL_WINDOW_SECONDS_15M,
        label_definition_version: str = BOUNDARY_TARGET_LABEL_DEFINITION_V1,
    ):
        self._storage = storage
        self._stride_seconds = int(stride_seconds)
        self._label_definition_version = str(label_definition_version)

    def handle_flushed_second(
        self,
        *,
        session_id: str,
        inst_id: str,
        second_bucket: int,
    ) -> list[dict[str, object]]:
        if not _is_boundary_second(second_bucket):
            return []
        rows = _load_recent_rows(self._storage, session_id)
        decision_ts = int(second_bucket) + 1
        events = [_persist_current_boundary_sample(
            storage=self._storage,
            session_id=session_id,
            inst_id=inst_id,
            decision_ts=decision_ts,
            rows=rows,
            stride_seconds=self._stride_seconds,
        )]
        matured_decision_ts = decision_ts - LABEL_WINDOW_SECONDS_15M
        matured_events = _persist_matured_boundary(
            storage=self._storage,
            session_id=session_id,
            inst_id=inst_id,
            decision_ts=matured_decision_ts,
            rows=rows,
            stride_seconds=self._stride_seconds,
            label_definition_version=self._label_definition_version,
        )
        return events + matured_events


def _persist_current_boundary_sample(
    *,
    storage,
    session_id: str,
    inst_id: str,
    decision_ts: int,
    rows: list[dict[str, object]],
    stride_seconds: int,
) -> dict[str, object]:
    sample = build_sample_index_15m(
        session_id=session_id,
        inst_id=inst_id,
        decision_ts=decision_ts,
        input_rows=_slice_rows(rows, start_ts=decision_ts - INPUT_WINDOW_SECONDS_15M, end_ts=decision_ts),
        label_rows=[],
        stride_seconds=stride_seconds,
    )
    storage.save_research_sample_index_15m(**asdict(sample))
    return _build_sample_event(sample)


def _persist_matured_boundary(
    *,
    storage,
    session_id: str,
    inst_id: str,
    decision_ts: int,
    rows: list[dict[str, object]],
    stride_seconds: int,
    label_definition_version: str,
) -> list[dict[str, object]]:
    if decision_ts <= 0:
        return []
    input_start_ts = decision_ts - INPUT_WINDOW_SECONDS_15M
    if not _window_start_is_covered(rows, start_ts=input_start_ts):
        return []
    input_rows = _slice_rows(rows, start_ts=decision_ts - INPUT_WINDOW_SECONDS_15M, end_ts=decision_ts)
    label_rows = _slice_rows(rows, start_ts=decision_ts, end_ts=decision_ts + LABEL_WINDOW_SECONDS_15M)
    if not input_rows and not label_rows:
        return []
    sample = build_sample_index_15m(
        session_id=session_id,
        inst_id=inst_id,
        decision_ts=decision_ts,
        input_rows=input_rows,
        label_rows=label_rows,
        stride_seconds=stride_seconds,
    )
    storage.save_research_sample_index_15m(**asdict(sample))
    events = [_build_sample_event(sample)]
    if _can_build_target(input_rows=input_rows, label_rows=label_rows, decision_ts=decision_ts):
        target = build_boundary_target_15m(
            session_id=session_id,
            inst_id=inst_id,
            decision_ts=decision_ts,
            input_rows=input_rows,
            label_rows=label_rows,
            label_definition_version=label_definition_version,
        )
        storage.save_research_boundary_target_15m(**asdict(target))
        events.append(
            {
                'event': 'boundary_target_materialized',
                'session_id': session_id,
                'inst_id': inst_id,
                'decision_ts': int(decision_ts),
                'label_complete': int(target.label_complete),
                'invalid_reason': target.invalid_reason,
            }
        )
    return events


def _load_recent_rows(storage, session_id: str) -> list[dict[str, object]]:
    rows = storage.list_research_second_states(session_id, limit=TOTAL_WINDOW_SECONDS)
    return list(reversed(rows))


def _slice_rows(
    rows: list[dict[str, object]],
    *,
    start_ts: int,
    end_ts: int,
) -> list[dict[str, object]]:
    return [
        row for row in rows
        if start_ts <= int(row['second_bucket']) < end_ts
    ]


def _window_start_is_covered(rows: list[dict[str, object]], *, start_ts: int) -> bool:
    if not rows:
        return False
    return int(rows[0]['second_bucket']) <= int(start_ts)


def _build_sample_event(sample) -> dict[str, object]:
    return {
        'event': 'sample_index_materialized',
        'session_id': sample.session_id,
        'inst_id': sample.inst_id,
        'decision_ts': int(sample.decision_ts),
        'ready_for_inference': int(sample.ready_for_inference),
        'ready_for_training': int(sample.ready_for_training),
        'sample_valid': int(sample.sample_valid),
        'invalid_reason': sample.invalid_reason,
    }


def _can_build_target(
    *,
    input_rows: list[dict[str, object]],
    label_rows: list[dict[str, object]],
    decision_ts: int,
) -> bool:
    if not input_rows or not label_rows:
        return False
    return int(input_rows[-1]['second_bucket']) == int(decision_ts) - 1


def _is_boundary_second(second_bucket: int) -> bool:
    return (int(second_bucket) + 1) % LABEL_WINDOW_SECONDS_15M == 0
