import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.data_fetcher import Candle
from app.core.data_storage import DataStorage
from app.main import app


class AppContextStorageApiRegressionTest(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.storage = DataStorage(f"{self.tmp_dir.name}/regression.db")
        self.client = TestClient(app)

    def tearDown(self):
        try:
            self.client.close()
            if hasattr(self.storage, "_local") and getattr(self.storage._local, "connection", None):
                self.storage._local.connection.close()
                self.storage._local.connection = None
            self.tmp_dir.cleanup()
        except PermissionError:
            pass

    def _fake_ctx(self):
        storage = self.storage

        class FakeCtx:
            def storage(self):
                return storage

        return FakeCtx()

    def test_journal_entries_endpoint_uses_storage_method(self):
        self.storage.save_journal_entry({
            "title": "回归测试",
            "mode": "simulated",
        })

        with patch("app.api.journal.get_app_context", return_value=self._fake_ctx()):
            response = self.client.get("/api/journal/entries?limit=20&offset=0")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["success"])
        self.assertEqual(payload["total"], 1)

    def test_journal_tags_endpoint_uses_storage_method(self):
        self.storage.save_journal_entry({
            "title": "标签回归",
            "mode": "simulated",
            "tags": ["趋势"],
        })

        with patch("app.api.journal.get_app_context", return_value=self._fake_ctx()):
            response = self.client.get("/api/journal/tags")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"][0]["tag"], "趋势")

    def test_journal_stats_endpoint_uses_storage_method(self):
        self.storage.save_journal_entry({
            "title": "统计回归",
            "mode": "simulated",
            "tags": ["趋势"],
            "pnl_snapshot": 100,
        })

        with patch("app.api.journal.get_app_context", return_value=self._fake_ctx()):
            response = self.client.get("/api/journal/stats?mode=simulated&group_by=tag")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"]["total_entries"], 1)

    def test_risk_metrics_endpoint_uses_storage_method(self):
        for index in range(10):
            self.storage.save_portfolio_snapshot(
                mode="simulated",
                date=f"2026-03-{index + 1:02d}",
                total_equity=10000 + index * 100,
            )

        with patch("app.api.risk.get_app_context", return_value=self._fake_ctx()):
            response = self.client.get("/api/risk/metrics?mode=simulated&days=30")

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.json()["success"])

    def test_scanner_profiles_endpoint_uses_storage_method(self):
        self.storage.save_scanner_profile({
            "name": "回归方案",
            "conditions": [],
        })

        with patch("app.api.scanner.get_app_context", return_value=self._fake_ctx()):
            response = self.client.get("/api/scanner/profiles")

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["data"][0]["name"], "回归方案")

    def test_scanner_scan_endpoint_uses_storage_method(self):
        candles = []
        for index in range(50):
            candles.append(
                Candle(
                    timestamp=1700000000000 + index * 3600000,
                    open=100 + index,
                    high=101 + index,
                    low=99 + index,
                    close=100 + index,
                    volume=1000 + index * 10,
                    volume_ccy=0,
                )
            )
        self.storage.save_candles("TEST-USDT", "1H", candles, inst_type="SPOT")

        with patch("app.api.scanner.get_app_context", return_value=self._fake_ctx()):
            response = self.client.post(
                "/api/scanner/scan",
                json={
                    "symbols": ["TEST-USDT"],
                    "conditions": [{"indicator": "rsi", "operator": "lt", "value": 100}],
                    "timeframe": "1H",
                    "inst_type": "SPOT",
                },
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["scanned"], 1)
