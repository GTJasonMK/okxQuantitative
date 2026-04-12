import json
import unittest


class _FakeFetcher:
    def get_mark_price(self, inst_id):
        return {"inst_id": inst_id, "mark_price": 60002.0, "ts": 1712365200200}

    def get_index_price(self, inst_id):
        return {"inst_id": inst_id, "index_price": 59997.0, "ts": 1712365200200}

    def get_open_interest(self, inst_id):
        return {"inst_id": inst_id, "open_interest": 1200.0, "ts": 1712365200200}

    def get_funding_rate(self, inst_id):
        return {
            "inst_id": inst_id,
            "funding_rate": 0.0001,
            "premium": 5.0,
            "ts": 1712365200200,
        }


class _FakeStorage:
    def __init__(self):
        self.saved_bars = []

    def save_feature_bars_1s(self, bars):
        self.saved_bars.extend(bars)
        return len(bars)

    def list_feature_bars_1s(self, inst_id, limit=100):
        return []

    def save_inference_snapshots(self, rows):
        return len(rows)

    def list_latest_inference_snapshots(self, limit=100, inst_ids=None):
        return []

    def list_factor_scores(self, inst_id, limit=20):
        return []


class _FakeWSManager:
    def add_trade_callback(self, callback):
        return None

    def remove_trade_callback(self, callback):
        return None

    def add_book_callback(self, callback):
        return None

    def remove_book_callback(self, callback):
        return None

    async def subscribe_trades(self, inst_ids):
        return None

    async def subscribe_books(self, inst_ids, channel="books5"):
        return None

    async def unsubscribe_trades(self, inst_ids):
        return None

    async def unsubscribe_books(self, inst_ids, channel="books5"):
        return None


class TrendResearchBooks5Test(unittest.TestCase):
    def test_feature_builder_ignores_books5_depth_for_non_whitelisted_instrument(self):
        from app.core.trend_research.models import BookTopEvent
        from app.core.trend_research.service import TrendResearchService

        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=_FakeStorage(),
            fetcher=_FakeFetcher(),
            ws_manager=_FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )

        service.on_book(
            "ETH-USDT-SWAP",
            BookTopEvent(
                inst_id="ETH-USDT-SWAP",
                ts_exchange=1712365200.05,
                ts_local=1712365200.05,
                bid_price=3199.0,
                ask_price=3201.0,
                bid_size=10.0,
                ask_size=8.0,
                bid_levels=((3199.0, 10.0), (3198.0, 8.0), (3197.0, 6.0), (3196.0, 4.0), (3195.0, 2.0)),
                ask_levels=((3201.0, 8.0), (3202.0, 6.0), (3203.0, 4.0), (3204.0, 2.0), (3205.0, 1.0)),
            ),
        )

        self.assertIsNone(service.builders["BTC-USDT-SWAP"]._book)

    def test_websocket_manager_parses_all_five_books5_levels(self):
        from app.core.websocket_manager import OKXWebSocketManager

        manager = OKXWebSocketManager(is_simulated=True, outbound=None)
        book_events = []
        manager.add_book_callback(lambda inst_id, event: book_events.append((inst_id, event)))

        manager._on_public_message(
            json.dumps(
                {
                    "arg": {"channel": "books5", "instId": "BTC-USDT-SWAP"},
                    "data": [
                        {
                            "asks": [
                                ["60001", "8", "0", "0"],
                                ["60002", "6", "0", "0"],
                                ["60003", "4", "0", "0"],
                                ["60004", "2", "0", "0"],
                                ["60005", "1", "0", "0"],
                            ],
                            "bids": [
                                ["59999", "12", "0", "0"],
                                ["59998", "10", "0", "0"],
                                ["59997", "8", "0", "0"],
                                ["59996", "6", "0", "0"],
                                ["59995", "4", "0", "0"],
                            ],
                            "ts": "1712365200200",
                        }
                    ],
                }
            )
        )

        self.assertEqual(len(book_events), 1)
        self.assertEqual(len(book_events[0][1].bid_levels), 5)
        self.assertEqual(len(book_events[0][1].ask_levels), 5)
        self.assertEqual(book_events[0][1].bid_levels[-1], (59995.0, 4.0))
        self.assertEqual(book_events[0][1].ask_levels[-1], (60005.0, 1.0))


class TrendResearchBooks5IntegrationTest(unittest.IsolatedAsyncioTestCase):
    async def test_service_flushes_multi_level_books5_features_for_whitelist(self):
        from app.core.trend_research.models import BookTopEvent
        from app.core.trend_research.service import TrendResearchService

        storage = _FakeStorage()
        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=storage,
            fetcher=_FakeFetcher(),
            ws_manager=_FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )

        await service.sync_contract_state_once()
        service.on_book(
            "BTC-USDT-SWAP",
            BookTopEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365200.05,
                ts_local=1712365200.05,
                bid_price=59999.0,
                ask_price=60001.0,
                bid_size=12.0,
                ask_size=8.0,
                bid_levels=((59999.0, 12.0), (59998.0, 10.0), (59997.0, 8.0), (59996.0, 6.0), (59995.0, 4.0)),
                ask_levels=((60001.0, 8.0), (60002.0, 6.0), (60003.0, 4.0), (60004.0, 2.0), (60005.0, 1.0)),
            ),
        )

        service.flush_once(second_bucket=1712365200)

        bar = storage.saved_bars[0]
        self.assertEqual(bar.book_level_count, 5)
        self.assertAlmostEqual(bar.multi_level_book_imbalance, 19.0 / 61.0)
        self.assertAlmostEqual(bar.book_slope, -0.4875)
