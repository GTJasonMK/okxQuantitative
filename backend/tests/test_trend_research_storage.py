import tempfile
import unittest


class TrendResearchStorageTest(unittest.TestCase):
    def test_save_and_load_feature_bar_label_factor_score_and_inference(self):
        from app.core.data_storage import DataStorage
        from app.core.trend_research.models import (
            FactorScore,
            FeatureBar1s,
            SwingLabel,
            TrendInferenceSnapshot,
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            storage = DataStorage(f"{tmp_dir}/market.db")

            saved = storage.save_feature_bars_1s([
                FeatureBar1s(
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
                    bid_price=59999.0,
                    ask_price=60001.0,
                    bid_size=12.0,
                    ask_size=8.0,
                    buy_notional=7000.0,
                    sell_notional=3000.0,
                    buy_count=3,
                    sell_count=1,
                    max_trade_notional=4500.0,
                    buy_burst_count=2,
                    sell_burst_count=1,
                    buy_burst_notional=5000.0,
                    sell_burst_notional=3000.0,
                    open_price=59998.0,
                    high_price=60003.0,
                    low_price=59995.0,
                    close_price=60001.0,
                    microprice=60000.8,
                    basis_bps=1.0000833402783566,
                    open_interest=1200.0,
                    funding_rate=0.0001,
                    funding_delta=0.00005,
                    premium=5.0,
                ),
            ])
            self.assertEqual(saved, 1)

            labels_saved = storage.replace_swing_labels(
                "BTC-USDT-SWAP",
                [
                    SwingLabel(
                        inst_id="BTC-USDT-SWAP",
                        second_bucket=1712365200,
                        trend_state="uptrend",
                        swing_top_confirmed=False,
                        swing_bottom_confirmed=True,
                        time_to_top=18,
                        time_to_bottom=0,
                    ),
                ],
            )
            self.assertEqual(labels_saved, 1)

            factor_scores_saved = storage.replace_factor_scores(
                "BTC-USDT-SWAP",
                [
                    FactorScore(
                        inst_id="BTC-USDT-SWAP",
                        factor_name="signed_trade_notional_z",
                        spearman_ic=0.42,
                        stability_score=0.42,
                        redundancy_cluster="flow",
                        category="trade_flow",
                        tier=0,
                        available=True,
                        unavailable_reason="",
                    ),
                ],
            )
            self.assertEqual(factor_scores_saved, 1)

            inference_saved = storage.save_inference_snapshots([
                TrendInferenceSnapshot(
                    inst_id="BTC-USDT-SWAP",
                    second_bucket=1712365200,
                    trend_score=18.0,
                    trend_state="range",
                    top_probability=0.41,
                    bottom_probability=0.59,
                    confidence=0.44,
                    data_quality="partial",
                ),
                TrendInferenceSnapshot(
                    inst_id="BTC-USDT-SWAP",
                    second_bucket=1712365201,
                    trend_score=62.5,
                    trend_state="uptrend_confirmed",
                    current_price=60001.0,
                    predicted_top_eta_seconds=900,
                    predicted_bottom_eta_seconds=2280,
                    predicted_top_price=61212.080402,
                    predicted_bottom_price=59402.990025,
                    predicted_top_return=0.02,
                    predicted_bottom_return=-0.01,
                    top_time_distribution=(0.0, 0.6),
                    bottom_time_distribution=(0.0, 0.7),
                    top_probability=0.12,
                    bottom_probability=0.71,
                    confidence=0.88,
                    data_quality="ok",
                ),
                TrendInferenceSnapshot(
                    inst_id="ETH-USDT-SWAP",
                    second_bucket=1712365200,
                    trend_score=-28.0,
                    trend_state="downtrend_confirmed",
                    top_probability=0.73,
                    bottom_probability=0.19,
                    confidence=0.66,
                    data_quality="ok",
                ),
            ])
            self.assertEqual(inference_saved, 3)

            bars = storage.list_feature_bars_1s("BTC-USDT-SWAP", limit=5)
            labels = storage.list_swing_labels("BTC-USDT-SWAP", limit=5)
            factor_scores = storage.list_factor_scores("BTC-USDT-SWAP", limit=5)
            inference_history = storage.list_inference_snapshots(limit=2)
            latest_inference = storage.list_latest_inference_snapshots(limit=5)
            btc_latest = storage.list_latest_inference_snapshots(
                limit=5,
                inst_ids=["BTC-USDT-SWAP"],
            )

            self.assertEqual(len(bars), 1)
            self.assertEqual(bars[0].trade_count, 4)
            self.assertEqual(bars[0].bid_size, 12.0)
            self.assertEqual(bars[0].buy_burst_count, 2)
            self.assertEqual(bars[0].open_interest, 1200.0)
            self.assertEqual(len(labels), 1)
            self.assertEqual(labels[0].trend_state, "uptrend")
            self.assertEqual(len(factor_scores), 1)
            self.assertEqual(factor_scores[0].factor_name, "signed_trade_notional_z")
            self.assertEqual(factor_scores[0].category, "trade_flow")
            self.assertTrue(factor_scores[0].available)
            self.assertEqual(len(inference_history), 2)
            self.assertEqual(inference_history[0].second_bucket, 1712365201)
            self.assertEqual(len(latest_inference), 2)
            self.assertEqual(latest_inference[0].inst_id, "BTC-USDT-SWAP")
            self.assertEqual(latest_inference[0].trend_state, "uptrend_confirmed")
            self.assertEqual(latest_inference[0].predicted_top_eta_seconds, 900)
            self.assertAlmostEqual(latest_inference[0].predicted_top_price, 61212.080402)
            self.assertEqual(latest_inference[0].top_time_distribution, (0.0, 0.6))
            self.assertEqual([row.inst_id for row in btc_latest], ["BTC-USDT-SWAP"])
            if hasattr(storage, "_local") and hasattr(storage._local, "connection"):
                storage._local.connection.close()
                storage._local.connection = None
