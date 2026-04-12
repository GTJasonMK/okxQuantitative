import unittest

from app.core.trend_research.models import FeatureBar1s


def _bar(minute_index: int, price: float) -> FeatureBar1s:
    second_bucket = minute_index * 60
    return FeatureBar1s(
        inst_id="BTC-USDT-SWAP",
        ts_exchange=float(second_bucket),
        ts_local=float(second_bucket),
        second_bucket=second_bucket,
        mid_price=price,
        mark_price=price,
        index_price=price,
        spread_bps=10.0,
        signed_trade_notional=0.0,
        trade_count=0,
        oi_delta=0.0,
        basis_zscore=0.0,
        data_quality="ok",
        bid_price=price - 0.5,
        ask_price=price + 0.5,
        bid_size=10.0,
        ask_size=10.0,
        open_price=price,
        high_price=price,
        low_price=price,
        close_price=price,
        microprice=price,
    )


def _bars(prices: list[float]) -> list[FeatureBar1s]:
    return [_bar(index, price) for index, price in enumerate(prices)]


class ExtremaTargetsTest(unittest.TestCase):
    def test_build_extrema_targets_marks_local_top_and_bottom_across_horizons(self):
        from app.core.trend_research.extrema_targets import build_extrema_targets

        bars = _bars([100.0, 104.0, 109.0, 115.0, 110.0, 103.0, 96.0, 99.0, 105.0, 112.0, 120.0])

        for horizon_minutes in (30, 60, 120):
            with self.subTest(horizon_minutes=horizon_minutes):
                targets = build_extrema_targets(bars, horizon_minutes=horizon_minutes)
                first = targets[0]

                self.assertTrue(first.top_event)
                self.assertTrue(first.bottom_event)
                self.assertEqual(first.time_to_top_seconds, 180)
                self.assertEqual(first.time_to_bottom_seconds, 360)
                self.assertAlmostEqual(first.top_forward_return, 0.15)
                self.assertAlmostEqual(first.bottom_forward_return, 0.04)
                self.assertGreater(first.top_reversal_return, first.reversal_threshold)
                self.assertGreater(first.bottom_reversal_return, first.reversal_threshold)

    def test_build_extrema_targets_uses_realized_volatility_with_named_floor(self):
        from app.core.trend_research.extrema_targets import MIN_REVERSAL_FLOOR, build_extrema_targets

        calm_bars = _bars([100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 103.0, 97.0, 105.0])
        volatile_bars = _bars([100.0, 110.0, 90.0, 112.0, 88.0, 100.0, 103.0, 97.0, 105.0])

        calm_targets = build_extrema_targets(calm_bars, horizon_minutes=30, volatility_window_seconds=300)
        volatile_targets = build_extrema_targets(volatile_bars, horizon_minutes=30, volatility_window_seconds=300)

        self.assertAlmostEqual(calm_targets[5].reversal_threshold, MIN_REVERSAL_FLOOR)
        self.assertGreater(volatile_targets[5].reversal_threshold, MIN_REVERSAL_FLOOR)
        self.assertGreater(volatile_targets[5].realized_volatility, calm_targets[5].realized_volatility)

    def test_build_extrema_targets_requires_post_extrema_reversal(self):
        from app.core.trend_research.extrema_targets import build_extrema_targets

        rising_bars = _bars([100.0, 104.0, 108.0, 112.0, 116.0, 120.0])
        falling_bars = _bars([120.0, 116.0, 112.0, 108.0, 104.0, 100.0])

        rising_targets = build_extrema_targets(rising_bars, horizon_minutes=30)
        falling_targets = build_extrema_targets(falling_bars, horizon_minutes=30)

        self.assertFalse(rising_targets[0].top_event)
        self.assertIsNone(rising_targets[0].time_to_top_seconds)
        self.assertFalse(falling_targets[0].bottom_event)
        self.assertIsNone(falling_targets[0].time_to_bottom_seconds)
