import tempfile
import unittest
from pathlib import Path

import numpy as np

from app.core.trend_research.models import FeatureSelectionResult, SelectedFeatureStats
from app.core.trend_research.sample_matrix import TrainingMatrix


def _selection(feature_name: str) -> FeatureSelectionResult:
    return FeatureSelectionResult(
        features=(
            SelectedFeatureStats(
                name=feature_name,
                category="test",
                mean=0.0,
                std=1.0,
                coverage=1.0,
                spearman_ic=0.8,
                stability_score=0.9,
            ),
        )
    )


class TrendResearchLogisticModelTest(unittest.TestCase):
    def test_dual_head_training_returns_probabilities_in_unit_interval(self):
        from app.core.trend_research.logistic_model import predict_probabilities, train_dual_logistic_heads

        features = np.asarray([[-2.0], [-1.0], [0.0], [1.0], [2.0]], dtype=float)
        top_labels = np.asarray([0, 0, 0, 1, 1], dtype=float)
        bottom_labels = np.asarray([1, 1, 0, 0, 0], dtype=float)

        top_head, bottom_head = train_dual_logistic_heads(features, top_labels, bottom_labels)
        top_probs = predict_probabilities(features, top_head)
        bottom_probs = predict_probabilities(features, bottom_head)

        self.assertTrue(np.all(top_probs >= 0.0))
        self.assertTrue(np.all(top_probs <= 1.0))
        self.assertTrue(np.all(bottom_probs >= 0.0))
        self.assertTrue(np.all(bottom_probs <= 1.0))
        self.assertGreater(top_probs[-1], top_probs[0])
        self.assertGreater(bottom_probs[0], bottom_probs[-1])

    def test_logistic_training_respects_positive_class_weight(self):
        from app.core.trend_research.logistic_model import predict_probabilities, train_logistic_head

        features = np.asarray([[0.0], [0.1], [0.2], [0.3], [0.4]], dtype=float)
        labels = np.asarray([0, 0, 0, 0, 1], dtype=float)

        plain_head = train_logistic_head(features, labels, positive_class_weight=1.0, negative_class_weight=1.0)
        weighted_head = train_logistic_head(features, labels, positive_class_weight=8.0, negative_class_weight=1.0)

        plain_probs = predict_probabilities(features, plain_head)
        weighted_probs = predict_probabilities(features, weighted_head)

        self.assertGreater(weighted_probs[-1], plain_probs[-1])

    def test_build_time_splits_is_contiguous_and_ordered(self):
        from app.core.trend_research.model_training import build_time_splits

        split = build_time_splits(tuple(range(10)), train_ratio=0.6, validation_ratio=0.2)

        self.assertEqual(split.train_indices, (0, 1, 2, 3, 4, 5))
        self.assertEqual(split.validation_indices, (6, 7))
        self.assertEqual(split.test_indices, (8, 9))
        self.assertLess(max(split.train_indices), min(split.validation_indices))
        self.assertLess(max(split.validation_indices), min(split.test_indices))

    def test_model_bundle_can_be_trained_saved_and_loaded(self):
        from app.core.trend_research.model_store import load_model_bundle, save_model_bundle
        from app.core.trend_research.model_training import train_trend_model

        rows = tuple((value,) for value in (-2.0, -1.0, 2.0, 1.0, -2.0, -1.0, 2.0, 1.0, -2.0, -1.0, 2.0, 1.0))
        top_labels = (0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 1, 1)
        bottom_labels = (1, 1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0)
        matrix = TrainingMatrix(
            inst_id="BTC-USDT-SWAP",
            feature_names=("alpha",),
            second_buckets=tuple(range(len(rows))),
            rows=rows,
            top_labels=top_labels,
            bottom_labels=bottom_labels,
        )

        bundle = train_trend_model(
            matrix,
            _selection("alpha"),
            horizon_minutes=60,
            reversal_threshold_floor=0.002,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            model_path = Path(temp_dir) / "trend_research_model.json"
            save_model_bundle(bundle, model_path)
            loaded = load_model_bundle(model_path)

        self.assertEqual(loaded.feature_names, ("alpha",))
        self.assertEqual(loaded.horizon_minutes, 60)
        self.assertEqual(len(loaded.top_head.weights), 1)
        self.assertGreaterEqual(loaded.top_validation.log_loss, 0.0)
