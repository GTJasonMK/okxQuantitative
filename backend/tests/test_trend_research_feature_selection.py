import unittest

from app.core.trend_research.factor_definition import FactorDefinition
from app.core.trend_research.models import FactorScore


def _definition(name: str, category: str) -> FactorDefinition:
    return FactorDefinition(
        name=name,
        category=category,
        tier=0,
        required_fields=("mid_price",),
        compute_series=lambda rows: [1.0 for _ in rows],
    )


def _score(name: str, category: str, stability: float, spearman: float) -> FactorScore:
    return FactorScore(
        inst_id="BTC-USDT-SWAP",
        factor_name=name,
        spearman_ic=spearman,
        stability_score=stability,
        redundancy_cluster=category,
        category=category,
        tier=0,
        available=True,
        unavailable_reason="",
    )


class TrendResearchFeatureSelectionTest(unittest.TestCase):
    def test_select_training_features_filters_low_coverage_and_low_variation(self):
        from app.core.trend_research.feature_selection import select_training_features

        columns = (
            (_definition("alpha", "microstructure"), (1.0, 2.0, 3.0, 4.0)),
            (_definition("low_coverage", "microstructure"), (1.0, None, None, 4.0)),
            (_definition("flat", "trade_flow"), (5.0, 5.0, 5.0, 5.0)),
        )
        scores = [
            _score("alpha", "microstructure", 0.9, 0.6),
            _score("low_coverage", "microstructure", 0.8, 0.4),
            _score("flat", "trade_flow", 0.7, 0.3),
        ]

        result = select_training_features(columns, scores, min_coverage=0.75)

        self.assertEqual(result.feature_names, ("alpha",))
        self.assertAlmostEqual(result.train_means[0], 2.5)
        self.assertAlmostEqual(result.train_stds[0], 1.118033988749895)

    def test_select_training_features_prunes_only_highly_correlated_features_within_category(self):
        from app.core.trend_research.feature_selection import select_training_features

        columns = (
            (_definition("leader_a", "microstructure"), (1.0, 2.0, 3.0, 4.0)),
            (_definition("follower_a", "microstructure"), (2.0, 4.0, 6.0, 8.0)),
            (_definition("other_category", "trade_flow"), (2.0, 4.0, 6.0, 8.0)),
        )
        scores = [
            _score("leader_a", "microstructure", 0.9, 0.6),
            _score("follower_a", "microstructure", 0.8, 0.7),
            _score("other_category", "trade_flow", 0.7, 0.5),
        ]

        result = select_training_features(columns, scores, max_correlation=0.95)

        self.assertEqual(result.feature_names, ("leader_a", "other_category"))

    def test_select_training_features_uses_abs_ic_and_stability_for_ordering(self):
        from app.core.trend_research.feature_selection import select_training_features

        columns = (
            (_definition("stable", "perpetual"), (1.0, 1.5, 2.0, 2.5)),
            (_definition("strong_ic", "perpetual"), (4.0, 3.0, 2.0, 1.0)),
        )
        scores = [
            _score("stable", "perpetual", 0.95, 0.20),
            _score("strong_ic", "perpetual", 0.40, -0.80),
        ]

        result = select_training_features(columns, scores, max_correlation=0.99)

        self.assertEqual(result.feature_names, ("stable",))
