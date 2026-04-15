from __future__ import annotations

import asyncio
from pathlib import Path

import pytest

from app.core.data_storage import DataStorage
from app.core.research_platform.census.runtime import CensusObservationRuntime


@pytest.fixture
def storage(tmp_path: Path):
    instance = DataStorage(tmp_path / 'research_census_runtime.db')
    yield instance
    connection = getattr(instance, '_local', None)
    if connection is not None and getattr(connection, 'connection', None) is not None:
        connection.connection.close()
        connection.connection = None


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


def test_census_runtime_start_writes_first_independent_second_state(storage):
    ws_manager = _FakeWsManager()
    runtime = CensusObservationRuntime(
        storage=storage,
        inst_id='BTC-USDT-SWAP',
        fetcher=_FakeFetcher(),
        ws_manager=ws_manager,
        book_channel='books5',
        state_poll_interval=60.0,
        now_fn=lambda: 1713000899.2,
        sleep_fn=_sleep_forever,
    )

    asyncio.run(runtime.start())
    rows = storage.list_research_census_second_states_for_inst(
        'BTC-USDT-SWAP',
        end_ts=1713000900,
        lookback_sec=5,
    )

    assert len(rows) == 1
    assert rows[0]['inst_id'] == 'BTC-USDT-SWAP'
    assert ws_manager.subscribed_trades == ['BTC-USDT-SWAP']
    assert ws_manager.subscribed_books == [('BTC-USDT-SWAP', 'books5')]


def test_census_runtime_stop_releases_subscriptions(storage):
    ws_manager = _FakeWsManager()
    runtime = CensusObservationRuntime(
        storage=storage,
        inst_id='BTC-USDT-SWAP',
        fetcher=_FakeFetcher(),
        ws_manager=ws_manager,
        book_channel='books5',
        state_poll_interval=60.0,
        now_fn=lambda: 1713000899.2,
        sleep_fn=_sleep_forever,
    )

    asyncio.run(runtime.start())
    asyncio.run(runtime.stop())

    assert ws_manager.trade_callbacks == []
    assert ws_manager.book_callbacks == []
    assert ws_manager.unsubscribed_trades == ['BTC-USDT-SWAP']
    assert ws_manager.unsubscribed_books == [('BTC-USDT-SWAP', 'books5')]


async def _sleep_forever(seconds: float) -> None:
    raise asyncio.CancelledError
