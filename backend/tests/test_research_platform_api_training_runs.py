from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest
from fastapi import HTTPException


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / 'app' / 'api' / 'research_platform.py'
    spec = importlib.util.spec_from_file_location('research_platform_api_module', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_start_training_run_api():
    module = _load_module()

    class FakeService:
        def start_training_run(self, payload):
            return {
                'run_id': 'run-1',
                'dataset_id': payload['dataset_id'],
                'evaluation_protocol_version': 'rolling_origin_v1',
            }

    class FakeContext:
        def research_platform(self):
            return FakeService()

    request = module.TrainingRunCreateRequest(
        dataset_id='dataset-1',
        candidate_set_ref='artifact://candidate-set/locked-v1.json',
        model_family='joint_density_model_v1',
        model_spec_ref='model://joint_density_model_v1/defaults',
        training_seed=7,
    )

    result = asyncio.run(module.start_training_run(request, FakeContext()))

    assert result['training_run']['run_id'] == 'run-1'
    assert result['training_run']['evaluation_protocol_version'] == 'rolling_origin_v1'


def test_list_training_runs_api():
    module = _load_module()

    class FakeService:
        def list_training_runs(self, *, dataset_id=None, limit=50):
            return [{'run_id': 'run-1', 'dataset_id': dataset_id, 'created_at': 1.0}]

    class FakeContext:
        def research_platform(self):
            return FakeService()

    result = asyncio.run(module.list_training_runs(dataset_id='dataset-1', limit=20, ctx=FakeContext()))

    assert isinstance(result['training_runs'], list)


def test_get_training_run_detail_api():
    module = _load_module()

    class FakeService:
        def get_training_run_detail(self, run_id):
            return {
                'run_id': run_id,
                'forecast_metrics_ref': 'artifact://forecast',
                'decision_metrics_ref': 'artifact://decision',
                'artifacts': {
                    'split_artifact': {
                        'origins': [{'inner_validation_folds': [{'fold_id': 'f-1'}]}],
                    },
                    'baseline_result': {'baseline': 'empirical_joint_distribution_v1'},
                    'bootstrap_result': {'ci_95': [0.1, 0.2]},
                },
            }

    class FakeContext:
        def research_platform(self):
            return FakeService()

    result = asyncio.run(module.get_training_run('run-1', FakeContext()))
    payload = result['training_run']

    assert 'forecast_metrics_ref' in payload
    assert 'decision_metrics_ref' in payload
    assert 'artifacts' in payload
    assert 'split_artifact' in payload['artifacts']
    assert 'inner_validation_folds' in payload['artifacts']['split_artifact']['origins'][0]
    assert 'baseline_result' in payload['artifacts']
    assert 'bootstrap_result' in payload['artifacts']


def test_start_training_run_api_returns_400_for_protocol_error():
    module = _load_module()

    class FakeService:
        def start_training_run(self, payload):
            raise ValueError('protocol-invalid: rolling-origin split requires at least one complete inner-validation fold per origin')

    class FakeContext:
        def research_platform(self):
            return FakeService()

    request = module.TrainingRunCreateRequest(
        dataset_id='dataset-1',
        candidate_set_ref='artifact://candidate-set/locked-v1.json',
        model_family='joint_density_model_v1',
        model_spec_ref='model://joint_density_model_v1/defaults',
        training_seed=7,
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(module.start_training_run(request, FakeContext()))

    assert exc_info.value.status_code == 400
    assert 'protocol-invalid' in exc_info.value.detail


def test_get_training_run_detail_api_returns_400_for_materialization_error():
    module = _load_module()

    class FakeService:
        def get_training_run_detail(self, run_id):
            raise ValueError('missing second_state window for sample sess-1:1713000900')

    class FakeContext:
        def research_platform(self):
            return FakeService()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(module.get_training_run('run-1', FakeContext()))

    assert exc_info.value.status_code == 400
    assert 'missing second_state window' in exc_info.value.detail
