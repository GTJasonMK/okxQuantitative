import unittest


class TrendResearchLabelingTest(unittest.TestCase):
    def test_build_swing_labels_marks_reversal_points(self):
        from app.core.trend_research.labeling import build_swing_labels
        from app.core.trend_research.models import FeatureBar1s

        prices = [100.0, 102.0, 105.0, 103.0, 99.0, 101.0]
        bars = [
            FeatureBar1s(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=float(1712365200 + idx),
                ts_local=float(1712365200 + idx),
                second_bucket=1712365200 + idx,
                mid_price=price,
                mark_price=price,
                index_price=price - 0.5,
                spread_bps=1.0,
                signed_trade_notional=0.0,
                trade_count=1,
                oi_delta=0.0,
                basis_zscore=0.0,
                data_quality="ok",
            )
            for idx, price in enumerate(prices)
        ]

        labels = build_swing_labels(bars, sigma_floor=0.01, threshold_multiplier=1.0)

        self.assertTrue(any(label.swing_top_confirmed for label in labels))
        self.assertTrue(any(label.swing_bottom_confirmed for label in labels))

    def test_build_swing_labels_prefers_mid_price_when_mark_price_is_stale(self):
        from app.core.trend_research.labeling import build_swing_labels
        from app.core.trend_research.models import FeatureBar1s

        mid_prices = [100.0, 102.0, 105.0, 103.0, 99.0, 101.0]
        bars = [
            FeatureBar1s(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=float(1712365200 + idx),
                ts_local=float(1712365200 + idx),
                second_bucket=1712365200 + idx,
                mid_price=price,
                mark_price=100.0,
                index_price=99.8,
                spread_bps=1.0,
                signed_trade_notional=0.0,
                trade_count=1,
                oi_delta=0.0,
                basis_zscore=0.2,
                data_quality="ok",
            )
            for idx, price in enumerate(mid_prices)
        ]

        labels = build_swing_labels(bars, sigma_floor=0.01, threshold_multiplier=1.0)

        self.assertTrue(any(label.swing_top_confirmed for label in labels))
        self.assertTrue(any(label.swing_bottom_confirmed for label in labels))

    def test_rank_candidate_factors_returns_stable_best_factor(self):
        from app.core.trend_research.factor_research import rank_candidate_factors
        from app.core.trend_research.models import CandidateFactorSeries, SwingLabel

        factors = [
            CandidateFactorSeries(
                inst_id="BTC-USDT-SWAP",
                factor_name="signed_trade_notional_z",
                values=[0.2, 0.4, 0.8, -0.5],
            ),
        ]
        labels = [
            SwingLabel(
                inst_id="BTC-USDT-SWAP",
                second_bucket=1712365200 + idx,
                trend_state="uptrend",
                swing_top_confirmed=value < 0,
                swing_bottom_confirmed=value > 0,
                time_to_top=10,
                time_to_bottom=0,
            )
            for idx, value in enumerate([0.2, 0.4, 0.8, -0.5])
        ]

        ranked = rank_candidate_factors(factors, labels)

        self.assertEqual(ranked[0].factor_name, "signed_trade_notional_z")
        self.assertGreaterEqual(ranked[0].stability_score, 0.0)

    def test_rank_candidate_factors_keeps_negative_signal_stability_and_normalizes_direction(self):
        from app.core.trend_research.factor_research import rank_candidate_factors
        from app.core.trend_research.models import CandidateFactorSeries, SwingLabel

        factors = [
            CandidateFactorSeries(
                inst_id="BTC-USDT-SWAP",
                factor_name="basis_zscore_z",
                values=[-4.0, 4.0, -3.5, 3.5, -3.0, 3.0, -2.5, 2.5],
            ),
        ]
        labels = [
            SwingLabel(
                inst_id="BTC-USDT-SWAP",
                second_bucket=1712365200 + idx,
                trend_state="range",
                swing_top_confirmed=idx % 2 == 1,
                swing_bottom_confirmed=idx % 2 == 0,
                time_to_top=0 if idx % 2 == 1 else 10,
                time_to_bottom=0 if idx % 2 == 0 else 10,
            )
            for idx in range(8)
        ]

        ranked = rank_candidate_factors(factors, labels)

        self.assertEqual(ranked[0].factor_name, "basis_zscore_z")
        self.assertLess(ranked[0].spearman_ic, 0.0)
        self.assertGreater(ranked[0].stability_score, 0.0)
        self.assertLessEqual(abs(ranked[0].spearman_ic), 1.0)
        self.assertLessEqual(ranked[0].stability_score, 1.0)
