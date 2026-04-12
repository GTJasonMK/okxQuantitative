import os
import unittest
from dataclasses import FrozenInstanceError
from unittest.mock import patch


class TrendResearchConfigTest(unittest.TestCase):
    @patch.dict(os.environ, {
        "TREND_RESEARCH_ENABLED": "true",
        "TREND_RESEARCH_WHITELIST": "BTC-USDT-SWAP,ETH-USDT-SWAP",
        "TREND_RESEARCH_FEATURE_BAR_SECONDS": "1",
        "TREND_RESEARCH_STATE_SYNC_SECONDS": "30",
        "TREND_RESEARCH_BOOK_CHANNEL": "books5",
    }, clear=False)
    def test_from_env_parses_whitelist(self):
        from app.config import AppConfig

        cfg = AppConfig.from_env()

        self.assertTrue(cfg.trend_research.enabled)
        self.assertEqual(
            cfg.trend_research.whitelist,
            ("BTC-USDT-SWAP", "ETH-USDT-SWAP"),
        )
        self.assertEqual(cfg.trend_research.feature_bar_seconds, 1)
        self.assertEqual(cfg.trend_research.state_sync_seconds, 30)
        self.assertEqual(cfg.trend_research.book_channel, "books5")

    def test_feature_bar_model_is_immutable(self):
        from app.core.trend_research.models import FeatureBar1s

        bar = FeatureBar1s(
            inst_id="BTC-USDT-SWAP",
            ts_exchange=1712365200.0,
            ts_local=1712365200.2,
            second_bucket=1712365200,
            mid_price=60000.0,
            mark_price=60001.0,
            index_price=59995.0,
            spread_bps=1.2,
            signed_trade_notional=10000.0,
            trade_count=4,
            oi_delta=0.1,
            basis_zscore=1.5,
            data_quality="ok",
        )

        with self.assertRaises(FrozenInstanceError):
            bar.inst_id = "ETH-USDT-SWAP"
