import math
import unittest


def _bar(second_bucket, **overrides):
    from app.core.trend_research.models import FeatureBar1s

    payload = {
        "inst_id": "BTC-USDT-SWAP",
        "ts_exchange": float(second_bucket),
        "ts_local": float(second_bucket),
        "second_bucket": second_bucket,
        "mid_price": 100.5,
        "mark_price": 100.7,
        "index_price": 100.2,
        "spread_bps": 99.50248756218906,
        "signed_trade_notional": 0.0,
        "trade_count": 0,
        "oi_delta": 0.0,
        "basis_zscore": 0.5,
        "data_quality": "ok",
        "bid_price": 100.0,
        "ask_price": 101.0,
        "bid_size": 10.0,
        "ask_size": 12.0,
        "buy_notional": 0.0,
        "sell_notional": 0.0,
        "buy_count": 0,
        "sell_count": 0,
        "max_trade_notional": 0.0,
        "open_price": 100.5,
        "high_price": 100.5,
        "low_price": 100.5,
        "close_price": 100.5,
        "microprice": 100.45454545454545,
        "basis_bps": 49.9001996007984,
        "open_interest": 1200.0,
        "funding_rate": 0.0001,
        "funding_delta": 0.0,
        "premium": 5.0,
    }
    payload.update(overrides)
    return FeatureBar1s(**payload)


class RollingStatsTest(unittest.TestCase):
    def test_shared_rolling_helpers_compute_expected_values(self):
        from app.core.trend_research.rolling_stats import (
            efficiency_ratio_series,
            rolling_mean_series,
            realized_range_series,
            realized_volatility_series,
            rolling_extrema,
            rolling_quantile_series,
            rolling_return_series,
            safe_divide,
        )

        closes = [100.0, 105.0, 103.0, 108.0]
        highs = [101.0, 106.0, 104.0, 109.0]
        lows = [99.0, 103.0, 101.0, 107.0]

        self.assertAlmostEqual(safe_divide(3.0, 2.0), 1.5)
        self.assertEqual(safe_divide(3.0, 0.0), 0.0)
        self.assertEqual(rolling_return_series(closes, window=2)[0], 0.0)
        self.assertAlmostEqual(rolling_return_series(closes, window=2)[-1], (108.0 / 103.0) - 1.0)
        self.assertEqual(rolling_extrema(closes, window=3), ([100.0, 105.0, 105.0, 108.0], [100.0, 100.0, 100.0, 103.0]))
        self.assertEqual(
            rolling_mean_series([10.0, 10.0, 40.0], window=2, include_current=False),
            [10.0, 10.0, 10.0],
        )
        self.assertEqual(
            rolling_quantile_series([80.0, 70.0, 30.0], window=2, quantile=0.75, include_current=False),
            [80.0, 80.0, 77.5],
        )
        self.assertGreater(realized_volatility_series(closes, window=3)[-1], 0.0)
        self.assertGreater(realized_range_series(highs, lows, closes, window=3)[-1], 0.0)
        self.assertAlmostEqual(efficiency_ratio_series([100.0, 104.0, 102.0, 106.0], window=3)[-1], 0.6)


class FactorCatalogTest(unittest.TestCase):
    def test_registry_exposes_metadata_for_registered_factors(self):
        from app.core.trend_research.factor_catalog import get_factor_definitions

        definitions = {definition.name: definition for definition in get_factor_definitions()}

        self.assertIn("signed_trade_notional_z", definitions)
        self.assertIn("queue_imbalance", definitions)
        self.assertEqual(definitions["queue_imbalance"].category, "microstructure")
        self.assertEqual(definitions["queue_imbalance"].tier, 0)
        self.assertEqual(
            definitions["queue_imbalance"].required_fields,
            ("bid_size", "ask_size"),
        )
        self.assertEqual(definitions["multi_level_book_imbalance"].tier, 1)
        self.assertFalse(definitions["multi_level_book_imbalance"].is_available([]))

    def test_microstructure_factor_formulas_match_expected_values(self):
        from app.core.trend_research.factors_microstructure import (
            compute_microprice_premium_bps_series,
            compute_ofi_top_book_series,
            compute_queue_imbalance_series,
            compute_spread_level_bps_series,
        )

        bars = [
            _bar(1, bid_size=10.0, ask_size=12.0, microprice=100.45454545454545),
            _bar(2, bid_size=13.0, ask_size=9.0, microprice=100.5909090909091),
            _bar(3, bid_price=99.0, ask_price=100.0, bid_size=8.0, ask_size=11.0, mid_price=99.5, microprice=99.42105263157895),
        ]

        queue = compute_queue_imbalance_series(bars)
        premium = compute_microprice_premium_bps_series(bars)
        spread = compute_spread_level_bps_series(bars)
        ofi = compute_ofi_top_book_series(bars)

        self.assertAlmostEqual(queue[0], -2.0 / 22.0)
        self.assertAlmostEqual(queue[1], 4.0 / 22.0)
        self.assertAlmostEqual(premium[1], ((100.5909090909091 - 100.5) / 100.5) * 10000.0)
        self.assertAlmostEqual(spread[2], ((100.0 - 99.0) / 99.5) * 10000.0)
        self.assertEqual(ofi[0], 0.0)
        self.assertAlmostEqual(ofi[1], 6.0)
        self.assertAlmostEqual(ofi[2], -24.0)

    def test_trade_flow_factor_formulas_match_expected_values(self):
        from app.core.trend_research.factors_trade_flow import (
            compute_buy_burst_strength_series,
            compute_large_trade_share_series,
            compute_sell_burst_strength_series,
            compute_signed_volume_imbalance_series,
            compute_trade_intensity_series,
        )

        bars = [
            _bar(
                1,
                buy_notional=40.0,
                sell_notional=60.0,
                buy_count=2,
                sell_count=3,
                max_trade_notional=80.0,
                buy_burst_count=2,
                sell_burst_count=3,
                buy_burst_notional=40.0,
                sell_burst_notional=60.0,
            ),
            _bar(
                2,
                buy_notional=40.0,
                sell_notional=60.0,
                buy_count=2,
                sell_count=3,
                max_trade_notional=70.0,
                buy_burst_count=2,
                sell_burst_count=2,
                buy_burst_notional=40.0,
                sell_burst_notional=45.0,
            ),
            _bar(
                3,
                buy_notional=160.0,
                sell_notional=40.0,
                buy_count=4,
                sell_count=1,
                max_trade_notional=30.0,
                buy_burst_count=3,
                sell_burst_count=1,
                buy_burst_notional=120.0,
                sell_burst_notional=40.0,
            ),
            _bar(
                4,
                buy_notional=20.0,
                sell_notional=80.0,
                buy_count=1,
                sell_count=4,
                max_trade_notional=90.0,
                buy_burst_count=1,
                sell_burst_count=4,
                buy_burst_notional=20.0,
                sell_burst_notional=80.0,
            ),
        ]

        self.assertAlmostEqual(compute_signed_volume_imbalance_series(bars)[0], -0.2)
        self.assertEqual(compute_trade_intensity_series(bars), [1.0, 1.0, 1.5, 0.875])
        self.assertEqual(compute_large_trade_share_series(bars), [0.8, 0.0, 0.0, 0.9])
        self.assertAlmostEqual(compute_buy_burst_strength_series(bars)[2], 0.6)
        self.assertAlmostEqual(compute_sell_burst_strength_series(bars)[0], 0.6)
        self.assertAlmostEqual(compute_sell_burst_strength_series(bars)[1], 0.425)

    def test_price_structure_factor_formulas_match_expected_values(self):
        from app.core.trend_research.factors_price_structure import (
            compute_breakout_pressure_series,
            compute_distance_to_window_extrema_series,
            compute_momentum_series,
            compute_realized_range_factor_series,
            compute_realized_volatility_factor_series,
            compute_trend_efficiency_series,
        )

        bars = [
            _bar(1, close_price=100.0, high_price=101.0, low_price=99.0, bid_size=8.0, ask_size=12.0, buy_notional=30.0, sell_notional=70.0),
            _bar(2, close_price=104.0, high_price=105.0, low_price=100.0, bid_size=13.0, ask_size=7.0, buy_notional=80.0, sell_notional=20.0),
            _bar(3, close_price=102.0, high_price=103.0, low_price=101.0, bid_size=11.0, ask_size=9.0, buy_notional=40.0, sell_notional=60.0),
            _bar(4, close_price=106.0, high_price=107.0, low_price=102.0, bid_size=16.0, ask_size=4.0, buy_notional=90.0, sell_notional=10.0),
        ]

        momentum = compute_momentum_series(bars, window=3)
        position = compute_distance_to_window_extrema_series(bars)
        realized_vol = compute_realized_volatility_factor_series(bars)
        realized_range = compute_realized_range_factor_series(bars)
        efficiency = compute_trend_efficiency_series(bars)
        breakout = compute_breakout_pressure_series(bars)

        self.assertAlmostEqual(momentum[-1], 0.06)
        self.assertAlmostEqual(position[2], 0.5)
        self.assertAlmostEqual(position[-1], 1.0)
        self.assertGreater(realized_vol[-1], 0.0)
        self.assertGreater(realized_range[-1], 0.0)
        self.assertAlmostEqual(efficiency[-1], 0.6)
        self.assertGreater(breakout[-1], 0.0)

    def test_perpetual_and_liquidity_factor_formulas_match_expected_values(self):
        from app.core.trend_research.factors_liquidity import (
            compute_amihud_illiquidity_series,
            compute_depth_to_vol_ratio_series,
            compute_impact_per_notional_series,
        )
        from app.core.trend_research.factors_perpetual import (
            compute_basis_momentum_series,
            compute_funding_basis_divergence_series,
            compute_premium_shock_series,
            compute_price_oi_quadrant_series,
        )

        bars = [
            _bar(1, close_price=100.0, mid_price=100.0, basis_bps=10.0, funding_rate=0.0001, funding_delta=0.0, premium=1.0, open_interest=1200.0, oi_delta=0.0, signed_trade_notional=100.0, buy_notional=40.0, sell_notional=60.0, bid_size=10.0, ask_size=12.0),
            _bar(2, close_price=102.0, mid_price=102.0, basis_bps=18.0, funding_rate=0.0002, funding_delta=0.0001, premium=1.5, open_interest=1250.0, oi_delta=50.0, signed_trade_notional=200.0, buy_notional=70.0, sell_notional=30.0, bid_price=101.0, ask_price=103.0, bid_size=14.0, ask_size=8.0),
            _bar(3, close_price=101.0, mid_price=101.0, basis_bps=5.0, funding_rate=-0.0001, funding_delta=-0.0003, premium=0.4, open_interest=1220.0, oi_delta=-30.0, signed_trade_notional=-150.0, buy_notional=25.0, sell_notional=75.0, bid_price=100.0, ask_price=102.0, bid_size=8.0, ask_size=16.0),
        ]

        basis_momentum = compute_basis_momentum_series(bars)
        price_oi_quadrant = compute_price_oi_quadrant_series(bars)
        funding_basis_divergence = compute_funding_basis_divergence_series(bars)
        premium_shock = compute_premium_shock_series(bars)
        amihud = compute_amihud_illiquidity_series(bars)
        impact = compute_impact_per_notional_series(bars)
        depth_to_vol = compute_depth_to_vol_ratio_series(bars)

        self.assertEqual(basis_momentum[0], 0.0)
        self.assertAlmostEqual(basis_momentum[1], 8.0)
        self.assertEqual(price_oi_quadrant[0], 0.0)
        self.assertEqual(price_oi_quadrant[1], 1.0)
        self.assertEqual(price_oi_quadrant[2], -0.5)
        self.assertAlmostEqual(funding_basis_divergence[1], 16.0)
        self.assertGreater(premium_shock[2], 0.0)
        self.assertGreater(amihud[1], 0.0)
        self.assertGreater(impact[1], 0.0)
        self.assertLess(impact[2], 0.0)
        self.assertGreater(depth_to_vol[1], 0.0)

    def test_build_candidate_factor_series_uses_registry_and_skips_unavailable(self):
        from app.core.trend_research.research_runtime import build_candidate_factor_series

        bars = [
            _bar(1, signed_trade_notional=-500.0, trade_count=3),
            _bar(2, signed_trade_notional=700.0, trade_count=5, bid_size=15.0, ask_size=5.0, microprice=100.75),
            _bar(3, signed_trade_notional=200.0, trade_count=4, bid_price=99.0, ask_price=100.0, mid_price=99.5, bid_size=8.0, ask_size=11.0, microprice=99.42105263157895),
        ]

        series = build_candidate_factor_series("BTC-USDT-SWAP", bars)
        factor_names = {item.factor_name for item in series}

        self.assertIn("signed_trade_notional_z", factor_names)
        self.assertIn("queue_imbalance", factor_names)
        self.assertIn("ofi_top_book", factor_names)
        self.assertIn("signed_volume_imbalance", factor_names)
        self.assertIn("trade_intensity", factor_names)
        self.assertIn("momentum_30s", factor_names)
        self.assertIn("distance_to_window_extrema", factor_names)
        self.assertIn("basis_bps", factor_names)
        self.assertIn("amihud_illiquidity", factor_names)
        self.assertNotIn("multi_level_book_imbalance", factor_names)
        queue_series = next(item for item in series if item.factor_name == "queue_imbalance")
        self.assertEqual(len(queue_series.values), len(bars))
        self.assertFalse(any(math.isnan(value) for value in queue_series.values))

    def test_build_candidate_factor_series_includes_books5_factors_when_available(self):
        from app.core.trend_research.research_runtime import build_candidate_factor_series

        bars = [
            _bar(1, book_level_count=5, multi_level_book_imbalance=0.2, book_slope=-0.1),
            _bar(2, book_level_count=5, multi_level_book_imbalance=0.4, book_slope=0.05),
            _bar(3, book_level_count=5, multi_level_book_imbalance=0.1, book_slope=-0.2),
        ]

        series = build_candidate_factor_series("BTC-USDT-SWAP", bars)
        factor_names = {item.factor_name for item in series}

        self.assertIn("multi_level_book_imbalance", factor_names)
        self.assertIn("book_slope", factor_names)
