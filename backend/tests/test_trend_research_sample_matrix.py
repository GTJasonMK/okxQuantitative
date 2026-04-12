import unittest

from app.core.trend_research.factor_definition import FactorDefinition
from app.core.trend_research.models import ExtremaTarget, FeatureBar1s


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


def _targets(bars: list[FeatureBar1s]) -> list[ExtremaTarget]:
    return [
        ExtremaTarget(
            inst_id=bar.inst_id,
            second_bucket=bar.second_bucket,
            horizon_minutes=60,
            realized_volatility=0.01,
            reversal_threshold=0.02,
            top_event=index == 1,
            bottom_event=index == 2,
            time_to_top_seconds=60 if index == 1 else None,
            time_to_bottom_seconds=60 if index == 2 else None,
            top_forward_return=0.03,
            bottom_forward_return=0.02,
            top_reversal_return=0.03,
            bottom_reversal_return=0.02,
        )
        for index, bar in enumerate(bars)
    ]


class TrendResearchSampleMatrixTest(unittest.TestCase):
    def test_training_matrix_and_latest_vector_share_stable_feature_order(self):
        from app.core.trend_research.sample_matrix import build_latest_feature_vector, build_training_matrix

        bars = _bars([100.0, 101.0, 102.0])
        targets = _targets(bars)
        definitions = (
            FactorDefinition(
                name="alpha",
                category="test",
                tier=0,
                required_fields=("mid_price",),
                compute_series=lambda rows: [bar.mid_price for bar in rows],
            ),
            FactorDefinition(
                name="beta",
                category="test",
                tier=0,
                required_fields=("close_price",),
                compute_series=lambda rows: [bar.close_price * 2.0 for bar in rows],
            ),
        )

        matrix = build_training_matrix(bars, targets, definitions=definitions)
        latest = build_latest_feature_vector(bars, definitions=definitions)

        self.assertEqual(matrix.feature_names, ("alpha", "beta"))
        self.assertEqual(latest.feature_names, matrix.feature_names)
        self.assertEqual(matrix.rows[-1], latest.values)

    def test_training_matrix_excludes_unavailable_factors_and_drops_missing_rows(self):
        from app.core.trend_research.sample_matrix import build_latest_feature_vector, build_training_matrix

        bars = _bars([100.0, 101.0, 102.0])
        targets = _targets(bars)
        definitions = (
            FactorDefinition(
                name="available",
                category="test",
                tier=0,
                required_fields=("mid_price",),
                compute_series=lambda rows: [1.0, 2.0, 3.0],
            ),
            FactorDefinition(
                name="unavailable",
                category="test",
                tier=1,
                required_fields=("book_level_count",),
                compute_series=lambda rows: [9.0, 9.0, 9.0],
                availability=lambda rows: False,
                unavailable_reason="needs books",
            ),
            FactorDefinition(
                name="sparse",
                category="test",
                tier=0,
                required_fields=("close_price",),
                compute_series=lambda rows: [10.0, None, 30.0],
            ),
        )

        matrix = build_training_matrix(bars, targets, definitions=definitions)
        latest = build_latest_feature_vector(bars, definitions=definitions)

        self.assertEqual(matrix.feature_names, ("available", "sparse"))
        self.assertEqual(matrix.second_buckets, (0, 120))
        self.assertEqual(matrix.rows, ((1.0, 10.0), (3.0, 30.0)))
        self.assertEqual(latest.values, (3.0, 30.0))

    def test_latest_feature_vector_raises_when_last_row_has_missing_value(self):
        from app.core.trend_research.sample_matrix import build_latest_feature_vector

        bars = _bars([100.0, 101.0, 102.0])
        definitions = (
            FactorDefinition(
                name="available",
                category="test",
                tier=0,
                required_fields=("mid_price",),
                compute_series=lambda rows: [1.0, 2.0, 3.0],
            ),
            FactorDefinition(
                name="missing_latest",
                category="test",
                tier=0,
                required_fields=("close_price",),
                compute_series=lambda rows: [10.0, 20.0, None],
            ),
        )

        with self.assertRaisesRegex(ValueError, "missing feature value"):
            build_latest_feature_vector(bars, definitions=definitions)
