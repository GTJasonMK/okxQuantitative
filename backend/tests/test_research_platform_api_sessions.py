from __future__ import annotations

import asyncio
import importlib.util
from pathlib import Path


def _load_module():
    module_path = Path(__file__).resolve().parents[1] / 'app' / 'api' / 'research_platform.py'
    spec = importlib.util.spec_from_file_location('research_platform_api_module', module_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_start_collection_session_api():
    module = _load_module()

    class FakeService:
        async def start_collection_session(self, payload):
            return {
                'session_id': 'sess-1',
                'inst_id': payload['inst_id'],
                'sampling_policy_id': payload['sampling_policy_id'],
                'integrity_policy_version': payload['integrity_policy_version'],
            }

    class FakeContext:
        def research_platform(self):
            return FakeService()

    request = module.ResearchSessionCreateRequest(
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

    result = asyncio.run(module.start_session(request, FakeContext()))

    assert result['session']['sampling_policy_id'] == 'manual_session_v1'
    assert result['session']['integrity_policy_version'] == 'strict_v1'


def test_list_and_get_collection_session_api():
    module = _load_module()

    class FakeService:
        def list_collection_sessions(self, *, limit=50):
            return [{'session_id': 'sess-1'}]

        def get_collection_session_detail(self, session_id):
            return {
                'session_id': session_id,
                'coverage': {'coverage_ratio': 1.0},
                'charts': {'price': [], 'trade': [], 'book': []},
            }

    class FakeContext:
        def research_platform(self):
            return FakeService()

    list_result = asyncio.run(module.list_sessions(limit=20, ctx=FakeContext()))
    detail_result = asyncio.run(module.get_session('sess-1', FakeContext()))

    assert 'sessions' in list_result
    assert 'coverage' in detail_result['session']
    assert 'charts' in detail_result['session']


def test_get_census_status_api():
    module = _load_module()

    class FakeService:
        def get_census_status(self):
            return {
                'shift_state_definition_version': 'compact_boundary_state_v1',
                'census_policy_version': 'deployment_eligible_boundary_census_v1',
            }

    class FakeContext:
        def research_platform(self):
            return FakeService()

    result = asyncio.run(module.get_census_status(FakeContext()))

    assert result['status']['shift_state_definition_version'] == 'compact_boundary_state_v1'
