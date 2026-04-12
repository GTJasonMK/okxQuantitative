from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.core.app_context import get_app_context


class OKXOutboundMonitorApiTests(unittest.TestCase):
    def test_okx_outbound_timeline_api_returns_events_and_summary(self):
        module_path = Path(__file__).resolve().parents[1] / "app" / "api" / "system_monitor.py"
        spec = importlib.util.spec_from_file_location("system_monitor_module", module_path)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        system_monitor = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(system_monitor)

        ctx = get_app_context()
        ctx.okx_outbound_timeline().record_event_for_test(
            op_key="market.ticker",
            channel="rest",
            target_group="public",
            rule_key="public_ip",
            scope_key="public_ip",
            inst_id="BTC-USDT",
            mode="",
            result="ok",
            latency_ms=9,
        )

        app = FastAPI()
        app.include_router(system_monitor.router)
        client = TestClient(app)

        response = client.get(
            "/api/system/okx-outbound-timeline",
            params={"window_seconds": 600, "limit": 100},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertGreaterEqual(payload["summary"]["event_count"], 1)
        self.assertEqual(payload["events"][-1]["op_key"], "market.ticker")


if __name__ == "__main__":
    unittest.main()
