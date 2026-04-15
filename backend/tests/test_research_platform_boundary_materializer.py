from __future__ import annotations

from pathlib import Path

import pytest

from app.core.data_storage import DataStorage
from app.core.research_platform.dataset.materializer import BoundaryMaterializer
from tests.research_platform_dataset_helpers import (
    DEFAULT_DECISION_TS,
    DEFAULT_INPUT_SECONDS,
    DEFAULT_INST_ID,
    DEFAULT_LABEL_SECONDS,
    build_second_rows,
    close_storage,
    save_second_rows,
)


BOUNDARY_DECISION_TS = DEFAULT_DECISION_TS - (DEFAULT_DECISION_TS % DEFAULT_LABEL_SECONDS)


@pytest.fixture
def storage(tmp_path: Path):
    instance = DataStorage(tmp_path / 'research_boundary_materializer.db')
    yield instance
    close_storage(instance)


def _create_session(storage: DataStorage) -> dict[str, object]:
    session_id = storage.create_research_collection_session(
        inst_id=DEFAULT_INST_ID,
        planned_duration_sec=DEFAULT_INPUT_SECONDS + (2 * DEFAULT_LABEL_SECONDS),
        trigger_mode='manual',
        trigger_note='',
        sampling_policy_id='manual_session_v1',
        integrity_policy_version='strict_v1',
        collector_version='research_collector_v1',
        source_config_hash='manual',
        feature_recipe_version='second_state_causal_tensor_v1',
        book_channel='books5',
    )
    return storage.get_research_collection_session(session_id)


def test_materializer_saves_boundary_sample_for_inference_ready_window(storage):
    session = _create_session(storage)
    decision_ts = BOUNDARY_DECISION_TS
    save_second_rows(
        storage,
        build_second_rows(
            start_ts=decision_ts - DEFAULT_INPUT_SECONDS,
            count=DEFAULT_INPUT_SECONDS,
            session_id=str(session['session_id']),
        ),
    )
    materializer = BoundaryMaterializer(storage=storage)

    events = materializer.handle_flushed_second(
        session_id=str(session['session_id']),
        inst_id=DEFAULT_INST_ID,
        second_bucket=decision_ts - 1,
    )

    sample = storage.get_research_sample_index_15m(str(session['session_id']), decision_ts)

    assert sample is not None
    assert sample['input_complete_7200'] == 1
    assert sample['label_complete_900'] == 0
    assert sample['ready_for_inference'] == 1
    assert sample['ready_for_training'] == 0
    assert sample['invalid_reason'] == 'label_window_incomplete'
    assert storage.get_research_boundary_target_15m(str(session['session_id']), decision_ts) is None
    assert events == [
        {
            'event': 'sample_index_materialized',
            'session_id': str(session['session_id']),
            'inst_id': DEFAULT_INST_ID,
            'decision_ts': decision_ts,
            'ready_for_inference': 1,
            'ready_for_training': 0,
            'sample_valid': 0,
            'invalid_reason': 'label_window_incomplete',
        }
    ]


def test_materializer_updates_previous_boundary_to_training_ready_at_next_boundary(storage):
    session = _create_session(storage)
    decision_ts = BOUNDARY_DECISION_TS
    save_second_rows(
        storage,
        build_second_rows(
            start_ts=decision_ts - DEFAULT_INPUT_SECONDS,
            count=DEFAULT_INPUT_SECONDS + DEFAULT_LABEL_SECONDS,
            session_id=str(session['session_id']),
        ),
    )
    materializer = BoundaryMaterializer(storage=storage)

    events = materializer.handle_flushed_second(
        session_id=str(session['session_id']),
        inst_id=DEFAULT_INST_ID,
        second_bucket=decision_ts + DEFAULT_LABEL_SECONDS - 1,
    )

    matured_sample = storage.get_research_sample_index_15m(str(session['session_id']), decision_ts)
    current_sample = storage.get_research_sample_index_15m(
        str(session['session_id']),
        decision_ts + DEFAULT_LABEL_SECONDS,
    )
    target = storage.get_research_boundary_target_15m(str(session['session_id']), decision_ts)

    assert matured_sample is not None
    assert matured_sample['sample_valid'] == 1
    assert matured_sample['ready_for_inference'] == 1
    assert matured_sample['ready_for_training'] == 1
    assert matured_sample['invalid_reason'] == ''
    assert current_sample is not None
    assert current_sample['ready_for_inference'] == 1
    assert current_sample['ready_for_training'] == 0
    assert target is not None
    assert target['label_complete'] == 1
    assert target['label_definition_version'] == 'next_bar_15m_ohlc_reparam_from_session_seconds_v1'
    assert [event['event'] for event in events] == [
        'sample_index_materialized',
        'sample_index_materialized',
        'boundary_target_materialized',
    ]
