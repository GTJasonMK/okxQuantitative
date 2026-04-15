from __future__ import annotations

from pathlib import Path

import pytest

from app.core.data_storage import DataStorage
from app.core.research_platform.dataset.service import ResearchDatasetService
from app.core.research_platform.training.service import ResearchTrainingService
from tests.research_platform_manifest_helpers import create_dataset_manifest


@pytest.fixture
def storage(tmp_path: Path):
    instance = DataStorage(tmp_path / 'research_dataset_delete.db')
    yield instance
    connection = getattr(instance, '_local', None)
    if connection is not None and getattr(connection, 'connection', None) is not None:
        connection.connection.close()
        connection.connection = None


def test_delete_dataset_manifest_rejects_manifest_with_training_runs(storage):
    manifest = create_dataset_manifest(storage, sample_count=24)
    dataset_service = ResearchDatasetService(storage=storage)
    training_service = ResearchTrainingService(storage=storage, dataset_service=dataset_service)
    training_service.start_training_run(
        {
            'dataset_id': manifest['dataset_id'],
            'candidate_set_ref': 'artifact://candidate-set/locked-v1.json',
            'model_family': 'joint_density_model_v1',
            'model_spec_ref': 'model://joint_density_model_v1/defaults',
            'training_seed': 7,
        }
    )

    with pytest.raises(RuntimeError, match='delete referenced training runs first'):
        dataset_service.delete_dataset_manifest(manifest['dataset_id'])

    assert storage.get_research_dataset_manifest(manifest['dataset_id']) is not None


def test_delete_dataset_manifest_removes_manifest_when_unreferenced(storage):
    manifest = create_dataset_manifest(storage)
    dataset_service = ResearchDatasetService(storage=storage)

    deleted = dataset_service.delete_dataset_manifest(manifest['dataset_id'])

    assert deleted['dataset_id'] == manifest['dataset_id']
    assert deleted['deleted_dataset_count'] == 1
    assert storage.get_research_dataset_manifest(manifest['dataset_id']) is None
    assert storage.get_research_artifact(manifest['strata_fit_ref']) is None
    assert storage.get_research_artifact(manifest['weight_fit_ref']) is None
