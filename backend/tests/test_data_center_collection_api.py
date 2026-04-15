from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path

import pytest
from fastapi import HTTPException

from app.core.research_platform_delete_errors import CollectionSessionDeleteBlockedError


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / 'app' / 'api' / 'data_center_collection.py'
    spec = importlib.util.spec_from_file_location('data_center_collection_api_module', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_list_and_get_data_center_collection_sessions():
    module = _load_module()

    class FakeService:
        def list_collection_sessions(self, *, limit=50):
            return [{'session_id': 'sess-1', 'inst_id': 'BTC-USDT-SWAP'}]

        def get_collection_session_detail(self, session_id):
            return {
                'session_id': session_id,
                'progress': {
                    'written_seconds': 12,
                    'remaining_seconds': 1788,
                    'seconds_to_full_window': 7188,
                    'seconds_to_next_boundary': 543,
                },
                'coverage': {'coverage_ratio': 0.98},
            }

    class FakeContext:
        def research_platform(self):
            return FakeService()

    list_result = asyncio.run(module.list_collection_sessions(limit=20, ctx=FakeContext()))
    detail_result = asyncio.run(module.get_collection_session('sess-1', ctx=FakeContext()))

    assert list_result['sessions'][0]['session_id'] == 'sess-1'
    assert detail_result['session']['progress']['written_seconds'] == 12
    assert detail_result['session']['coverage']['coverage_ratio'] == 0.98


def test_start_stop_and_census_status_use_data_center_collection_contract():
    module = _load_module()

    class FakeService:
        async def start_collection_session(self, payload):
            return {'session_id': 'sess-1', 'inst_id': payload['inst_id']}

        async def stop_collection_session(self, session_id):
            return {'session_id': session_id, 'status': 'stopped'}

        def get_census_status(self):
            return {'census_policy_version': 'deployment_eligible_boundary_census_v1'}

    class FakeContext:
        def research_platform(self):
            return FakeService()

    request = module.DataCenterCollectionSessionCreateRequest(
        inst_id='BTC-USDT-SWAP',
        planned_duration_sec=1800,
        trigger_mode='manual',
        trigger_note='operator-started',
        sampling_policy_id='manual_session_v1',
        integrity_policy_version='strict_v1',
        collector_version='research_collector_v1',
        feature_recipe_version='second_state_causal_tensor_v1',
        book_channel='books5',
    )

    started = asyncio.run(module.start_collection_session(request, ctx=FakeContext()))
    stopped = asyncio.run(module.stop_collection_session('sess-1', ctx=FakeContext()))
    census = asyncio.run(module.get_collection_census_status(ctx=FakeContext()))

    assert started['session']['inst_id'] == 'BTC-USDT-SWAP'
    assert stopped['session']['status'] == 'stopped'
    assert census['status']['census_policy_version'] == 'deployment_eligible_boundary_census_v1'


def test_start_collection_session_returns_503_when_runtime_bootstrap_fails():
    module = _load_module()

    class FakeService:
        async def start_collection_session(self, payload):
            raise RuntimeError('market feed unavailable')

    class FakeContext:
        def research_platform(self):
            return FakeService()

    request = module.DataCenterCollectionSessionCreateRequest(
        inst_id='BTC-USDT-SWAP',
        planned_duration_sec=1800,
        trigger_mode='manual',
        trigger_note='operator-started',
        sampling_policy_id='manual_session_v1',
        integrity_policy_version='strict_v1',
        collector_version='research_collector_v1',
        feature_recipe_version='second_state_causal_tensor_v1',
        book_channel='books5',
    )

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(module.start_collection_session(request, ctx=FakeContext()))

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == 'market feed unavailable'


def test_delete_collection_session_returns_deleted_session_payload():
    module = _load_module()

    class FakeService:
        async def delete_collection_session(self, session_id):
            return {
                'session_id': session_id,
                'deleted_second_state_count': 1,
                'deleted_sample_index_count': 1,
                'deleted_boundary_target_count': 1,
                'deleted_session_count': 1,
            }

    class FakeContext:
        def research_platform(self):
            return FakeService()

    result = asyncio.run(module.delete_collection_session('sess-1', ctx=FakeContext()))

    assert result['deleted_session']['session_id'] == 'sess-1'
    assert result['deleted_session']['deleted_session_count'] == 1


def test_delete_collection_session_returns_409_when_referenced_by_dataset():
    module = _load_module()

    class FakeService:
        async def delete_collection_session(self, session_id):
            raise CollectionSessionDeleteBlockedError.referenced_by_datasets(
                session_id,
                ['dataset-1'],
            )

    class FakeContext:
        def research_platform(self):
            return FakeService()

    with pytest.raises(HTTPException) as exc_info:
        asyncio.run(module.delete_collection_session('sess-1', ctx=FakeContext()))

    assert exc_info.value.status_code == 409
    assert exc_info.value.detail['blocking_dataset_ids'] == ['dataset-1']
