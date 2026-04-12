import unittest


class TrendResearchRuntimeSettingsTest(unittest.TestCase):
    def test_normalize_accepts_csv_and_newlines_and_deduplicates(self):
        from app.core.trend_research.settings import normalize_trend_research_settings

        settings = normalize_trend_research_settings(
            {
                "enabled": True,
                "whitelist": "btc-usdt-swap,\nETH-USDT-SWAP\nbtc-usdt-swap",
                "feature_bar_seconds": 2,
                "state_sync_seconds": 45,
                "book_channel": "books5",
            },
            defaults={
                "enabled": False,
                "whitelist": [],
                "feature_bar_seconds": 1,
                "state_sync_seconds": 30,
                "book_channel": "books5",
            },
        )

        self.assertEqual(settings["whitelist"], ["BTC-USDT-SWAP", "ETH-USDT-SWAP"])
        self.assertEqual(settings["feature_bar_seconds"], 2)
        self.assertEqual(settings["state_sync_seconds"], 45)

    def test_normalize_rejects_non_swap_symbols(self):
        from app.core.trend_research.settings import normalize_trend_research_settings

        with self.assertRaisesRegex(ValueError, "非法永续合约"):
            normalize_trend_research_settings(
                {"enabled": True, "whitelist": ["BTC-USDT"]},
                defaults={
                    "enabled": False,
                    "whitelist": [],
                    "feature_bar_seconds": 1,
                    "state_sync_seconds": 30,
                    "book_channel": "books5",
                },
            )

    def test_build_default_settings_uses_env_defaults(self):
        from app.core.trend_research.settings import build_default_trend_research_settings

        defaults = build_default_trend_research_settings(
            type(
                "Cfg",
                (),
                {
                    "enabled": True,
                    "whitelist": ("BTC-USDT-SWAP",),
                    "feature_bar_seconds": 1,
                    "state_sync_seconds": 30,
                    "book_channel": "books5",
                },
            )()
        )

        self.assertTrue(defaults["enabled"])
        self.assertEqual(defaults["whitelist"], ["BTC-USDT-SWAP"])
