from __future__ import annotations

from pathlib import Path

from app.core.data_storage import DataStorage
from app.core.research_platform.dataset.service import ResearchDatasetService
from app.core.research_platform.training.service import ResearchTrainingService
from tests.research_platform_dataset_helpers import close_storage
from tests.research_platform_manifest_helpers import (
    DEFAULT_DECISION_TS,
    DEFAULT_LABEL_SECONDS,
    DEFAULT_SESSION_ID,
    create_dataset_manifest,
)
from tests.test_research_platform_training_run import _seed_training_second_windows


def test_training_run_detail_remains_frozen_after_first_materialization(tmp_path: Path):
    storage = DataStorage(tmp_path / 'research_platform_artifact_freeze.db')
    try:
        dataset_service = ResearchDatasetService(storage=storage)
        training_service = ResearchTrainingService(storage=storage, dataset_service=dataset_service)
        manifest = create_dataset_manifest(storage, sample_count=24)
        _seed_training_second_windows(storage)
        run = training_service.start_training_run(
            {
                'dataset_id': manifest['dataset_id'],
                'candidate_set_ref': 'artifact://candidate-set/locked-v1.json',
                'model_family': 'joint_density_model_v1',
                'model_spec_ref': 'model://joint_density_model_v1/defaults',
                'training_seed': 7,
            }
        )

        detail = training_service.get_training_run_detail(run['run_id'])
        frozen_artifacts = detail['artifacts']
        mutation_ts = DEFAULT_DECISION_TS + (2 * DEFAULT_LABEL_SECONDS)
        storage.save_research_boundary_target_15m(
            target_id=f'{DEFAULT_SESSION_ID}:{mutation_ts}',
            session_id=DEFAULT_SESSION_ID,
            inst_id='BTC-USDT-SWAP',
            decision_ts=mutation_ts,
            anchor_second_bucket=mutation_ts - 1,
            anchor_close_price=65000.0,
            label_start_ts=mutation_ts,
            label_end_ts=mutation_ts + DEFAULT_LABEL_SECONDS,
            open_price=65000.0,
            high_price=70000.0,
            low_price=60000.0,
            close_price=69999.0,
            r_open=0.5,
            r_close=0.6,
            u=0.7,
            d=0.4,
            label_complete=1,
            invalid_reason='',
            label_definition_version='next_bar_15m_ohlc_reparam_from_session_seconds_v1',
        )

        replayed_detail = training_service.get_training_run_detail(run['run_id'])

        assert replayed_detail['artifacts'] == frozen_artifacts
    finally:
        close_storage(storage)
