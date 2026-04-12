import unittest


class FeatureBarBuilderTest(unittest.TestCase):
    def _book_event(self, **overrides):
        from app.core.trend_research.models import BookTopEvent

        payload = {
            "inst_id": "BTC-USDT-SWAP",
            "ts_exchange": 1712365200.05,
            "ts_local": 1712365200.05,
            "bid_price": 59999.0,
            "ask_price": 60001.0,
            "bid_size": 12.0,
            "ask_size": 8.0,
        }
        payload.update(overrides)
        return BookTopEvent(**payload)

    def _trade_event(self, **overrides):
        from app.core.trend_research.models import TradeTickEvent

        payload = {
            "inst_id": "BTC-USDT-SWAP",
            "ts_exchange": 1712365200.10,
            "ts_local": 1712365200.10,
            "price": 60001.0,
            "size": 0.4,
            "side": "buy",
        }
        payload.update(overrides)
        return TradeTickEvent(**payload)

    def _state_snapshot(self, **overrides):
        from app.core.trend_research.models import ContractStateSnapshot

        payload = {
            "inst_id": "BTC-USDT-SWAP",
            "ts_exchange": 1712365200.20,
            "ts_local": 1712365200.20,
            "mark_price": 60002.0,
            "index_price": 59997.0,
            "open_interest": 1200.0,
            "funding_rate": 0.0001,
            "premium": 5.0,
        }
        payload.update(overrides)
        return ContractStateSnapshot(**payload)

    def test_builder_flushes_normalized_bar(self):
        from app.core.trend_research.feature_builder import FeatureBarBuilder

        builder = FeatureBarBuilder(inst_id="BTC-USDT-SWAP")
        builder.apply_book(self._book_event())
        builder.apply_trade(self._trade_event())
        builder.apply_contract_state(self._state_snapshot())

        bar = builder.flush(second_bucket=1712365200)

        self.assertEqual(bar.inst_id, "BTC-USDT-SWAP")
        self.assertAlmostEqual(bar.mid_price, 60000.0)
        self.assertGreater(bar.signed_trade_notional, 0.0)
        self.assertEqual(bar.trade_count, 1)
        self.assertEqual(bar.data_quality, "ok")

    def test_flush_resets_trade_aggregates_but_keeps_last_snapshots(self):
        from app.core.trend_research.feature_builder import FeatureBarBuilder

        builder = FeatureBarBuilder(inst_id="BTC-USDT-SWAP")
        builder.apply_book(self._book_event())
        builder.apply_trade(self._trade_event())
        builder.apply_contract_state(self._state_snapshot())

        first_bar = builder.flush(second_bucket=1712365200)
        second_bar = builder.flush(second_bucket=1712365201)

        self.assertEqual(first_bar.trade_count, 1)
        self.assertGreater(first_bar.signed_trade_notional, 0.0)
        self.assertEqual(second_bar.trade_count, 0)
        self.assertEqual(second_bar.signed_trade_notional, 0.0)
        self.assertAlmostEqual(second_bar.mid_price, 60000.0)
        self.assertEqual(second_bar.mark_price, 60002.0)

    def test_builder_tracks_side_flow_ohlc_and_book_metrics(self):
        from app.core.trend_research.feature_builder import FeatureBarBuilder

        builder = FeatureBarBuilder(inst_id="BTC-USDT-SWAP")
        builder.apply_book(self._book_event(bid_size=15.0, ask_size=5.0))
        builder.apply_trade(self._trade_event(price=60001.0, size=0.4, side="buy"))
        builder.apply_trade(self._trade_event(price=60003.0, size=0.2, side="buy"))
        builder.apply_trade(self._trade_event(price=59998.0, size=0.5, side="sell"))
        builder.apply_contract_state(self._state_snapshot())

        bar = builder.flush(second_bucket=1712365200)

        self.assertEqual(bar.bid_size, 15.0)
        self.assertEqual(bar.ask_size, 5.0)
        self.assertAlmostEqual(bar.buy_notional, 36001.0)
        self.assertAlmostEqual(bar.sell_notional, 29999.0)
        self.assertEqual(bar.buy_count, 2)
        self.assertEqual(bar.sell_count, 1)
        self.assertAlmostEqual(bar.max_trade_notional, 29999.0)
        self.assertEqual(bar.buy_burst_count, 2)
        self.assertEqual(bar.sell_burst_count, 1)
        self.assertAlmostEqual(bar.buy_burst_notional, 36001.0)
        self.assertAlmostEqual(bar.sell_burst_notional, 29999.0)
        self.assertEqual(bar.open_price, 60001.0)
        self.assertEqual(bar.high_price, 60003.0)
        self.assertEqual(bar.low_price, 59998.0)
        self.assertEqual(bar.close_price, 59998.0)
        self.assertAlmostEqual(bar.microprice, 60000.5)

    def test_builder_tracks_funding_and_basis_deltas(self):
        from app.core.trend_research.feature_builder import FeatureBarBuilder

        builder = FeatureBarBuilder(inst_id="BTC-USDT-SWAP")
        builder.apply_book(self._book_event())
        builder.apply_contract_state(self._state_snapshot(funding_rate=0.0001, open_interest=1200.0))
        builder.apply_contract_state(self._state_snapshot(funding_rate=0.0004, open_interest=1205.0))

        bar = builder.flush(second_bucket=1712365200)

        self.assertAlmostEqual(bar.open_interest, 1205.0)
        self.assertAlmostEqual(bar.oi_delta, 5.0)
        self.assertAlmostEqual(bar.funding_rate, 0.0004)
        self.assertAlmostEqual(bar.funding_delta, 0.0003)
        self.assertAlmostEqual(bar.basis_bps, 0.8333750020834376)

    def test_builder_tracks_books5_multi_level_features(self):
        from app.core.trend_research.feature_builder import FeatureBarBuilder

        builder = FeatureBarBuilder(inst_id="BTC-USDT-SWAP")
        builder.apply_book(
            self._book_event(
                bid_levels=((59999.0, 12.0), (59998.0, 10.0), (59997.0, 8.0), (59996.0, 6.0), (59995.0, 4.0)),
                ask_levels=((60001.0, 8.0), (60002.0, 6.0), (60003.0, 4.0), (60004.0, 2.0), (60005.0, 1.0)),
            )
        )
        builder.apply_contract_state(self._state_snapshot())

        bar = builder.flush(second_bucket=1712365200)

        self.assertEqual(bar.book_level_count, 5)
        self.assertAlmostEqual(bar.multi_level_book_imbalance, 19.0 / 61.0)
        self.assertAlmostEqual(bar.book_slope, -0.4875)
