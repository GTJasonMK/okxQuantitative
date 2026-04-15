import pytest

from app.core.data_center_collection.runtime_registry import CollectionRuntimeRegistry


class _DummyRunner:
    async def start(self):
        return None

    async def stop(self):
        return None


def test_runtime_registry_rejects_multiple_active_sessions():
    registry = CollectionRuntimeRegistry()
    registry.register('sess-1', _DummyRunner())

    with pytest.raises(ValueError, match='active collection session already exists'):
        registry.register('sess-2', _DummyRunner())


def test_runtime_registry_unregisters_runner():
    registry = CollectionRuntimeRegistry()
    registry.register('sess-1', _DummyRunner())

    registry.unregister('sess-1')

    assert registry.get('sess-1') is None
