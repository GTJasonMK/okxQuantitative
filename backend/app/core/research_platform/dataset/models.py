from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BoundaryTarget15m:
    target_id: str
    session_id: str
    inst_id: str
    decision_ts: int
    anchor_second_bucket: int
    anchor_close_price: float
    label_start_ts: int
    label_end_ts: int
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    r_open: float
    r_close: float
    u: float
    d: float
    label_complete: bool
    invalid_reason: str
    label_definition_version: str


@dataclass(frozen=True)
class SampleIndex15m:
    sample_id: str
    session_id: str
    inst_id: str
    decision_ts: int
    input_start_ts: int
    input_end_ts: int
    label_start_ts: int
    label_end_ts: int
    input_second_count: int
    label_second_count: int
    input_complete_7200: bool
    label_complete_900: bool
    sample_valid: bool
    ready_for_inference: bool
    ready_for_training: bool
    invalid_reason: str
    prev_sample_overlap_seconds: int
    stride_seconds: int
