from __future__ import annotations

from .constants import INPUT_WINDOW_SECONDS_15M, LABEL_WINDOW_SECONDS_15M
from .models import SampleIndex15m
from .windowing import rows_cover_window


def build_sample_index_15m(
    *,
    session_id: str,
    inst_id: str,
    decision_ts: int,
    input_rows: list[dict[str, object]],
    label_rows: list[dict[str, object]],
    stride_seconds: int,
) -> SampleIndex15m:
    input_start_ts = decision_ts - INPUT_WINDOW_SECONDS_15M
    label_end_ts = decision_ts + LABEL_WINDOW_SECONDS_15M
    input_complete = rows_cover_window(
        rows=input_rows,
        start_ts=input_start_ts,
        end_ts=decision_ts,
        session_id=session_id,
        inst_id=inst_id,
    )
    label_complete = rows_cover_window(
        rows=label_rows,
        start_ts=decision_ts,
        end_ts=label_end_ts,
        session_id=session_id,
        inst_id=inst_id,
    )
    sample_valid = input_complete and label_complete
    return SampleIndex15m(
        sample_id=f'{session_id}:{decision_ts}',
        session_id=session_id,
        inst_id=inst_id,
        decision_ts=decision_ts,
        input_start_ts=input_start_ts,
        input_end_ts=decision_ts,
        label_start_ts=decision_ts,
        label_end_ts=label_end_ts,
        input_second_count=len(input_rows),
        label_second_count=len(label_rows),
        input_complete_7200=input_complete,
        label_complete_900=label_complete,
        sample_valid=sample_valid,
        ready_for_inference=input_complete,
        ready_for_training=sample_valid,
        invalid_reason=_build_invalid_reason(
            input_complete=input_complete,
            label_complete=label_complete,
        ),
        prev_sample_overlap_seconds=max(0, INPUT_WINDOW_SECONDS_15M - int(stride_seconds)),
        stride_seconds=int(stride_seconds),
    )


def _build_invalid_reason(*, input_complete: bool, label_complete: bool) -> str:
    if input_complete and label_complete:
        return ''
    if not input_complete and not label_complete:
        return 'strict_window_incomplete'
    if not input_complete:
        return 'input_window_incomplete'
    return 'label_window_incomplete'
