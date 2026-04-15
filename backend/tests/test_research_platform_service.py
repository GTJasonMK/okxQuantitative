from app.core.app_context import get_app_context
from app.core.research_platform.service import ResearchPlatformService


def test_app_context_exposes_research_platform_service():
    ctx = get_app_context()
    service = ctx.research_platform()

    assert service is not None
    assert hasattr(service, 'start_collection_session')
    assert hasattr(service, 'stop_collection_session')
    assert hasattr(service, 'get_census_status')
    locks = service.get_protocol_locks()
    assert locks['shift_state_definition_version_v1'] == 'compact_boundary_state_v1'
    assert locks['census_policy_version_v1'] == 'deployment_eligible_boundary_census_v1'


def test_research_platform_forwards_collection_runtime_events():
    seen = []

    class _FakeCensus:
        enabled = False
        last_decision_ts = None

        async def start(self):
            return None

        async def stop(self):
            return None

    class _FakeDataset:
        pass

    class _FakeTraining:
        pass

    class _FakeStorage:
        pass

    class FakeCollectionService:
        def add_listener(self, listener):
            self.listener = listener

    service = ResearchPlatformService(
        collection_service=FakeCollectionService(),
        census_service=_FakeCensus(),
        dataset_service=_FakeDataset(),
        training_service=_FakeTraining(),
        storage=_FakeStorage(),
    )
    service.add_listener(seen.append)
    service._collection.listener({'event': 'session_running', 'session_id': 'sess-1'})
    service._collection.listener({'event': 'second_flushed', 'session_id': 'sess-1', 'second_bucket': 1713000000})

    assert seen[0]['event'] == 'session_running'
    assert seen[0]['session_id'] == 'sess-1'
    assert seen[1]['event'] == 'session_updated'
    assert seen[2]['event'] == 'second_flushed'
    assert seen[2]['second_bucket'] == 1713000000


def test_research_platform_does_not_emit_session_updated_for_session_deleted():
    seen = []

    class _FakeCensus:
        enabled = False
        last_decision_ts = None

        async def start(self):
            return None

        async def stop(self):
            return None

    class _FakeDataset:
        pass

    class _FakeTraining:
        pass

    class _FakeStorage:
        pass

    class FakeCollectionService:
        def add_listener(self, listener):
            self.listener = listener

    service = ResearchPlatformService(
        collection_service=FakeCollectionService(),
        census_service=_FakeCensus(),
        dataset_service=_FakeDataset(),
        training_service=_FakeTraining(),
        storage=_FakeStorage(),
    )
    service.add_listener(seen.append)
    service._collection.listener({'event': 'session_deleted', 'session_id': 'sess-1'})

    assert seen == [{'event': 'session_deleted', 'session_id': 'sess-1'}]


def test_research_platform_exposes_census_universe_count():
    class _FakeCensus:
        enabled = True
        last_decision_ts = 1713000900
        universe_count = 3

        async def start(self):
            return None

        async def stop(self):
            return None

    class _FakeDataset:
        pass

    class _FakeTraining:
        pass

    class _FakeStorage:
        pass

    class FakeCollectionService:
        def add_listener(self, listener):
            self.listener = listener

    service = ResearchPlatformService(
        collection_service=FakeCollectionService(),
        census_service=_FakeCensus(),
        dataset_service=_FakeDataset(),
        training_service=_FakeTraining(),
        storage=_FakeStorage(),
    )

    status = service.get_census_status()

    assert status['universe_count'] == 3
