from __future__ import annotations

from pathlib import Path

import pytest

from app.core.data_storage import DataStorage
from app.core.research_platform.dataset.labeling import build_boundary_target_15m
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
    instance = DataStorage(tmp_path / 'research_boundary_target.db')
    yield instance
    close_storage(instance)


def test_build_boundary_target_15m_aggregates_session_seconds():
    decision_ts = DEFAULT_DECISION_TS
    input_rows = build_second_rows(
        start_ts=decision_ts - DEFAULT_INPUT_SECONDS,
        count=DEFAULT_INPUT_SECONDS,
    )
    label_rows = build_second_rows(
        start_ts=decision_ts,
        count=DEFAULT_LABEL_SECONDS,
    )

    target = build_boundary_target_15m(
        session_id=DEFAULT_SESSION_ID,
        inst_id=DEFAULT_INST_ID,
        decision_ts=decision_ts,
        input_rows=input_rows,
        label_rows=label_rows,
        label_definition_version='next_bar_15m_ohlc_reparam_from_session_seconds_v1',
    )

    assert target.anchor_second_bucket == decision_ts - 1
    assert target.anchor_close_price > 0
    assert target.label_start_ts == decision_ts
    assert target.label_end_ts == decision_ts + DEFAULT_LABEL_SECONDS
    assert target.r_open is not None
    assert target.r_close is not None
    assert target.u >= 0
    assert target.d >= 0
    assert target.label_complete is True
    assert target.label_definition_version == 'next_bar_15m_ohlc_reparam_from_session_seconds_v1'


def test_build_boundary_target_marks_invalid_label_seconds_as_incomplete():
    decision_ts = DEFAULT_DECISION_TS
    input_rows = build_second_rows(
        start_ts=decision_ts - DEFAULT_INPUT_SECONDS,
        count=DEFAULT_INPUT_SECONDS,
    )
    label_rows = build_second_rows(
        start_ts=decision_ts,
        count=DEFAULT_LABEL_SECONDS,
    )
    label_rows[20]['is_valid_second'] = 0
    label_rows[20]['state_age_seconds'] = 99.0

    target = build_boundary_target_15m(
        session_id=DEFAULT_SESSION_ID,
        inst_id=DEFAULT_INST_ID,
        decision_ts=decision_ts,
        input_rows=input_rows,
        label_rows=label_rows,
        label_definition_version='next_bar_15m_ohlc_reparam_from_session_seconds_v1',
    )

    assert target.label_complete is False
    assert target.invalid_reason == 'label_seconds_missing'


def test_storage_round_trips_boundary_target_15m(storage):
    storage.save_research_boundary_target_15m(
        target_id='target-1',
        session_id=DEFAULT_SESSION_ID,
        inst_id=DEFAULT_INST_ID,
        decision_ts=DEFAULT_DECISION_TS,
        anchor_second_bucket=DEFAULT_DECISION_TS - 1,
        anchor_close_price=65000.0,
        label_start_ts=DEFAULT_DECISION_TS,
        label_end_ts=DEFAULT_DECISION_TS + DEFAULT_LABEL_SECONDS,
        open_price=65000.2,
        high_price=65002.4,
        low_price=64998.8,
        close_price=65001.1,
        r_open=0.0000030769,
        r_close=0.0000169231,
        u=0.0000199998,
        d=0.0000215387,
        label_complete=1,
        invalid_reason='',
        label_definition_version='next_bar_15m_ohlc_reparam_from_session_seconds_v1',
    )

    row = storage.get_research_boundary_target_15m(DEFAULT_SESSION_ID, DEFAULT_DECISION_TS)

    assert row is not None
    assert row['target_id'] == 'target-1'
    assert row['label_complete'] == 1
    assert row['label_definition_version'] == 'next_bar_15m_ohlc_reparam_from_session_seconds_v1'
