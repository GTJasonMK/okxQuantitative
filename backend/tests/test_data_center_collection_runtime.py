from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.core.data_center_collection.runtime import build_collection_runtime
from app.core.data_storage import DataStorage


@pytest.fixture
def storage(tmp_path: Path):
    instance = DataStorage(tmp_path / 'collection_runtime.db')
    yield instance
    connection = getattr(instance, '_local', None)
    if connection is not None and getattr(connection, 'connection', None) is not None:
        connection.connection.close()
        connection.connection = None


def _create_session(storage, *, planned_duration_sec=2):
    session_id = storage.create_research_collection_session(
        inst_id='BTC-USDT-SWAP',
        planned_duration_sec=planned_duration_sec,
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


class _FakeFetcher:
    def get_mark_price(self, inst_id):
        return {'mark_price': 65000.1, 'ts': 1713000000000}

    def get_index_price(self, inst_id):
        return {'index_price': 65000.0, 'ts': 1713000000000}

    def get_open_interest(self, inst_id):
        return {'open_interest': 3200000.0, 'ts': 1713000000000}

    def get_funding_rate(self, inst_id):
        return {'funding_rate': 0.0001, 'premium': 1.5, 'ts': 1713000000000}


class _FakeWsManager:
    def __init__(self):
        self.trade_callbacks = []
        self.book_callbacks = []
        self.subscribed_trades = []
        self.subscribed_books = []
        self.unsubscribed_trades = []
        self.unsubscribed_books = []

    def add_trade_callback(self, callback):
        self.trade_callbacks.append(callback)

    def remove_trade_callback(self, callback):
        if callback in self.trade_callbacks:
            self.trade_callbacks.remove(callback)

    def add_book_callback(self, callback):
        self.book_callbacks.append(callback)

    def remove_book_callback(self, callback):
        if callback in self.book_callbacks:
            self.book_callbacks.remove(callback)

    async def subscribe_trades(self, inst_ids):
        self.subscribed_trades.extend(inst_ids)

    async def subscribe_books(self, inst_ids, channel='books5'):
        self.subscribed_books.extend((inst_id, channel) for inst_id in inst_ids)

    async def unsubscribe_trades(self, inst_ids):
        self.unsubscribed_trades.extend(inst_ids)

    async def unsubscribe_books(self, inst_ids, channel='books5'):
        self.unsubscribed_books.extend((inst_id, channel) for inst_id in inst_ids)


def test_collection_runtime_start_writes_first_second_state(storage):
    session = _create_session(storage, planned_duration_sec=2)
    events = []
    ws_manager = _FakeWsManager()
    runtime = build_collection_runtime(
        storage=storage,
        session=session,
        fetcher=_FakeFetcher(),
        ws_manager=ws_manager,
        publish_event=events.append,
        state_poll_interval=60.0,
    )

    updated = asyncio.run(runtime.start())
    rows = storage.list_research_second_states(session['session_id'], limit=10)

    assert updated['status'] == 'running'
    assert len(rows) == 1
    assert ws_manager.subscribed_trades == ['BTC-USDT-SWAP']
    assert ws_manager.subscribed_books == [('BTC-USDT-SWAP', 'books5')]
    assert [event['event'] for event in events[:4]] == [
        'session_started',
        'second_flushed',
        'session_quality_updated',
        'session_running',
    ]


def test_collection_runtime_stop_releases_callbacks_and_subscriptions(storage):
    session = _create_session(storage, planned_duration_sec=2)
    ws_manager = _FakeWsManager()
    runtime = build_collection_runtime(
        storage=storage,
        session=session,
        fetcher=_FakeFetcher(),
        ws_manager=ws_manager,
        publish_event=lambda payload: None,
        state_poll_interval=60.0,
    )

    asyncio.run(runtime.start())
    stopped = asyncio.run(runtime.stop(stop_reason='manual_stop'))

    assert stopped['status'] == 'stopped'
    assert ws_manager.trade_callbacks == []
    assert ws_manager.book_callbacks == []
    assert ws_manager.unsubscribed_trades == ['BTC-USDT-SWAP']
    assert ws_manager.unsubscribed_books == [('BTC-USDT-SWAP', 'books5')]
