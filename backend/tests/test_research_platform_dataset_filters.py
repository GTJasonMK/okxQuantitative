from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.core.data_storage import DataStorage
from app.core.research_platform.dataset.service import ResearchDatasetService
from tests.research_platform_manifest_helpers import (
    DEFAULT_DECISION_TS,
    DEFAULT_INST_ID,
    DEFAULT_LABEL_SECONDS,
    DEFAULT_SESSION_ID,
    _save_background_census,
    _save_boundary_target,
    _save_census,
    _save_sample_index,
    build_manifest_payload,
)
from tests.research_platform_dataset_helpers import close_storage


@pytest.fixture
def storage(tmp_path: Path):
    instance = DataStorage(tmp_path / 'research_dataset_filters.db')
    yield instance
    close_storage(instance)


def test_dataset_service_filters_to_training_ready_complete_and_eligible_rows(storage):
    _seed_rows(storage, count=8)
    _update_sample(
        storage,
        decision_ts=DEFAULT_DECISION_TS + DEFAULT_LABEL_SECONDS,
        ready_for_training=0,
        sample_valid=0,
        invalid_reason='label_window_incomplete',
    )
    _update_target(
        storage,
        decision_ts=DEFAULT_DECISION_TS + (2 * DEFAULT_LABEL_SECONDS),
        label_complete=0,
        invalid_reason='label_window_incomplete',
    )
    _update_census(
        storage,
        decision_ts=DEFAULT_DECISION_TS + (3 * DEFAULT_LABEL_SECONDS),
        deployment_eligible=0,
        invalid_reason='source_unhealthy',
    )
    service = ResearchDatasetService(storage=storage)

    labeled_rows, census_rows = service._load_joined_rows(build_manifest_payload())

    assert [row['decision_ts'] for row in labeled_rows] == [
        DEFAULT_DECISION_TS,
        DEFAULT_DECISION_TS + (4 * DEFAULT_LABEL_SECONDS),
        DEFAULT_DECISION_TS + (5 * DEFAULT_LABEL_SECONDS),
        DEFAULT_DECISION_TS + (6 * DEFAULT_LABEL_SECONDS),
        DEFAULT_DECISION_TS + (7 * DEFAULT_LABEL_SECONDS),
    ]
    assert all(int(row['deployment_eligible']) == 1 for row in census_rows)


def test_dataset_manifest_marks_support_gap_when_target_census_has_extra_strata(storage):
    _seed_rows(storage, count=8)
    _save_background_census(storage, base_decision_ts=DEFAULT_DECISION_TS - (6 * DEFAULT_LABEL_SECONDS))
    service = ResearchDatasetService(storage=storage)

    manifest = service.create_dataset_manifest(build_manifest_payload())

    assert manifest['support_overlap_result'] == 'gap_detected'
    assert manifest['dataset_status'] == 'research_only'


def test_sampling_stride_only_downsamples_train_split(storage):
    _seed_rows(storage, count=40)
    service = ResearchDatasetService(storage=storage)

    full_stride = service.create_dataset_manifest(build_manifest_payload())
    sparse_stride = service.create_dataset_manifest(
        {
            **build_manifest_payload(),
            'sampling_stride_sec': DEFAULT_LABEL_SECONDS * 2,
        }
    )

    assert sparse_stride['train_sample_count'] < full_stride['train_sample_count']
    assert sparse_stride['val_sample_count'] == full_stride['val_sample_count']
    assert sparse_stride['test_sample_count'] == full_stride['test_sample_count']


def test_dataset_manifest_ignores_legacy_session_coupled_census(storage):
    _seed_rows(storage, count=8)
    for index in range(8):
        _update_census(
            storage,
            decision_ts=DEFAULT_DECISION_TS + (index * DEFAULT_LABEL_SECONDS),
            observation_source_kind='legacy_session_coupled_v0',
        )
    service = ResearchDatasetService(storage=storage)

    manifest = service.create_dataset_manifest(build_manifest_payload())

    assert manifest['target_census_count'] == 0
    assert manifest['dataset_status'] == 'research_only'


def _seed_rows(storage: DataStorage, *, count: int) -> None:
    for index in range(count):
        decision_ts = DEFAULT_DECISION_TS + (index * DEFAULT_LABEL_SECONDS)
        _save_boundary_target(storage, decision_ts, index)
        _save_sample_index(storage, decision_ts)
        _save_census(storage, decision_ts, index, shift_gap=False)


def _update_sample(storage: DataStorage, *, decision_ts: int, **updates: object) -> None:
    row = storage.get_research_sample_index_15m(DEFAULT_SESSION_ID, decision_ts)
    storage.save_research_sample_index_15m(**{**row, **updates})


def _update_target(storage: DataStorage, *, decision_ts: int, **updates: object) -> None:
    row = storage.get_research_boundary_target_15m(DEFAULT_SESSION_ID, decision_ts)
    storage.save_research_boundary_target_15m(**{**row, **updates})


def _update_census(storage: DataStorage, *, decision_ts: int, **updates: object) -> None:
    row = storage.get_research_target_census(DEFAULT_INST_ID, decision_ts)
    shift_state = json.loads(str(row['shift_state_blob_json']))
    payload = {**row, **updates}
    payload['shift_state_blob_json'] = json.dumps(shift_state)
    storage.save_research_target_census(**payload)
