import importlib.util
from types import SimpleNamespace
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient


class TrendResearchApiTest(unittest.TestCase):
    def _load_module(self):
        module_path = Path(__file__).resolve().parents[1] / "app" / "api" / "trend_research.py"
        spec = importlib.util.spec_from_file_location("trend_research_api_module", module_path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def _build_client(self, fake_context):
        from app.core.app_context import get_app_context

        module = self._load_module()
        app = FastAPI()
        app.include_router(module.router)
        app.dependency_overrides[get_app_context] = lambda: fake_context
        return TestClient(app)

    def test_inference_engine_returns_model_not_ready_snapshot_without_bundle(self):
        from app.core.trend_research.inference import TrendInferenceEngine
        from app.core.trend_research.models import FeatureBar1s

        engine = TrendInferenceEngine()
        bar = FeatureBar1s(
            inst_id="BTC-USDT-SWAP",
            ts_exchange=1712365200.0,
            ts_local=1712365200.0,
            second_bucket=1712365200,
            mid_price=60000.0,
            mark_price=60002.0,
            index_price=59997.0,
            spread_bps=1.0,
            signed_trade_notional=62500.0,
            trade_count=12,
            oi_delta=0.2,
            basis_zscore=1.5,
            data_quality="ok",
            close_price=60000.0,
        )

        snapshot = engine.build_snapshot(bar, recent_bars=(bar,))

        self.assertEqual(snapshot.inst_id, "BTC-USDT-SWAP")
        self.assertEqual(snapshot.trend_state, "model_not_ready")
        self.assertEqual(snapshot.current_price, 60000.0)
        self.assertIsNone(snapshot.predicted_top_price)

    def test_inference_engine_builds_direct_prediction_snapshot(self):
        from app.core.trend_research.direct_models import DirectExtremaMetrics, DirectExtremaModelBundle, DirectExtremaModelConfig
        from app.core.trend_research.inference import TrendInferenceEngine
        from app.core.trend_research.models import FeatureBar1s

        bundle = DirectExtremaModelBundle(
            trained_at="2026-04-07T00:00:00+00:00",
            config=DirectExtremaModelConfig(
                architecture="tcn",
                input_minutes=120,
                horizon_minutes=60,
                bucket_seconds=60,
                hidden_channels=(32, 64),
                dropout=0.1,
                feature_names=("queue_imbalance", "basis_bps"),
            ),
            normalization_means=(0.0, 0.0),
            normalization_stds=(1.0, 1.0),
            state_dict={},
            metrics=DirectExtremaMetrics(
                top_time_mae_minutes=4.0,
                bottom_time_mae_minutes=5.0,
                top_price_mae_bps=40.0,
                bottom_price_mae_bps=55.0,
                joint_hit_rate=0.42,
            ),
        )
        engine = TrendInferenceEngine(model_bundle=bundle)
        bar = FeatureBar1s(
            inst_id="BTC-USDT-SWAP",
            ts_exchange=1712365200.0,
            ts_local=1712365200.0,
            second_bucket=1712365200,
            mid_price=60000.0,
            mark_price=60002.0,
            index_price=59997.0,
            spread_bps=1.0,
            signed_trade_notional=62500.0,
            trade_count=12,
            oi_delta=0.2,
            basis_zscore=1.5,
            data_quality="ok",
            close_price=60000.0,
        )

        with patch(
            "app.core.trend_research.inference.build_online_sequence_window",
            return_value=SimpleNamespace(
                inst_id="BTC-USDT-SWAP",
                anchor_minute_bucket=1712365200 // 60,
                feature_names=("queue_imbalance", "basis_bps"),
                feature_rows=((0.1, 1.0),) * 120,
                current_price=60000.0,
            ),
        ), patch(
            "app.core.trend_research.inference.run_direct_model",
            return_value=SimpleNamespace(
                top_time_bucket=14,
                bottom_time_bucket=37,
                top_return=0.02,
                bottom_return=-0.01,
                top_distribution=tuple(0.0 for _ in range(14)) + (0.6,) + tuple(0.0 for _ in range(45)),
                bottom_distribution=tuple(0.0 for _ in range(37)) + (0.7,) + tuple(0.0 for _ in range(22)),
            ),
        ):
            snapshot = engine.build_snapshot(bar, recent_bars=(bar,))

        self.assertEqual(snapshot.predicted_top_eta_seconds, 900)
        self.assertEqual(snapshot.predicted_bottom_eta_seconds, 2280)
        self.assertAlmostEqual(snapshot.predicted_top_price, 61212.080402, places=6)
        self.assertEqual(snapshot.trend_state, "uptrend_confirmed")

    def test_inference_endpoint_returns_rows(self):
        class FakeService:
            def get_settings(self):
                return {
                    "enabled": True,
                    "whitelist": ["BTC-USDT-SWAP"],
                    "feature_bar_seconds": 1,
                    "state_sync_seconds": 30,
                    "book_channel": "books5",
                }

            def list_inference(self, limit=100):
                return [
                    {
                        "inst_id": "BTC-USDT-SWAP",
                        "second_bucket": 1712365200,
                        "current_price": 60000.0,
                        "trend_score": 100.0,
                        "trend_state": "uptrend_confirmed",
                        "predicted_top_eta_seconds": 900,
                        "predicted_bottom_eta_seconds": 2280,
                        "predicted_top_price": 61212.080402,
                        "predicted_bottom_price": 59402.990025,
                        "predicted_top_return": 0.02,
                        "predicted_bottom_return": -0.01,
                        "top_time_distribution": [0.0] * 14 + [0.6] + [0.0] * 45,
                        "bottom_time_distribution": [0.0] * 37 + [0.7] + [0.0] * 22,
                        "confidence": 0.7,
                        "data_quality": "ok",
                    }
                ]

        class FakeContext:
            def trend_research(self):
                return FakeService()

        client = self._build_client(FakeContext())
        response = client.get("/api/trend-research/inference")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["enabled"])
        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["whitelist"], ["BTC-USDT-SWAP"])
        self.assertEqual(payload["rows"][0]["inst_id"], "BTC-USDT-SWAP")
        self.assertEqual(payload["rows"][0]["trend_state"], "uptrend_confirmed")

    def test_inference_endpoint_reports_disabled_status(self):
        class FakeService:
            def get_settings(self):
                return {
                    "enabled": False,
                    "whitelist": [],
                    "feature_bar_seconds": 1,
                    "state_sync_seconds": 30,
                    "book_channel": "books5",
                }

            def list_inference(self, limit=100):
                return []

        class FakeContext:
            def trend_research(self):
                return FakeService()

        client = self._build_client(FakeContext())
        response = client.get("/api/trend-research/inference")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertFalse(payload["enabled"])
        self.assertEqual(payload["status"], "disabled")
        self.assertEqual(payload["whitelist"], [])
        self.assertEqual(payload["rows"], [])

    def test_inference_endpoint_exposes_runtime_error_status(self):
        class FakeService:
            def get_settings(self):
                return {
                    "enabled": True,
                    "whitelist": ["BTC-USDT-SWAP"],
                    "feature_bar_seconds": 1,
                    "state_sync_seconds": 30,
                    "book_channel": "books5",
                }

            def get_runtime_error(self):
                return "BTC-USDT-SWAP funding unavailable"

            def list_inference(self, limit=100):
                return []

        class FakeContext:
            def trend_research(self):
                return FakeService()

        client = self._build_client(FakeContext())
        response = client.get("/api/trend-research/inference")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "error")
        self.assertEqual(payload["runtime_error"], "BTC-USDT-SWAP funding unavailable")

    def test_process_endpoint_returns_pipeline_snapshot(self):
        class FakeService:
            def get_settings(self):
                return {
                    "enabled": True,
                    "whitelist": ["BTC-USDT-SWAP"],
                    "feature_bar_seconds": 1,
                    "state_sync_seconds": 30,
                    "book_channel": "books5",
                }

            def list_inference(self, limit=100):
                return [
                    {
                        "inst_id": "BTC-USDT-SWAP",
                        "second_bucket": 1712365200,
                        "trend_score": 62.5,
                        "trend_state": "uptrend_confirmed",
                        "top_probability": 0.12,
                        "bottom_probability": 0.71,
                        "confidence": 0.88,
                        "data_quality": "ok",
                    }
                ]

            def get_model_status(self):
                return {
                    "ready": True,
                    "trained_at": "2026-04-06T00:00:00+00:00",
                    "horizon_minutes": 60,
                    "selected_feature_count": 8,
                }

            def build_process_snapshot(self, *, bar_limit=20):
                return {
                    "summary": {
                        "whitelist_count": 1,
                        "trade_ready_count": 1,
                        "book_ready_count": 1,
                        "state_ready_count": 1,
                        "feature_ready_count": 1,
                        "inference_ready_count": 1,
                    },
                    "instruments": [
                        {
                            "inst_id": "BTC-USDT-SWAP",
                            "pipeline_state": "inference_ready",
                            "stages": {
                                "trade": {"ready": True},
                                "book": {"ready": True},
                                "state": {"ready": True},
                                "feature": {"ready": True},
                                "inference": {"ready": True},
                            },
                            "latest_feature_bar": {
                                "inst_id": "BTC-USDT-SWAP",
                                "second_bucket": 1712365200,
                                "trade_count": 12,
                                "signed_trade_notional": 62500.0,
                                "data_quality": "ok",
                            },
                            "latest_inference": {
                                "inst_id": "BTC-USDT-SWAP",
                                "trend_state": "uptrend_confirmed",
                            },
                            "recent_feature_bars": [
                                {
                                    "inst_id": "BTC-USDT-SWAP",
                                    "second_bucket": 1712365200,
                                    "signed_trade_notional": 62500.0,
                                    "trade_count": 12,
                                    "data_quality": "ok",
                                }
                            ],
                        }
                    ],
                    "bar_limit": bar_limit,
                }

        class FakeContext:
            def trend_research(self):
                return FakeService()

        client = self._build_client(FakeContext())
        response = client.get("/api/trend-research/process?bar_limit=10")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ready")
        self.assertTrue(payload["model_status"]["ready"])
        self.assertEqual(payload["summary"]["inference_ready_count"], 1)
        self.assertEqual(payload["bar_limit"], 10)
        self.assertEqual(payload["instruments"][0]["inst_id"], "BTC-USDT-SWAP")
        self.assertEqual(payload["instruments"][0]["pipeline_state"], "inference_ready")
        self.assertTrue(payload["instruments"][0]["stages"]["feature"]["ready"])

    def test_diagnostics_endpoint_returns_selected_snapshot(self):
        class FakeService:
            def build_diagnostics_snapshot(self, *, inst_id=None, timeline_limit=40):
                return {
                    "selected_inst_id": inst_id or "BTC-USDT-SWAP",
                    "instruments": [
                        {
                            "inst_id": "BTC-USDT-SWAP",
                            "pipeline_stage": "inference_ready",
                            "is_error": False,
                            "is_stale": False,
                        }
                    ],
                    "global_health": {
                        "whitelist_count": 1,
                        "active_count": 1,
                        "stale_count": 0,
                        "error_count": 0,
                        "last_event_at": 1712365200.0,
                    },
                    "instrument_health": {
                        "inst_id": "BTC-USDT-SWAP",
                        "pipeline_stage": "inference_ready",
                        "trade_age_seconds": 1.0,
                    },
                    "timeline": [
                        {
                            "sequence": 5,
                            "kind": "inference",
                            "label": "推断已生成",
                        }
                    ],
                    "details": {
                        "subscription_state": "subscribed",
                        "last_feature_bucket": 1712365200,
                    },
                }

        class FakeContext:
            def trend_research(self):
                return FakeService()

        client = self._build_client(FakeContext())
        response = client.get(
            "/api/trend-research/diagnostics?inst_id=BTC-USDT-SWAP&timeline_limit=30"
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["selected_inst_id"], "BTC-USDT-SWAP")
        self.assertEqual(payload["instrument_health"]["pipeline_stage"], "inference_ready")
        self.assertEqual(payload["timeline"][0]["kind"], "inference")
        self.assertEqual(payload["details"]["subscription_state"], "subscribed")

    def test_factor_series_endpoint_returns_series_and_score_meta(self):
        class FakeService:
            def get_settings(self):
                return {
                    "enabled": True,
                    "whitelist": ["BTC-USDT-SWAP"],
                    "feature_bar_seconds": 1,
                    "state_sync_seconds": 30,
                    "book_channel": "books5",
                }

            def list_inference(self, limit=100):
                return []

            def list_factor_series(self, inst_id, *, lookback, limit=None):
                return {
                    "inst_id": inst_id,
                    "lookback": lookback,
                    "second_buckets": [1712365200, 1712365201],
                    "series": [
                        {
                            "factor_name": "momentum_60s",
                            "category": "price_structure",
                            "available": True,
                            "tier": 0,
                            "unavailable_reason": "",
                            "values": [0.0, 0.4],
                        }
                    ],
                    "score_meta": [
                        {
                            "factor_name": "momentum_60s",
                            "stability_score": 0.41,
                            "spearman_ic": 0.23,
                            "redundancy_cluster": "price",
                            "category": "price_structure",
                            "tier": 0,
                            "available": True,
                            "unavailable_reason": "",
                        }
                    ],
                }

        class FakeContext:
            def trend_research(self):
                return FakeService()

        client = self._build_client(FakeContext())
        response = client.get("/api/trend-research/factor-series/BTC-USDT-SWAP?lookback=1800")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["inst_id"], "BTC-USDT-SWAP")
        self.assertEqual(payload["second_buckets"], [1712365200, 1712365201])
        self.assertEqual(payload["series"][0]["factor_name"], "momentum_60s")
        self.assertEqual(payload["score_meta"][0]["stability_score"], 0.41)

    def test_config_endpoint_returns_settings_defaults_and_status(self):
        class FakeService:
            def get_settings(self):
                return {
                    "enabled": True,
                    "whitelist": ["BTC-USDT-SWAP"],
                    "feature_bar_seconds": 1,
                    "state_sync_seconds": 30,
                    "book_channel": "books5",
                }

            def get_default_settings(self):
                return {
                    "enabled": False,
                    "whitelist": ["BTC-USDT-SWAP", "ETH-USDT-SWAP"],
                    "feature_bar_seconds": 1,
                    "state_sync_seconds": 30,
                    "book_channel": "books5",
                }

            def list_inference(self, limit=100):
                return []

        class FakeContext:
            def trend_research(self):
                return FakeService()

        client = self._build_client(FakeContext())
        response = client.get("/api/trend-research/config")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["settings"]["whitelist"], ["BTC-USDT-SWAP"])
        self.assertEqual(payload["defaults"]["whitelist"], ["BTC-USDT-SWAP", "ETH-USDT-SWAP"])
        self.assertEqual(payload["status"], "collecting")

    def test_feature_bars_endpoint_returns_recent_rows(self):
        class FakeService:
            def get_settings(self):
                return {
                    "enabled": True,
                    "whitelist": ["BTC-USDT-SWAP"],
                    "feature_bar_seconds": 1,
                    "state_sync_seconds": 30,
                    "book_channel": "books5",
                }

            def list_inference(self, limit=100):
                return []

            def list_feature_bars(self, inst_id, limit=100):
                return [
                    {
                        "inst_id": inst_id,
                        "second_bucket": 1712365200,
                        "signed_trade_notional": 62500.0,
                        "trade_count": 12,
                        "data_quality": "ok",
                    }
                ]

        class FakeContext:
            def trend_research(self):
                return FakeService()

        client = self._build_client(FakeContext())
        response = client.get("/api/trend-research/feature-bars/BTC-USDT-SWAP?limit=10")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["inst_id"], "BTC-USDT-SWAP")
        self.assertEqual(payload["rows"][0]["trade_count"], 12)

    def test_factors_endpoint_returns_ranked_scores(self):
        class FakeService:
            def get_settings(self):
                return {
                    "enabled": True,
                    "whitelist": ["BTC-USDT-SWAP"],
                    "feature_bar_seconds": 1,
                    "state_sync_seconds": 30,
                    "book_channel": "books5",
                }

            def list_inference(self, limit=100):
                return []

            def rebuild_factor_scores(self, inst_id, *, lookback=3600, limit=20):
                return [
                    {
                        "inst_id": inst_id,
                        "factor_name": "signed_trade_notional_z",
                        "spearman_ic": 0.42,
                        "stability_score": 0.67,
                        "redundancy_cluster": "flow",
                        "category": "trade_flow",
                        "tier": 0,
                        "available": True,
                        "unavailable_reason": "",
                    },
                    {
                        "inst_id": inst_id,
                        "factor_name": "multi_level_book_imbalance",
                        "spearman_ic": None,
                        "stability_score": None,
                        "redundancy_cluster": "microstructure",
                        "category": "microstructure",
                        "tier": 1,
                        "available": False,
                        "unavailable_reason": "依赖多档盘口",
                    }
                ]

        class FakeContext:
            def trend_research(self):
                return FakeService()

        client = self._build_client(FakeContext())
        response = client.get("/api/trend-research/factors/BTC-USDT-SWAP?lookback=1800&limit=5")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["inst_id"], "BTC-USDT-SWAP")
        self.assertEqual(payload["lookback"], 1800)
        self.assertEqual(payload["rows"][0]["factor_name"], "signed_trade_notional_z")
        self.assertEqual(payload["rows"][0]["category"], "trade_flow")
        self.assertTrue(payload["rows"][0]["available"])
        self.assertFalse(payload["rows"][1]["available"])
        self.assertEqual(payload["rows"][1]["unavailable_reason"], "依赖多档盘口")

    def test_factors_endpoint_rejects_short_lookback(self):
        class FakeService:
            def get_settings(self):
                return {
                    "enabled": True,
                    "whitelist": ["BTC-USDT-SWAP"],
                    "feature_bar_seconds": 1,
                    "state_sync_seconds": 30,
                    "book_channel": "books5",
                }

            def list_inference(self, limit=100):
                return []

            def rebuild_factor_scores(self, inst_id, *, lookback=3600, limit=20):
                raise AssertionError("should not be called when lookback is invalid")

        class FakeContext:
            def trend_research(self):
                return FakeService()

        client = self._build_client(FakeContext())
        response = client.get("/api/trend-research/factors/BTC-USDT-SWAP?lookback=1200&limit=5")

        self.assertEqual(response.status_code, 422)

    def test_update_config_returns_422_for_invalid_swap(self):
        class FakeService:
            def get_settings(self):
                return {
                    "enabled": True,
                    "whitelist": [],
                    "feature_bar_seconds": 1,
                    "state_sync_seconds": 30,
                    "book_channel": "books5",
                }

            def list_inference(self, limit=100):
                return []

            async def apply_settings(self, settings, *, persist=False):
                raise ValueError("非法永续合约: BTC-USDT")

        class FakeContext:
            def trend_research(self):
                return FakeService()

        client = self._build_client(FakeContext())
        response = client.put(
            "/api/trend-research/config",
            json={
                "enabled": True,
                "whitelist": ["BTC-USDT"],
                "feature_bar_seconds": 1,
                "state_sync_seconds": 30,
                "book_channel": "books5",
            },
        )

        self.assertEqual(response.status_code, 422)
        self.assertIn("非法永续合约", response.json()["detail"])

    def test_model_endpoint_returns_model_status(self):
        class FakeService:
            def get_settings(self):
                return {
                    "enabled": True,
                    "whitelist": ["BTC-USDT-SWAP"],
                    "feature_bar_seconds": 1,
                    "state_sync_seconds": 30,
                    "book_channel": "books5",
                }

            def list_inference(self, limit=100):
                return []

            def get_model_status(self):
                return {
                    "ready": True,
                    "trained_at": "2026-04-06T00:00:00+00:00",
                    "horizon_minutes": 60,
                    "selected_feature_count": 8,
                }

        class FakeContext:
            def trend_research(self):
                return FakeService()

        client = self._build_client(FakeContext())
        response = client.get("/api/trend-research/model")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["model"]["ready"])
        self.assertEqual(payload["model"]["horizon_minutes"], 60)
        self.assertEqual(payload["model"]["selected_feature_count"], 8)

    def test_training_run_endpoint_returns_latest_snapshot(self):
        class FakeService:
            def get_settings(self):
                return {
                    "enabled": True,
                    "whitelist": ["BTC-USDT-SWAP"],
                    "feature_bar_seconds": 1,
                    "state_sync_seconds": 30,
                    "book_channel": "books5",
                }

            def list_inference(self, limit=1):
                return []

            def get_training_run(self):
                return {
                    "status": "running",
                    "current_stage": "train_epochs",
                    "progress_pct": 52.0,
                }

        class FakeContext:
            def trend_research(self):
                return FakeService()

        client = self._build_client(FakeContext())
        response = client.get("/api/trend-research/training-run")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json()["training_run"]["current_stage"],
            "train_epochs",
        )

    def test_retrain_model_endpoint_returns_409_when_training_already_running(self):
        class FakeService:
            def get_settings(self):
                return {
                    "enabled": True,
                    "whitelist": ["BTC-USDT-SWAP"],
                    "feature_bar_seconds": 1,
                    "state_sync_seconds": 30,
                    "book_channel": "books5",
                }

            def list_inference(self, limit=100):
                return []

            def get_model_status(self):
                return {
                    "ready": False,
                    "trained_at": "",
                    "horizon_minutes": 0,
                    "selected_feature_count": 0,
                }

            async def start_retrain_model(self, *, lookback=3600):
                raise RuntimeError("trend research training already running")

        class FakeContext:
            def trend_research(self):
                return FakeService()

        client = self._build_client(FakeContext())
        response = client.post("/api/trend-research/model/retrain?lookback=3600")

        self.assertEqual(response.status_code, 409)
        self.assertIn("already running", response.json()["detail"])
