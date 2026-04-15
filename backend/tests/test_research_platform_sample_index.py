from __future__ import annotations

from pathlib import Path

import pytest

from app.core.data_storage import DataStorage
from app.core.research_platform.dataset.sample_index import build_sample_index_15m
from tests.research_platform_dataset_helpers import (
    DEFAULT_DECISION_TS,
    DEFAULT_INPUT_SECONDS,
    DEFAULT_INST_ID,
    DEFAULT_LABEL_SECONDS,
    DEFAULT_SESSION_ID,
    build_second_rows,
    close_storage,
)


@pytest.fixture
def storage(tmp_path: Path):
    instance = DataStorage(tmp_path / 'research_sample_index.db')
    yield instance
    close_storage(instance)


def test_build_sample_index_marks_only_complete_single_session_samples():
    decision_ts = DEFAULT_DECISION_TS
    input_rows = build_second_rows(
        start_ts=decision_ts - DEFAULT_INPUT_SECONDS,
        count=DEFAULT_INPUT_SECONDS,
    )
    label_rows = build_second_rows(
        start_ts=decision_ts,
        count=DEFAULT_LABEL_SECONDS,
    )

    sample = build_sample_index_15m(
        session_id=DEFAULT_SESSION_ID,
        inst_id=DEFAULT_INST_ID,
        decision_ts=decision_ts,
        input_rows=input_rows,
        label_rows=label_rows,
        stride_seconds=DEFAULT_LABEL_SECONDS,
    )

    assert sample.input_start_ts == decision_ts - DEFAULT_INPUT_SECONDS
    assert sample.input_end_ts == decision_ts
    assert sample.label_start_ts == decision_ts
    assert sample.label_end_ts == decision_ts + DEFAULT_LABEL_SECONDS
    assert sample.input_complete_7200 is True
    assert sample.label_complete_900 is True
    assert sample.ready_for_inference is True
    assert sample.ready_for_training is True
    assert sample.sample_valid is True
    assert sample.prev_sample_overlap_seconds == DEFAULT_INPUT_SECONDS - DEFAULT_LABEL_SECONDS


def test_build_sample_index_rejects_invalid_seconds_inside_strict_window():
    decision_ts = DEFAULT_DECISION_TS
    input_rows = build_second_rows(
        start_ts=decision_ts - DEFAULT_INPUT_SECONDS,
        count=DEFAULT_INPUT_SECONDS,
    )
    label_rows = build_second_rows(
        start_ts=decision_ts,
        count=DEFAULT_LABEL_SECONDS,
    )
    input_rows[-5]['is_valid_second'] = 0
    input_rows[-5]['book_age_seconds'] = 9.0

    sample = build_sample_index_15m(
        session_id=DEFAULT_SESSION_ID,
        inst_id=DEFAULT_INST_ID,
        decision_ts=decision_ts,
        input_rows=input_rows,
        label_rows=label_rows,
        stride_seconds=DEFAULT_LABEL_SECONDS,
    )

    assert sample.input_complete_7200 is False
    assert sample.label_complete_900 is True
    assert sample.sample_valid is False
    assert sample.invalid_reason == 'input_window_incomplete'


def test_storage_round_trips_sample_index_15m(storage):
    storage.save_research_sample_index_15m(
        sample_id='sample-1',
        session_id=DEFAULT_SESSION_ID,
        inst_id=DEFAULT_INST_ID,
        decision_ts=DEFAULT_DECISION_TS,
        input_start_ts=DEFAULT_DECISION_TS - DEFAULT_INPUT_SECONDS,
        input_end_ts=DEFAULT_DECISION_TS,
        label_start_ts=DEFAULT_DECISION_TS,
        label_end_ts=DEFAULT_DECISION_TS + DEFAULT_LABEL_SECONDS,
        input_second_count=DEFAULT_INPUT_SECONDS,
        label_second_count=DEFAULT_LABEL_SECONDS,
        input_complete_7200=1,
        label_complete_900=1,
        sample_valid=1,
        ready_for_inference=1,
        ready_for_training=1,
        invalid_reason='',
        prev_sample_overlap_seconds=DEFAULT_INPUT_SECONDS - DEFAULT_LABEL_SECONDS,
        stride_seconds=DEFAULT_LABEL_SECONDS,
    )

    row = storage.get_research_sample_index_15m(DEFAULT_SESSION_ID, DEFAULT_DECISION_TS)

    assert row is not None
    assert row['sample_id'] == 'sample-1'
    assert row['sample_valid'] == 1
    assert row['ready_for_training'] == 1
