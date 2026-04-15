from app.core.data_center_collection.contract_state_poller import ContractStatePoller
from app.core.data_center_collection.market_feed_adapter import MarketFeedAdapter


class _DummyWsManager:
    pass


def test_market_feed_adapter_normalizes_trade_and_book_messages():
    adapter = MarketFeedAdapter(
        ws_manager=_DummyWsManager(),
        inst_id='BTC-USDT-SWAP',
        book_channel='books5',
    )
    trade_events = adapter.normalize(
        {
            'arg': {'channel': 'trades', 'instId': 'BTC-USDT-SWAP'},
            'data': [{'px': '65000', 'sz': '1', 'side': 'buy', 'ts': '1713000000000'}],
        }
    )
    book_events = adapter.normalize(
        {
            'arg': {'channel': 'books5', 'instId': 'BTC-USDT-SWAP'},
            'data': [{'ts': '1713000000100', 'bids': [['64999.5', '12']], 'asks': [['65000.5', '10']]}],
        }
    )

    assert trade_events[0].inst_id == 'BTC-USDT-SWAP'
    assert trade_events[0].price == 65000.0
    assert book_events[0].bid_price == 64999.5
    assert book_events[0].ask_price == 65000.5


def test_contract_state_poller_reads_snapshot_from_fetcher():
    class _DummyFetcher:
        def get_mark_price(self, inst_id):
            return {'mark_price': 65000.1, 'ts': 1713000000000}

        def get_index_price(self, inst_id):
            return {'index_price': 65000.0, 'ts': 1713000000000}

        def get_open_interest(self, inst_id):
            return {'open_interest': 3200000.0, 'ts': 1713000000000}

        def get_funding_rate(self, inst_id):
            return {'funding_rate': 0.0001, 'premium': 1.5, 'ts': 1713000000000}

    poller = ContractStatePoller(fetcher=_DummyFetcher(), inst_id='BTC-USDT-SWAP')
    snapshot = poller.read_snapshot()

    assert snapshot.inst_id == 'BTC-USDT-SWAP'
    assert snapshot.mark_price == 65000.1
