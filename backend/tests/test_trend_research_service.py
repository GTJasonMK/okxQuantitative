import asyncio
import contextlib
import json
import time
import types
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch


class FakeFetcher:
    def get_mark_price(self, inst_id):
        return {"inst_id": inst_id, "mark_price": 60002.0, "ts": 1712365200200}

    def get_index_price(self, inst_id):
        return {"inst_id": inst_id, "index_price": 59997.0, "ts": 1712365200200}

    def get_open_interest(self, inst_id):
        return {"inst_id": inst_id, "open_interest": 1200.0, "ts": 1712365200200}

    def get_funding_rate(self, inst_id):
        return {
            "inst_id": inst_id,
            "funding_rate": 0.0001,
            "premium": 5.0,
            "ts": 1712365200200,
        }


class BrokenFundingFetcher(FakeFetcher):
    def get_funding_rate(self, inst_id):
        raise RuntimeError(f"{inst_id} funding unavailable")


class SlowFetcher(FakeFetcher):
    DELAY_SECONDS = 0.05

    def _pause(self):
        time.sleep(self.DELAY_SECONDS)

    def get_mark_price(self, inst_id):
        self._pause()
        return super().get_mark_price(inst_id)

    def get_index_price(self, inst_id):
        self._pause()
        return super().get_index_price(inst_id)

    def get_open_interest(self, inst_id):
        self._pause()
        return super().get_open_interest(inst_id)

    def get_funding_rate(self, inst_id):
        self._pause()
        return super().get_funding_rate(inst_id)


class FakeWSManager:
    def __init__(self):
        self.trade_callbacks = []
        self.book_callbacks = []
        self.trade_subscriptions = []
        self.book_subscriptions = []
        self.refreshed_trades = []
        self.refreshed_books = []
        self.unsubscribed_trades = []
        self.unsubscribed_books = []

    def add_trade_callback(self, callback):
        self.trade_callbacks.append(callback)

    def remove_trade_callback(self, callback):
        if callback in self.trade_callbacks:
            self.trade_callbacks.remove(callback)

    def add_book_callback(self, callback):
        self.book_callbacks.append(callback)

    def remove_book_callback(self, callback):
        if callback in self.book_callbacks:
            self.book_callbacks.remove(callback)

    async def subscribe_trades(self, inst_ids):
        self.trade_subscriptions.extend(inst_ids)

    async def subscribe_books(self, inst_ids, channel="books5"):
        self.book_subscriptions.extend((inst_id, channel) for inst_id in inst_ids)

    async def refresh_trade_subscriptions(self, inst_ids):
        self.refreshed_trades.extend(inst_ids)

    async def refresh_book_subscriptions(self, inst_ids, channel="books5"):
        self.refreshed_books.extend((inst_id, channel) for inst_id in inst_ids)

    async def unsubscribe_trades(self, inst_ids):
        self.unsubscribed_trades.extend(inst_ids)

    async def unsubscribe_books(self, inst_ids, channel="books5"):
        self.unsubscribed_books.extend((inst_id, channel) for inst_id in inst_ids)


class FakeStorage:
    def __init__(self):
        self.saved_bars = []
        self.saved_labels = {}
        self.saved_factor_scores = {}
        self.saved_inference_rows = []

    def save_feature_bars_1s(self, bars):
        self.saved_bars.extend(bars)
        return len(bars)

    def list_feature_bars_1s(self, inst_id, limit=100):
        normalized_limit = max(int(limit or 100), 1)
        matched = [bar for bar in self.saved_bars if bar.inst_id == inst_id]
        ordered = sorted(matched, key=lambda bar: bar.second_bucket, reverse=True)
        return ordered[:normalized_limit]

    def replace_swing_labels(self, inst_id, labels):
        self.saved_labels[inst_id] = list(labels)
        return len(labels)

    def list_swing_labels(self, inst_id, limit=100):
        normalized_limit = max(int(limit or 100), 1)
        return list(self.saved_labels.get(inst_id, []))[:normalized_limit]

    def replace_factor_scores(self, inst_id, scores):
        self.saved_factor_scores[inst_id] = list(scores)
        return len(scores)

    def list_factor_scores(self, inst_id, limit=20):
        normalized_limit = max(int(limit or 20), 1)
        return list(self.saved_factor_scores.get(inst_id, []))[:normalized_limit]

    def save_inference_snapshots(self, rows):
        self.saved_inference_rows.extend(rows)
        return len(rows)

    def list_inference_snapshots(self, limit=100, inst_ids=None):
        normalized_limit = max(int(limit or 100), 1)
        rows = list(self.saved_inference_rows)
        if inst_ids:
            inst_id_set = set(inst_ids)
            rows = [row for row in rows if row.inst_id in inst_id_set]
        ordered = sorted(rows, key=lambda row: (row.second_bucket, row.inst_id), reverse=True)
        return ordered[:normalized_limit]

    def list_latest_inference_snapshots(self, limit=100, inst_ids=None):
        normalized_limit = max(int(limit or 100), 1)
        latest_by_inst = {}
        for row in self.saved_inference_rows:
            if inst_ids and row.inst_id not in inst_ids:
                continue
            previous = latest_by_inst.get(row.inst_id)
            if previous is None or row.second_bucket >= previous.second_bucket:
                latest_by_inst[row.inst_id] = row
        ordered = sorted(
            latest_by_inst.values(),
            key=lambda row: (-row.second_bucket, row.inst_id),
        )
        return ordered[:normalized_limit]


class CountingStorage(FakeStorage):
    def __init__(self):
        super().__init__()
        self.list_feature_bar_calls = 0
        self.list_latest_inference_calls = 0

    def list_feature_bars_1s(self, inst_id, limit=100):
        self.list_feature_bar_calls += 1
        return super().list_feature_bars_1s(inst_id, limit=limit)

    def list_latest_inference_snapshots(self, limit=100, inst_ids=None):
        self.list_latest_inference_calls += 1
        return super().list_latest_inference_snapshots(limit=limit, inst_ids=inst_ids)


class TrendResearchServiceTest(unittest.IsolatedAsyncioTestCase):
    def _model_bundle(self):
        from app.core.trend_research.direct_models import (
            DirectExtremaMetrics,
            DirectExtremaModelBundle,
            DirectExtremaModelConfig,
        )

        return DirectExtremaModelBundle(
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

    def _prediction(self):
        return SimpleNamespace(
            top_time_bucket=14,
            bottom_time_bucket=37,
            top_return=0.02,
            bottom_return=-0.01,
            top_distribution=tuple(0.0 for _ in range(14)) + (0.6,) + tuple(0.0 for _ in range(45)),
            bottom_distribution=tuple(0.0 for _ in range(37)) + (0.7,) + tuple(0.0 for _ in range(22)),
        )

    async def test_start_retrain_model_rejects_concurrent_runs(self):
        from app.core.trend_research.service import TrendResearchService

        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )
        service._training_task = asyncio.create_task(
            asyncio.sleep(60),
            name="trend_research_model_train",
        )
        try:
            with self.assertRaisesRegex(RuntimeError, "training already running"):
                await service.start_retrain_model(lookback=3600)
        finally:
            service._training_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await service._training_task

    async def test_start_retrain_model_applies_worker_progress_events(self):
        from app.core.trend_research.service import TrendResearchService

        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
            model_bundle=self._model_bundle(),
        )

        def fake_runtime(storage, whitelist, *, lookback, progress_callback):
            progress_callback(
                {
                    "kind": "stage",
                    "stage": "collect_bars",
                    "status": "running",
                    "message": "collecting feature bars",
                }
            )
            progress_callback(
                {
                    "kind": "stage",
                    "stage": "collect_bars",
                    "status": "completed",
                    "message": "bars ready",
                    "stats": {"eligible_inst_count": 1, "whitelist_count": 1},
                }
            )
            progress_callback(
                {
                    "kind": "stage",
                    "stage": "train_epochs",
                    "status": "running",
                    "message": "Epoch 1 / 2",
                }
            )
            progress_callback(
                {
                    "kind": "epoch",
                    "epoch": 1,
                    "total_epochs": 2,
                    "train_loss": 0.84,
                    "validation_loss": 0.91,
                }
            )
            progress_callback(
                {
                    "kind": "epoch",
                    "epoch": 2,
                    "total_epochs": 2,
                    "train_loss": 0.77,
                    "validation_loss": 0.86,
                }
            )
            progress_callback(
                {
                    "kind": "stage",
                    "stage": "train_epochs",
                    "status": "completed",
                    "message": "Epoch 2 / 2",
                    "stats": {"epoch_count": 2},
                }
            )
            progress_callback(
                {
                    "kind": "stage",
                    "stage": "evaluate_validation",
                    "status": "completed",
                    "message": "validation metrics ready",
                    "stats": {"joint_hit_rate": 0.42},
                }
            )
            progress_callback(
                {
                    "kind": "stage",
                    "stage": "save_bundle",
                    "status": "completed",
                    "message": "bundle saved",
                    "stats": {"selected_feature_count": 2},
                }
            )
            return self._model_bundle()

        with patch(
            "app.core.trend_research.service.retrain_model_from_storage",
            side_effect=fake_runtime,
        ):
            snapshot = await service.start_retrain_model(lookback=3600)
            await asyncio.wait_for(service._training_task, timeout=1)
            await asyncio.sleep(0)

        training_run = service.get_training_run()
        self.assertEqual(snapshot["status"], "queued")
        self.assertEqual(training_run["status"], "completed")
        self.assertEqual(training_run["epoch_history"][1]["epoch"], 2)
        self.assertEqual(training_run["stages"][1]["stats"]["eligible_inst_count"], 1)
        self.assertEqual(service.get_model_status()["metrics"]["joint_hit_rate"], 0.42)

    async def test_start_subscribes_whitelist_and_syncs_state(self):
        from app.core.trend_research.service import TrendResearchService

        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )

        await service.start()
        await service.sync_contract_state_once()

        self.assertEqual(service.ws_manager.trade_subscriptions, ["BTC-USDT-SWAP"])
        self.assertEqual(service.ws_manager.book_subscriptions, [("BTC-USDT-SWAP", "books5")])
        self.assertIn("BTC-USDT-SWAP", service.builders)
        self.assertEqual(len(service.list_inference(limit=5)), 1)
        self.assertEqual(service.list_inference(limit=5)[0].data_quality, "partial")

        await service.stop()

    async def test_start_keeps_runtime_alive_when_initial_state_sync_fails(self):
        from app.core.trend_research.service import TrendResearchService

        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )

        async def parked_loop():
            await asyncio.Event().wait()

        with patch.object(
            service,
            "sync_contract_state_once",
            new=AsyncMock(side_effect=RuntimeError("bootstrap sync failed")),
        ):
            with patch.object(service, "_flush_once_async", new=AsyncMock(return_value=[])):
                with patch.object(service, "_state_sync_loop", new=parked_loop):
                    with patch.object(service, "_flush_loop", new=parked_loop):
                        with patch.object(service, "_watchdog_loop", new=parked_loop):
                            await service.start()

        self.assertTrue(service._running)
        self.assertIn("bootstrap sync failed", service.get_runtime_error())
        self.assertEqual(service.ws_manager.trade_subscriptions, ["BTC-USDT-SWAP"])
        self.assertEqual(service.ws_manager.book_subscriptions, [("BTC-USDT-SWAP", "books5")])

        await service.stop()

    async def test_sync_contract_state_once_offloads_contract_fetch_to_thread(self):
        from app.core.trend_research.service import TrendResearchService

        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=SlowFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )

        async def fake_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        with patch("app.core.trend_research.service.asyncio.to_thread", new=AsyncMock(side_effect=fake_to_thread)) as mocked:
            await service.sync_contract_state_once()

        self.assertEqual(mocked.await_count, 1)
        self.assertTrue(service.builders["BTC-USDT-SWAP"].build_runtime_snapshot().has_contract_state)

    async def test_flush_once_persists_bar_and_updates_inference_rows(self):
        from app.core.trend_research.models import BookTopEvent, TradeTickEvent
        from app.core.trend_research.service import TrendResearchService

        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )

        await service.sync_contract_state_once()
        service.on_book(
            "BTC-USDT-SWAP",
            BookTopEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365200.05,
                ts_local=1712365200.05,
                bid_price=59999.0,
                ask_price=60001.0,
                bid_size=12.0,
                ask_size=8.0,
            ),
        )
        service.on_trade(
            "BTC-USDT-SWAP",
            TradeTickEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365200.10,
                ts_local=1712365200.10,
                price=60001.0,
                size=0.4,
                side="buy",
            ),
        )

        rows = service.flush_once(second_bucket=1712365200)

        self.assertEqual(len(service.storage.saved_bars), 1)
        self.assertEqual(len(service.storage.saved_inference_rows), 1)
        self.assertEqual(service.storage.saved_bars[0].second_bucket, 1712365200)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].inst_id, "BTC-USDT-SWAP")
        self.assertEqual(service.list_inference(limit=5)[0].trend_state, "model_not_ready")

    async def test_build_diagnostics_snapshot_tracks_runtime_updates(self):
        from app.core.trend_research.models import BookTopEvent, TradeTickEvent
        from app.core.trend_research.service import TrendResearchService

        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )

        await service.sync_contract_state_once()
        service.on_book(
            "BTC-USDT-SWAP",
            BookTopEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365200.05,
                ts_local=1712365200.05,
                bid_price=59999.0,
                ask_price=60001.0,
                bid_size=12.0,
                ask_size=8.0,
            ),
        )
        service.on_trade(
            "BTC-USDT-SWAP",
            TradeTickEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365200.10,
                ts_local=1712365200.10,
                price=60001.0,
                size=0.4,
                side="buy",
            ),
        )
        service.flush_once(second_bucket=1712365200)

        snapshot = service.build_diagnostics_snapshot(
            inst_id="BTC-USDT-SWAP",
            timeline_limit=20,
        )

        self.assertEqual(snapshot["selected_inst_id"], "BTC-USDT-SWAP")
        self.assertIn(
            snapshot["instrument_health"]["pipeline_stage"],
            {"feature_ready", "inference_ready"},
        )
        self.assertEqual(snapshot["details"]["subscription_state"], "subscribed")
        self.assertGreaterEqual(len(snapshot["timeline"]), 3)

    async def test_flush_loop_offloads_persistence_to_thread(self):
        from app.core.trend_research.service import TrendResearchService

        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )

        async def fake_to_thread(func, *args, **kwargs):
            return func(*args, **kwargs)

        with patch("app.core.trend_research.service.asyncio.to_thread", new=AsyncMock(side_effect=fake_to_thread)) as mocked_to_thread:
            with patch("app.core.trend_research.service.asyncio.sleep", new=AsyncMock(side_effect=[None, asyncio.CancelledError()])):
                with patch.object(service, "_build_feature_bars", return_value=["bar"]):
                    with patch.object(service, "_build_inference_rows", return_value=["row"]):
                        with patch.object(service, "_persist_flush_rows", return_value=None) as persist_rows:
                            with self.assertRaises(asyncio.CancelledError):
                                await service._flush_loop()

        self.assertEqual(mocked_to_thread.await_count, 1)
        persist_rows.assert_called_once_with(["bar"], ["row"])

    async def test_state_sync_failure_is_exposed_and_cleared_after_recovery(self):
        from app.core.trend_research.service import TrendResearchService

        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=BrokenFundingFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )

        with self.assertRaisesRegex(RuntimeError, "funding unavailable"):
            await service.sync_contract_state_once()
        self.assertIn("funding unavailable", service.get_runtime_error())

        service.fetcher = FakeFetcher()
        await service.sync_contract_state_once()

        self.assertEqual(service.get_runtime_error(), "")

    async def test_flush_loop_survives_transient_failure(self):
        from app.core.trend_research.service import TrendResearchService

        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )

        with patch(
            "app.core.trend_research.service.asyncio.sleep",
            new=AsyncMock(side_effect=[None, None, asyncio.CancelledError()]),
        ):
            with patch.object(
                service,
                "_flush_once_async",
                new=AsyncMock(side_effect=[RuntimeError("flush unavailable"), []]),
            ) as mocked_flush:
                with self.assertRaises(asyncio.CancelledError):
                    await service._flush_loop()

        self.assertEqual(mocked_flush.await_count, 2)
        self.assertEqual(service.get_runtime_error(), "")

    async def test_watchdog_replays_subscriptions_when_inputs_go_stale(self):
        from app.core.trend_research.service import TrendResearchService

        ws_manager = FakeWSManager()
        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=FakeFetcher(),
            ws_manager=ws_manager,
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )

        service._running = True
        service._last_trade_event_ts = time.time() - 120
        service._last_book_event_ts = time.time() - 120

        await service._watchdog_once()

        self.assertEqual(ws_manager.refreshed_trades, ["BTC-USDT-SWAP"])
        self.assertEqual(ws_manager.refreshed_books, [("BTC-USDT-SWAP", "books5")])

    async def test_watchdog_emits_runtime_error_and_recovery_events(self):
        from app.core.trend_research.models import BookTopEvent, TradeTickEvent
        from app.core.trend_research.service import TrendResearchService

        ws_manager = FakeWSManager()
        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=FakeFetcher(),
            ws_manager=ws_manager,
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )
        diagnostics_events = []
        service.add_diagnostics_listener(diagnostics_events.append)
        service._running = True
        stale_ts = time.time() - 120
        service._last_trade_event_ts = stale_ts
        service._last_book_event_ts = stale_ts

        await service._watchdog_once()

        self.assertEqual(diagnostics_events[-1]["event_type"], "runtime_error_changed")
        self.assertIn("输入流停滞", diagnostics_events[-1]["payload"]["current_error"])

        fresh_ts = time.time()
        service.on_trade(
            "BTC-USDT-SWAP",
            TradeTickEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=fresh_ts,
                ts_local=fresh_ts,
                price=60001.0,
                size=0.4,
                side="buy",
            ),
        )
        service.on_book(
            "BTC-USDT-SWAP",
            BookTopEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=fresh_ts,
                ts_local=fresh_ts,
                bid_price=59999.0,
                ask_price=60001.0,
                bid_size=12.0,
                ask_size=8.0,
            ),
        )

        self.assertEqual(diagnostics_events[-1]["event_type"], "runtime_error_changed")
        self.assertEqual(diagnostics_events[-1]["payload"]["current_error"], "")

    async def test_list_inference_recovers_latest_snapshots_from_storage(self):
        from app.core.trend_research.models import TrendInferenceSnapshot
        from app.core.trend_research.service import TrendResearchService

        storage = FakeStorage()
        storage.save_inference_snapshots([
            TrendInferenceSnapshot(
                inst_id="BTC-USDT-SWAP",
                second_bucket=1712365200,
                trend_score=62.5,
                trend_state="uptrend_confirmed",
                top_probability=0.12,
                bottom_probability=0.71,
                confidence=0.88,
                data_quality="ok",
            ),
            TrendInferenceSnapshot(
                inst_id="DOGE-USDT-SWAP",
                second_bucket=1712365201,
                trend_score=-21.0,
                trend_state="downtrend_confirmed",
                top_probability=0.66,
                bottom_probability=0.24,
                confidence=0.64,
                data_quality="ok",
            ),
        ])

        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=storage,
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )

        rows = service.list_inference(limit=5)

        self.assertEqual([row.inst_id for row in rows], ["BTC-USDT-SWAP"])
        self.assertEqual(rows[0].trend_state, "uptrend_confirmed")

    async def test_start_creates_background_tasks_and_stop_cleans_up(self):
        from app.core.trend_research.service import TrendResearchService

        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=5,
            book_channel="books5",
        )

        await service.start()
        flush_task = service._flush_task
        state_task = service._state_task

        self.assertIsNotNone(flush_task)
        self.assertIsNotNone(state_task)
        self.assertFalse(flush_task.done())
        self.assertFalse(state_task.done())

        await service.stop()

        self.assertEqual(service.ws_manager.trade_callbacks, [])
        self.assertEqual(service.ws_manager.book_callbacks, [])
        self.assertTrue(flush_task.done())
        self.assertTrue(state_task.done())

    async def test_apply_settings_replaces_subscriptions_and_snapshots(self):
        from app.core.trend_research.service import TrendResearchService

        ws_manager = FakeWSManager()
        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=FakeFetcher(),
            ws_manager=ws_manager,
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )

        await service.start()
        service.replace_inference_snapshots([
            {"inst_id": "BTC-USDT-SWAP", "second_bucket": 1, "trend_state": "range"}
        ])

        applied = await service.apply_settings(
            {
                "enabled": True,
                "whitelist": ["ETH-USDT-SWAP"],
                "feature_bar_seconds": 2,
                "state_sync_seconds": 30,
                "book_channel": "books5",
            },
            persist=False,
        )

        self.assertEqual(applied["whitelist"], ["ETH-USDT-SWAP"])
        self.assertEqual(ws_manager.unsubscribed_trades, ["BTC-USDT-SWAP"])
        self.assertEqual(ws_manager.unsubscribed_books, [("BTC-USDT-SWAP", "books5")])
        self.assertEqual(ws_manager.trade_subscriptions[-1], "ETH-USDT-SWAP")
        self.assertEqual(list(service.builders.keys()), ["ETH-USDT-SWAP"])
        self.assertEqual(service.list_inference(limit=5)[0].inst_id, "ETH-USDT-SWAP")

        await service.stop()

    async def test_process_snapshot_reports_runtime_feature_and_inference_stage(self):
        from app.core.trend_research.models import BookTopEvent, TradeTickEvent
        from app.core.trend_research.process_view import build_trend_process_snapshot
        from app.core.trend_research.service import TrendResearchService

        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )

        await service.sync_contract_state_once()
        service.on_book(
            "BTC-USDT-SWAP",
            BookTopEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365200.05,
                ts_local=1712365200.05,
                bid_price=59999.0,
                ask_price=60001.0,
                bid_size=12.0,
                ask_size=8.0,
            ),
        )
        service.on_trade(
            "BTC-USDT-SWAP",
            TradeTickEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365200.10,
                ts_local=1712365200.10,
                price=60001.0,
                size=0.4,
                side="buy",
            ),
        )
        service.flush_once(second_bucket=1712365200)

        payload = build_trend_process_snapshot(service, bar_limit=5)

        self.assertEqual(payload["summary"]["trade_ready_count"], 1)
        self.assertEqual(payload["summary"]["feature_ready_count"], 1)
        self.assertEqual(payload["summary"]["inference_ready_count"], 1)
        self.assertEqual(payload["instruments"][0]["pipeline_state"], "inference_ready")
        self.assertTrue(payload["instruments"][0]["stages"]["state"]["ready"])
        self.assertEqual(payload["instruments"][0]["latest_feature_bar"]["trade_count"], 1)
        self.assertEqual(payload["instruments"][0]["latest_inference"]["trend_state"], "model_not_ready")

    async def test_flush_once_notifies_realtime_listeners_with_snapshot_payload(self):
        from app.core.trend_research.models import BookTopEvent, TradeTickEvent
        from app.core.trend_research.service import TrendResearchService

        payloads = []
        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )
        service.add_listener(payloads.append)

        await service.sync_contract_state_once()
        service.on_book(
            "BTC-USDT-SWAP",
            BookTopEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365200.05,
                ts_local=1712365200.05,
                bid_price=59999.0,
                ask_price=60001.0,
                bid_size=12.0,
                ask_size=8.0,
            ),
        )
        service.on_trade(
            "BTC-USDT-SWAP",
            TradeTickEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365200.10,
                ts_local=1712365200.10,
                price=60001.0,
                size=0.4,
                side="buy",
            ),
        )

        service.flush_once(second_bucket=1712365200)

        self.assertGreaterEqual(len(payloads), 1)
        self.assertEqual(payloads[-1]["status"], "ready")
        self.assertEqual(payloads[-1]["rows"][0]["inst_id"], "BTC-USDT-SWAP")
        self.assertEqual(payloads[-1]["instruments"][0]["pipeline_state"], "inference_ready")

    async def test_runtime_stage_transitions_notify_realtime_listeners_before_flush(self):
        from app.core.trend_research.models import BookTopEvent, TradeTickEvent
        from app.core.trend_research.service import TrendResearchService

        payloads = []
        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )
        service.add_listener(payloads.append)

        await service.sync_contract_state_once()
        service.on_book(
            "BTC-USDT-SWAP",
            BookTopEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365200.05,
                ts_local=1712365200.05,
                bid_price=59999.0,
                ask_price=60001.0,
                bid_size=12.0,
                ask_size=8.0,
            ),
        )
        service.on_trade(
            "BTC-USDT-SWAP",
            TradeTickEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365200.10,
                ts_local=1712365200.10,
                price=60001.0,
                size=0.4,
                side="buy",
            ),
        )

        self.assertEqual(len(payloads), 3)
        self.assertTrue(payloads[0]["instruments"][0]["stages"]["state"]["ready"])
        self.assertTrue(payloads[1]["instruments"][0]["stages"]["book"]["ready"])
        self.assertTrue(payloads[2]["instruments"][0]["stages"]["trade"]["ready"])
        self.assertEqual(payloads[2]["instruments"][0]["pipeline_state"], "collecting")

        service.on_trade(
            "BTC-USDT-SWAP",
            TradeTickEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365200.20,
                ts_local=1712365200.20,
                price=60002.0,
                size=0.1,
                side="sell",
            ),
        )

        self.assertEqual(len(payloads), 4)
        self.assertEqual(payloads[-1]["instruments"][0]["runtime"]["pending_trade_count"], 2)

    async def test_flush_once_uses_model_bundle_when_available(self):
        from app.core.trend_research.models import BookTopEvent, TradeTickEvent
        from app.core.trend_research.service import TrendResearchService

        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
            model_bundle=self._model_bundle(),
        )

        await service.sync_contract_state_once()
        service.on_book(
            "BTC-USDT-SWAP",
            BookTopEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365200.05,
                ts_local=1712365200.05,
                bid_price=59999.0,
                ask_price=60001.0,
                bid_size=12.0,
                ask_size=8.0,
            ),
        )
        service.on_trade(
            "BTC-USDT-SWAP",
            TradeTickEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365200.10,
                ts_local=1712365200.10,
                price=60001.0,
                size=0.4,
                side="buy",
            ),
        )

        with patch(
            "app.core.trend_research.inference.build_online_sequence_window",
            return_value=SimpleNamespace(
                inst_id="BTC-USDT-SWAP",
                anchor_minute_bucket=1712365200 // 60,
                feature_names=("queue_imbalance", "basis_bps"),
                feature_rows=((0.1, 1.0),) * 120,
                current_price=60001.0,
            ),
        ), patch(
            "app.core.trend_research.inference.run_direct_model",
            return_value=self._prediction(),
        ):
            rows = service.flush_once(second_bucket=1712365200)

        self.assertEqual(rows[0].trend_state, "uptrend_confirmed")
        self.assertEqual(rows[0].predicted_top_eta_seconds, 900)
        self.assertEqual(rows[0].predicted_bottom_eta_seconds, 2280)
        self.assertGreater(rows[0].predicted_top_price, rows[0].current_price)

    async def test_flush_once_uses_recent_bar_cache_instead_of_storage_reads_for_model_scoring(self):
        from app.core.trend_research.models import BookTopEvent, TradeTickEvent
        from app.core.trend_research.service import TrendResearchService

        storage = CountingStorage()
        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=storage,
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
            model_bundle=self._model_bundle(),
        )
        storage.list_feature_bar_calls = 0

        await service.sync_contract_state_once()
        service.on_book(
            "BTC-USDT-SWAP",
            BookTopEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365200.05,
                ts_local=1712365200.05,
                bid_price=59999.0,
                ask_price=60001.0,
                bid_size=12.0,
                ask_size=8.0,
            ),
        )
        service.on_trade(
            "BTC-USDT-SWAP",
            TradeTickEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365200.10,
                ts_local=1712365200.10,
                price=60001.0,
                size=0.4,
                side="buy",
            ),
        )

        with patch(
            "app.core.trend_research.inference.build_online_sequence_window",
            return_value=SimpleNamespace(
                inst_id="BTC-USDT-SWAP",
                anchor_minute_bucket=1712365200 // 60,
                feature_names=("queue_imbalance", "basis_bps"),
                feature_rows=((0.1, 1.0),) * 120,
                current_price=60001.0,
            ),
        ), patch(
            "app.core.trend_research.inference.run_direct_model",
            return_value=self._prediction(),
        ):
            service.flush_once(second_bucket=1712365200)
        service.on_trade(
            "BTC-USDT-SWAP",
            TradeTickEvent(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365201.10,
                ts_local=1712365201.10,
                price=60002.0,
                size=0.5,
                side="buy",
            ),
        )
        with patch(
            "app.core.trend_research.inference.build_online_sequence_window",
            return_value=SimpleNamespace(
                inst_id="BTC-USDT-SWAP",
                anchor_minute_bucket=1712365201 // 60,
                feature_names=("queue_imbalance", "basis_bps"),
                feature_rows=((0.2, 1.1),) * 120,
                current_price=60002.0,
            ),
        ), patch(
            "app.core.trend_research.inference.run_direct_model",
            return_value=self._prediction(),
        ):
            service.flush_once(second_bucket=1712365201)

        self.assertEqual(storage.list_feature_bar_calls, 0)

    async def test_start_bootstraps_recent_bar_cache_from_storage_for_model_scoring(self):
        from app.core.trend_research.models import FeatureBar1s
        from app.core.trend_research.service import TrendResearchService

        storage = CountingStorage()
        base_bucket = 1712365200
        storage.save_feature_bars_1s([
            FeatureBar1s(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=float(base_bucket + index),
                ts_local=float(base_bucket + index),
                second_bucket=base_bucket + index,
                mid_price=60000.0 + index,
                mark_price=60002.0 + index,
                index_price=59997.0 + index,
                spread_bps=1.0,
                signed_trade_notional=10_000.0 + index,
                trade_count=1,
                oi_delta=0.1,
                basis_zscore=0.2,
                data_quality="ok",
                close_price=60000.0 + index,
            )
            for index in range(120 * 60)
        ])

        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=storage,
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
            model_bundle=self._model_bundle(),
        )

        with patch.object(service, "sync_contract_state_once", new=AsyncMock(return_value=None)):
            with patch.object(service, "_flush_once_async", new=AsyncMock(return_value=[])):
                await service.start()

        cached_rows = service._recent_bars_by_inst["BTC-USDT-SWAP"]
        self.assertEqual(len(cached_rows), 120 * 60)
        self.assertEqual(cached_rows[0].second_bucket, base_bucket)
        self.assertEqual(cached_rows[-1].second_bucket, base_bucket + (120 * 60) - 1)
        self.assertEqual(storage.list_feature_bar_calls, 1)

        await service.stop()

    async def test_process_snapshot_and_realtime_payload_expose_model_status(self):
        from app.core.trend_research.process_view import build_trend_process_snapshot
        from app.core.trend_research.realtime import build_trend_realtime_payload
        from app.core.trend_research.service import TrendResearchService

        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=FakeStorage(),
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
            model_bundle=self._model_bundle(),
        )

        process_payload = build_trend_process_snapshot(service, bar_limit=5)
        realtime_payload = build_trend_realtime_payload(service, bar_limit=5, rows_limit=5)

        self.assertTrue(process_payload["summary"]["model_ready"])
        self.assertEqual(process_payload["summary"]["selected_feature_count"], 2)
        self.assertTrue(realtime_payload["model_status"]["ready"])
        self.assertEqual(realtime_payload["model_status"]["architecture"], "tcn")
        self.assertEqual(realtime_payload["model_status"]["horizon_minutes"], 60)
        self.assertAlmostEqual(realtime_payload["model_status"]["metrics"]["joint_hit_rate"], 0.42)

    async def test_realtime_payload_uses_in_memory_snapshots_without_storage_reads(self):
        from app.core.trend_research.realtime import build_trend_realtime_payload
        from app.core.trend_research.models import FeatureBar1s, TrendInferenceSnapshot
        from app.core.trend_research.service import TrendResearchService

        storage = CountingStorage()
        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=storage,
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
            model_bundle=self._model_bundle(),
        )

        service._recent_bars_by_inst["BTC-USDT-SWAP"] = [
            FeatureBar1s(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365201.0,
                ts_local=1712365201.0,
                second_bucket=1712365201,
                mid_price=60000.0,
                mark_price=60002.0,
                index_price=59997.0,
                spread_bps=3.3,
                signed_trade_notional=24000.4,
                trade_count=1,
                oi_delta=5.0,
                basis_zscore=5.0,
                data_quality="ok",
            )
        ]
        row = TrendInferenceSnapshot(
            inst_id="BTC-USDT-SWAP",
            second_bucket=1712365201,
            trend_score=28.0,
            trend_state="uptrend_confirmed",
            confidence=0.76,
            data_quality="ok",
            current_price=60002.0,
            predicted_top_eta_seconds=900,
            predicted_bottom_eta_seconds=1800,
            predicted_top_price=60600.0,
            predicted_bottom_price=59400.0,
            predicted_top_return=0.01,
            predicted_bottom_return=-0.01,
            top_time_distribution=(0.1, 0.9),
            bottom_time_distribution=(0.8, 0.2),
            top_probability=0.9,
            bottom_probability=0.8,
        )
        service._latest_inference_by_inst = {"BTC-USDT-SWAP": row}
        service._inference_rows = [row]

        storage.list_feature_bar_calls = 0
        storage.list_latest_inference_calls = 0

        payload = build_trend_realtime_payload(service, bar_limit=5, rows_limit=5)

        self.assertEqual(payload["rows"][0]["inst_id"], "BTC-USDT-SWAP")
        self.assertEqual(storage.list_feature_bar_calls, 0)
        self.assertEqual(storage.list_latest_inference_calls, 0)

    async def test_realtime_tick_emit_does_not_query_storage(self):
        from app.core.trend_research.service import TrendResearchService

        storage = CountingStorage()
        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=storage,
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )
        payloads = []
        service.add_listener(payloads.append)

        service.on_trade(
            "BTC-USDT-SWAP",
            SimpleNamespace(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=1712365200.1,
                ts_local=1712365200.1,
                price=60001.0,
                size=0.4,
                side="buy",
            ),
        )

        self.assertEqual(len(payloads), 1)
        self.assertEqual(storage.list_feature_bar_calls, 0)
        self.assertEqual(storage.list_latest_inference_calls, 0)
        instrument = payloads[0]["instruments"][0]
        self.assertEqual(instrument["runtime"]["last_trade_price"], 60001.0)
        self.assertEqual(instrument["runtime"]["pending_trade_count"], 1)

    async def test_rebuild_factor_scores_persists_labels_and_ranked_scores(self):
        from app.core.trend_research.models import FeatureBar1s
        from app.core.trend_research.service import TrendResearchService

        storage = FakeStorage()
        storage.save_feature_bars_1s([
            FeatureBar1s(
                inst_id="BTC-USDT-SWAP",
                ts_exchange=float(1712365200 + idx),
                ts_local=float(1712365200 + idx),
                second_bucket=1712365200 + idx,
                mid_price=price,
                mark_price=price,
                index_price=price - 0.5,
                spread_bps=1.0 + idx,
                signed_trade_notional=flow,
                trade_count=1 + idx,
                oi_delta=(-1.0) ** idx * 0.2,
                basis_zscore=0.1 * idx,
                data_quality="ok",
            )
            for idx, (price, flow) in enumerate([
                (100.0, -500.0),
                (102.0, 600.0),
                (105.0, 1100.0),
                (103.0, -700.0),
                (99.0, -1200.0),
                (101.0, 900.0),
            ])
        ])

        service = TrendResearchService(
            whitelist=("BTC-USDT-SWAP",),
            storage=storage,
            fetcher=FakeFetcher(),
            ws_manager=FakeWSManager(),
            feature_bar_seconds=1,
            state_sync_seconds=30,
            book_channel="books5",
        )

        rows = service.rebuild_factor_scores("BTC-USDT-SWAP", lookback=20, limit=5)

        self.assertGreater(len(rows), 0)
        self.assertGreater(len(storage.list_swing_labels("BTC-USDT-SWAP", limit=20)), 0)
        self.assertGreater(len(storage.list_factor_scores("BTC-USDT-SWAP", limit=20)), 0)
        self.assertTrue(any(row.factor_name == "signed_trade_notional_z" for row in rows))

    def test_data_fetcher_and_cached_fetcher_expose_contract_state_methods(self):
        from app.core.cache import CachedDataFetcher
        from app.core.data_fetcher import DataFetcher

        seen_index_inst_ids = []
        fake_data_fetcher = object.__new__(DataFetcher)
        fake_data_fetcher._run_public_rest = lambda op_key, inst_id="", operation=None: operation()
        fake_data_fetcher.public_api = types.SimpleNamespace(
            get_mark_price=lambda **kwargs: {
                "code": "0",
                "data": [{"instId": kwargs["instId"], "markPx": "60002", "ts": "1712365200200"}],
            },
            get_open_interest=lambda **kwargs: {
                "code": "0",
                "data": [{"instId": kwargs["instId"], "oi": "1200", "ts": "1712365200200"}],
            },
            get_funding_rate=lambda **kwargs: {
                "code": "0",
                "data": [{"instId": kwargs["instId"], "fundingRate": "0.0001", "premium": "5", "ts": "1712365200200"}],
            },
        )
        fake_data_fetcher.market_api = types.SimpleNamespace(
            get_index_tickers=lambda **kwargs: seen_index_inst_ids.append(kwargs["instId"]) or {
                "code": "0",
                "data": [{"instId": kwargs["instId"], "idxPx": "59997", "ts": "1712365200200"}],
            }
        )

        mark = fake_data_fetcher.get_mark_price("BTC-USDT-SWAP")
        index = fake_data_fetcher.get_index_price("BTC-USDT-SWAP")
        oi = fake_data_fetcher.get_open_interest("BTC-USDT-SWAP")
        funding = fake_data_fetcher.get_funding_rate("BTC-USDT-SWAP")

        self.assertEqual(mark["mark_price"], 60002.0)
        self.assertEqual(index["index_price"], 59997.0)
        self.assertEqual(seen_index_inst_ids, ["BTC-USDT"])
        self.assertEqual(oi["open_interest"], 1200.0)
        self.assertEqual(funding["funding_rate"], 0.0001)

        cached_fetcher = object.__new__(CachedDataFetcher)
        cached_fetcher._fetcher = fake_data_fetcher
        cached_fetcher._requires_legacy_pre_acquire = lambda: False

        self.assertEqual(
            cached_fetcher.get_mark_price("BTC-USDT-SWAP")["mark_price"],
            60002.0,
        )

    def test_websocket_manager_dispatches_trade_and_book_callbacks(self):
        from app.core.websocket_manager import OKXWebSocketManager

        manager = OKXWebSocketManager(is_simulated=True, outbound=None)
        trade_events = []
        book_events = []

        manager.add_trade_callback(lambda inst_id, event: trade_events.append((inst_id, event)))
        manager.add_book_callback(lambda inst_id, event: book_events.append((inst_id, event)))

        manager._on_public_message(
            json.dumps(
                {
                    "arg": {"channel": "trades", "instId": "BTC-USDT-SWAP"},
                    "data": [
                        {
                            "instId": "BTC-USDT-SWAP",
                            "px": "60001",
                            "sz": "0.4",
                            "side": "buy",
                            "ts": "1712365200100",
                        }
                    ],
                }
            )
        )
        manager._on_public_message(
            json.dumps(
                {
                    "arg": {"channel": "books5", "instId": "BTC-USDT-SWAP"},
                    "data": [
                        {
                            "asks": [["60001", "8", "0", "0"], ["60002", "6", "0", "0"]],
                            "bids": [["59999", "12", "0", "0"], ["59998", "10", "0", "0"]],
                            "ts": "1712365200200",
                        }
                    ],
                }
            )
        )

        self.assertEqual(len(trade_events), 1)
        self.assertEqual(trade_events[0][0], "BTC-USDT-SWAP")
        self.assertEqual(trade_events[0][1].side, "buy")
        self.assertEqual(len(book_events), 1)
        self.assertEqual(book_events[0][1].bid_price, 59999.0)
        self.assertEqual(len(book_events[0][1].bid_levels), 2)
        self.assertEqual(book_events[0][1].ask_levels[1][0], 60002.0)

    def test_websocket_manager_health_check_does_not_touch_close_exc_on_open_connection(self):
        from app.core.websocket_manager import OKXWebSocketManager

        class OpenProtocol:
            @property
            def close_exc(self):
                raise AssertionError("connection isn't closed yet")

        class OpenWebSocket:
            protocol = OpenProtocol()
            state = "OPEN"
            closed = False

        class OpenClient:
            websocket = OpenWebSocket()

        manager = OKXWebSocketManager(is_simulated=True, outbound=None)

        self.assertTrue(manager._is_ws_client_healthy(OpenClient()))

    def test_outbound_rules_cover_trend_research_contract_state_operations(self):
        from app.core.okx_outbound.rules import OKXRateRuleRegistry

        registry = OKXRateRuleRegistry()

        self.assertEqual(registry.get("market.mark_price").op_key, "market.mark_price")
        self.assertEqual(registry.get("market.index_ticker").op_key, "market.index_ticker")
        self.assertEqual(registry.get("market.open_interest").op_key, "market.open_interest")
        self.assertEqual(registry.get("market.funding_rate").op_key, "market.funding_rate")
