from __future__ import annotations

import asyncio
import time
from threading import Lock
from typing import Callable

from .diagnostics_projector import TrendDiagnosticsProjector
from .feature_builder import FeatureBarBuilder
from .inference import TrendInferenceEngine
from .models import BookTopEvent, TradeTickEvent
from .realtime import build_trend_realtime_payload
from .research_runtime import DEFAULT_FACTOR_LIMIT, DEFAULT_FACTOR_LOOKBACK, build_factor_series_payload, rebuild_factor_scores_for_inst
from .runtime_service import TrendResearchRuntime
from .service_support import append_recent_bar, build_contract_state_snapshot, cancel_task, row_inst_id, settings_dict, sort_inference_rows
from .settings import normalize_trend_research_settings, save_trend_research_settings
from .training_constants import DEFAULT_EPOCHS
from .training_tracker import TrendTrainingTracker

DEFAULT_RECENT_BAR_LIMIT = 7200
DEFAULT_WATCHDOG_INTERVAL_SECONDS = 10.0
DEFAULT_INPUT_STALE_SECONDS = 30.0
SECONDS_PER_MINUTE = 60

class TrendResearchService:
    def __init__(
        self,
        *,
        whitelist,
        storage,
        fetcher,
        ws_manager,
        ws_manager_supplier=None,
        feature_bar_seconds: int,
        state_sync_seconds: int,
        book_channel: str,
        enabled: bool = True,
        defaults=None,
        cfg=None,
        model_bundle=None,
        recent_bar_limit: int = DEFAULT_RECENT_BAR_LIMIT,
    ):
        self.storage = storage
        self.fetcher = fetcher
        self.ws_manager = ws_manager
        self._ws_manager_supplier = ws_manager_supplier or (lambda: ws_manager)
        self._cfg = cfg
        initial_settings = settings_dict(
            enabled=enabled,
            whitelist=whitelist,
            feature_bar_seconds=feature_bar_seconds,
            state_sync_seconds=state_sync_seconds,
            book_channel=book_channel,
        )
        self._default_settings = dict(defaults or initial_settings)
        self._runtime_lock = asyncio.Lock()
        self._listeners_lock = Lock()
        self._engine = TrendInferenceEngine(model_bundle=model_bundle)
        self._flush_task = None
        self._state_task = None
        self._watchdog_task = None
        self._callbacks_registered = False
        self._running = False
        self._enabled = bool(enabled)
        self._runtime_error = ""
        self._flush_error = ""
        self._state_error = ""
        self._watchdog_error = ""
        self._listeners: list[Callable[[dict], None]] = []
        self._diagnostics_listeners: list[Callable[[dict], None]] = []
        self.recent_bar_limit = max(int(recent_bar_limit or DEFAULT_RECENT_BAR_LIMIT), 1)
        self._last_trade_event_ts: float | None = None
        self._last_book_event_ts: float | None = None
        self._diagnostics_runtime_error = ""
        self._apply_runtime_settings(initial_settings)
        self._training_tracker = TrendTrainingTracker()
        self._training_task = None
        self._training_loop = None

    def _settings_from(self, source):
        return settings_dict(
            enabled=source["enabled"],
            whitelist=source["whitelist"],
            feature_bar_seconds=source["feature_bar_seconds"],
            state_sync_seconds=source["state_sync_seconds"],
            book_channel=source["book_channel"],
        )

    def _apply_runtime_settings(self, settings) -> None:
        self._enabled = bool(settings["enabled"])
        self.whitelist = tuple(settings["whitelist"])
        self.feature_bar_seconds = int(settings["feature_bar_seconds"])
        self.state_sync_seconds = int(settings["state_sync_seconds"])
        self.book_channel = str(settings["book_channel"])
        self._flush_error = ""
        self._state_error = ""
        self._watchdog_error = ""
        self._last_trade_event_ts = None
        self._last_book_event_ts = None
        self._diagnostics_runtime_error = ""
        self.builders = {inst_id: FeatureBarBuilder(inst_id) for inst_id in self.whitelist}
        self._recent_bars_by_inst = {inst_id: [] for inst_id in self.whitelist}
        self._inference_rows = []
        self._latest_inference_by_inst = {}
        self._diagnostics = TrendDiagnosticsProjector()
        self._diagnostics.reset_instruments(self.whitelist)
        self._runtime = TrendResearchRuntime(
            builders=self.builders,
            projector=self._diagnostics,
        )
        self._hydrate_recent_bars_cache()
        self._refresh_runtime_error()

    def _recent_bar_cache_limit(self) -> int:
        model_status = self.get_model_status()
        if not bool(model_status.get("ready")):
            return 0
        input_minutes = max(int(model_status.get("input_minutes", 0) or 0), 1)
        return max(self.recent_bar_limit, input_minutes * SECONDS_PER_MINUTE)

    def _hydrate_recent_bars_cache(self) -> None:
        limit = self._recent_bar_cache_limit()
        if limit <= 0:
            return
        for inst_id in self.whitelist:
            rows = self.storage.list_feature_bars_1s(inst_id, limit=limit)
            self._recent_bars_by_inst[inst_id] = list(reversed(rows))

    def get_settings(self):
        return self._settings_from(
            {
                "enabled": self._enabled,
                "whitelist": self.whitelist,
                "feature_bar_seconds": self.feature_bar_seconds,
                "state_sync_seconds": self.state_sync_seconds,
                "book_channel": self.book_channel,
            }
        )

    def get_default_settings(self):
        return self._settings_from(self._default_settings)

    def get_runtime_error(self):
        return self._runtime_error

    def _refresh_runtime_error(self) -> None:
        messages = [
            message
            for message in (self._state_error, self._flush_error, self._watchdog_error)
            if message
        ]
        self._runtime_error = " | ".join(messages)

    def _sync_runtime_error_diagnostics(self, *, emitted_at: float | None = None) -> None:
        if self._runtime_error == self._diagnostics_runtime_error:
            return
        self._diagnostics_runtime_error = self._runtime_error
        event_ts = float(emitted_at if emitted_at is not None else time.time())
        for inst_id in self.whitelist:
            self._emit_diagnostics_event(
                self._diagnostics.record_runtime_error(
                    inst_id,
                    message=self._runtime_error,
                    emitted_at=event_ts,
                )
            )

    def _set_runtime_issue(self, issue_name: str, message: str, *, emitted_at: float | None = None) -> None:
        setattr(self, issue_name, str(message or ""))
        self._refresh_runtime_error()
        self._sync_runtime_error_diagnostics(emitted_at=emitted_at)

    def _clear_runtime_issue(self, issue_name: str, *, emitted_at: float | None = None) -> None:
        setattr(self, issue_name, "")
        self._refresh_runtime_error()
        self._sync_runtime_error_diagnostics(emitted_at=emitted_at)

    def get_model_status(self):
        return self._engine.get_model_status()

    def set_model_bundle(self, model_bundle) -> None:
        self._engine.set_model_bundle(model_bundle)
        self._hydrate_recent_bars_cache()

    def get_training_run(self):
        return self._training_tracker.snapshot()

    def add_listener(self, listener: Callable[[dict], None]) -> None:
        with self._listeners_lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[dict], None]) -> None:
        with self._listeners_lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    def add_diagnostics_listener(self, listener: Callable[[dict], None]) -> None:
        with self._listeners_lock:
            if listener not in self._diagnostics_listeners:
                self._diagnostics_listeners.append(listener)

    def remove_diagnostics_listener(self, listener: Callable[[dict], None]) -> None:
        with self._listeners_lock:
            if listener in self._diagnostics_listeners:
                self._diagnostics_listeners.remove(listener)

    def _emit_update(self) -> None:
        with self._listeners_lock:
            listeners = list(self._listeners)
        if not listeners:
            return
        payload = build_trend_realtime_payload(self)
        for listener in listeners:
            try:
                listener(payload)
            except Exception as exc:
                print(f"[TrendResearch] 推送监听器执行失败: {exc}")

    def _emit_diagnostics_event(self, payload: dict) -> None:
        with self._listeners_lock:
            listeners = list(self._diagnostics_listeners)
        for listener in listeners:
            try:
                listener(payload)
            except Exception as exc:
                print(f"[TrendResearch] 诊断监听器执行失败: {exc}")

    def _register_callbacks(self) -> None:
        if self._callbacks_registered:
            return
        self.ws_manager.add_trade_callback(self.on_trade)
        self.ws_manager.add_book_callback(self.on_book)
        self._callbacks_registered = True

    def _remove_callbacks(self) -> None:
        if not self._callbacks_registered:
            return
        self.ws_manager.remove_trade_callback(self.on_trade)
        self.ws_manager.remove_book_callback(self.on_book)
        self._callbacks_registered = False

    async def _start_unlocked(self):
        if self._running or not self._enabled or not self.whitelist:
            return
        self._register_callbacks()
        try:
            await self.ws_manager.subscribe_trades(list(self.whitelist))
            await self.ws_manager.subscribe_books(list(self.whitelist), channel=self.book_channel)
        except Exception:
            self._remove_callbacks()
            raise
        self._running = True
        self._state_task = asyncio.create_task(
            self._state_sync_loop(),
            name="trend_research_state_sync",
        )
        self._flush_task = asyncio.create_task(
            self._flush_loop(),
            name="trend_research_feature_flush",
        )
        self._watchdog_task = asyncio.create_task(
            self._watchdog_loop(),
            name="trend_research_watchdog",
        )
        try:
            await self.sync_contract_state_once()
        except Exception as exc:
            self._set_runtime_issue("_state_error", str(exc))
            self._emit_update()
        try:
            await self._flush_once_async()
        except Exception as exc:
            self._set_runtime_issue("_flush_error", str(exc))
            self._emit_update()

    async def start(self):
        async with self._runtime_lock:
            await self._start_unlocked()

    async def _stop_unlocked(self):
        self._running = False
        self._remove_callbacks()
        await cancel_task(self._flush_task)
        await cancel_task(self._state_task)
        await cancel_task(self._watchdog_task)
        self._flush_task = None
        self._state_task = None
        self._watchdog_task = None

    async def stop(self):
        async with self._runtime_lock:
            await self._stop_unlocked()

    async def on_ws_manager_restart(self) -> None:
        async with self._runtime_lock:
            next_ws_manager = self._ws_manager_supplier()
            if next_ws_manager is self.ws_manager:
                return
            was_running = self._running and self._enabled and bool(self.whitelist)
            self._remove_callbacks()
            self.ws_manager = next_ws_manager
            if not was_running:
                return
            self._register_callbacks()
            await self.ws_manager.subscribe_trades(list(self.whitelist))
            await self.ws_manager.subscribe_books(list(self.whitelist), channel=self.book_channel)
        self._emit_update()

    async def apply_settings(self, settings, *, persist: bool = False):
        normalized = normalize_trend_research_settings(settings, defaults=self._default_settings)
        if persist:
            if self._cfg is None:
                raise RuntimeError("趋势研究配置缺少持久化上下文")
            normalized = save_trend_research_settings(normalized, cfg=self._cfg)
        async with self._runtime_lock:
            await self._reload_runtime_unlocked(normalized)
        self._emit_update()
        return self.get_settings()

    async def _reload_runtime_unlocked(self, settings):
        previous_whitelist = list(self.whitelist)
        previous_channel = self.book_channel
        await self._stop_unlocked()
        if previous_whitelist:
            await self.ws_manager.unsubscribe_trades(previous_whitelist)
            await self.ws_manager.unsubscribe_books(previous_whitelist, channel=previous_channel)
        self._apply_runtime_settings(settings)
        await self._start_unlocked()

    async def _run_periodic_task(self, *, interval_seconds: float, operation, error_attr: str):
        while True:
            await asyncio.sleep(interval_seconds)
            try:
                await operation()
                self._clear_runtime_issue(error_attr)
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._set_runtime_issue(error_attr, str(exc))
                self._emit_update()

    async def _state_sync_loop(self):
        await self._run_periodic_task(
            interval_seconds=self.state_sync_seconds,
            operation=self.sync_contract_state_once,
            error_attr="_state_error",
        )

    async def _flush_loop(self):
        await self._run_periodic_task(
            interval_seconds=self.feature_bar_seconds,
            operation=self._flush_once_async,
            error_attr="_flush_error",
        )

    def _input_stale(self, event_ts: float | None) -> bool:
        if event_ts is None:
            return True
        return (time.time() - event_ts) >= DEFAULT_INPUT_STALE_SECONDS

    def _input_age_seconds(self, event_ts: float | None) -> float:
        if event_ts is None:
            return -1.0
        return max(time.time() - event_ts, 0.0)

    async def _replay_input_subscriptions(self) -> None:
        whitelist = list(self.whitelist)
        refresh_trades = getattr(self.ws_manager, "refresh_trade_subscriptions", None)
        if callable(refresh_trades):
            await refresh_trades(whitelist)
        else:
            await self.ws_manager.subscribe_trades(whitelist)
        refresh_books = getattr(self.ws_manager, "refresh_book_subscriptions", None)
        if callable(refresh_books):
            await refresh_books(whitelist, channel=self.book_channel)
            return
        await self.ws_manager.subscribe_books(whitelist, channel=self.book_channel)

    async def _watchdog_once(self) -> None:
        if not self._running or not self._enabled or not self.whitelist:
            return
        if not self._input_stale(self._last_trade_event_ts) and not self._input_stale(self._last_book_event_ts):
            self._clear_runtime_issue("_watchdog_error")
            return
        self._set_runtime_issue(
            "_watchdog_error",
            (
                f"输入流停滞：trade={self._input_age_seconds(self._last_trade_event_ts):.1f}s, "
                f"book={self._input_age_seconds(self._last_book_event_ts):.1f}s，已触发订阅重放"
            ),
        )
        await self._replay_input_subscriptions()

    def _clear_watchdog_issue_if_recovered(self, *, emitted_at: float) -> None:
        if not self._watchdog_error:
            return
        if self._input_stale(self._last_trade_event_ts) or self._input_stale(self._last_book_event_ts):
            return
        self._clear_runtime_issue("_watchdog_error", emitted_at=emitted_at)

    async def _watchdog_loop(self) -> None:
        await self._run_periodic_task(
            interval_seconds=DEFAULT_WATCHDOG_INTERVAL_SECONDS,
            operation=self._watchdog_once,
            error_attr="_watchdog_error",
        )

    def on_trade(self, inst_id: str, event: TradeTickEvent) -> None:
        diagnostics_event = self._runtime.on_trade(inst_id, event)
        if diagnostics_event is None:
            return
        self._last_trade_event_ts = event.ts_local or time.time()
        self._emit_diagnostics_event(diagnostics_event)
        self._clear_watchdog_issue_if_recovered(
            emitted_at=event.ts_local or time.time(),
        )
        self._emit_update()

    def on_book(self, inst_id: str, event: BookTopEvent) -> None:
        diagnostics_event = self._runtime.on_book(inst_id, event)
        if diagnostics_event is None:
            return
        self._last_book_event_ts = event.ts_local or time.time()
        self._emit_diagnostics_event(diagnostics_event)
        self._clear_watchdog_issue_if_recovered(
            emitted_at=event.ts_local or time.time(),
        )
        self._emit_update()

    def _collect_contract_states(self):
        snapshots = []
        for inst_id in self.whitelist:
            builder = self.builders.get(inst_id)
            if builder is None:
                continue
            snapshots.append((inst_id, build_contract_state_snapshot(self.fetcher, inst_id)))
        return snapshots

    async def sync_contract_state_once(self):
        try:
            snapshots = await asyncio.to_thread(self._collect_contract_states)
        except Exception as exc:
            self._set_runtime_issue("_state_error", str(exc))
            self._emit_update()
            raise
        for diagnostics_event in self._runtime.apply_contract_states(snapshots):
            self._emit_diagnostics_event(diagnostics_event)
        self._clear_runtime_issue("_state_error")
        self._emit_update()

    def _build_feature_bars(self, second_bucket: int):
        return [builder.flush(second_bucket) for builder in self.builders.values() if builder.has_snapshot()]

    def _update_inference_rows(self, rows) -> None:
        for row in rows:
            inst_id = row_inst_id(row)
            if inst_id:
                self._latest_inference_by_inst[inst_id] = row
        self._inference_rows = sort_inference_rows(list(self._latest_inference_by_inst.values()))

    def _build_inference_rows(self, bars):
        rows = []
        for bar in bars:
            recent_bars = append_recent_bar(self._recent_bars_by_inst, bar, limit=self.recent_bar_limit)
            rows.append(self._engine.build_snapshot(bar, recent_bars=recent_bars))
        return rows

    def _persist_flush_rows(self, bars, rows) -> None:
        self.storage.save_feature_bars_1s(bars)
        self.storage.save_inference_snapshots(rows)

    async def _flush_once_async(self, second_bucket: int | None = None):
        bucket = int(second_bucket if second_bucket is not None else time.time())
        bars = self._build_feature_bars(bucket)
        if not bars:
            return []
        rows = self._build_inference_rows(bars)
        await asyncio.to_thread(self._persist_flush_rows, bars, rows)
        self._update_inference_rows(rows)
        for diagnostics_event in self._runtime.record_flush(bars, rows):
            self._emit_diagnostics_event(diagnostics_event)
        self._clear_runtime_issue("_flush_error")
        self._emit_update()
        return rows

    def flush_once(self, second_bucket: int | None = None):
        bucket = int(second_bucket if second_bucket is not None else time.time())
        bars = self._build_feature_bars(bucket)
        if not bars:
            return []
        rows = self._build_inference_rows(bars)
        self._persist_flush_rows(bars, rows)
        self._update_inference_rows(rows)
        for diagnostics_event in self._runtime.record_flush(bars, rows):
            self._emit_diagnostics_event(diagnostics_event)
        self._emit_update()
        return rows

    def build_diagnostics_snapshot(
        self,
        *,
        inst_id: str | None = None,
        timeline_limit: int = 40,
    ) -> dict:
        return self._runtime.build_snapshot(
            inst_id=inst_id,
            timeline_limit=timeline_limit,
        )

    def replace_inference_snapshots(self, rows):
        self.storage.save_inference_snapshots(rows)
        self._latest_inference_by_inst = {}
        self._update_inference_rows(list(rows))

    def list_inference(self, limit: int = 100):
        normalized_limit = max(int(limit or 100), 1)
        if not self._inference_rows:
            rows = self.storage.list_latest_inference_snapshots(
                limit=max(normalized_limit, len(self.whitelist), 100),
                inst_ids=list(self.whitelist),
            )
            self._latest_inference_by_inst = {row.inst_id: row for row in rows}
            self._inference_rows = sort_inference_rows(rows)
        return self._inference_rows[:normalized_limit]

    def list_feature_bars(self, inst_id: str, limit: int = 100):
        rows = self.storage.list_feature_bars_1s(inst_id, limit=max(int(limit or 100), 1))
        return list(reversed(rows))

    def rebuild_factor_scores(self, inst_id: str, *, lookback: int = DEFAULT_FACTOR_LOOKBACK, limit: int = DEFAULT_FACTOR_LIMIT):
        return rebuild_factor_scores_for_inst(self.storage, inst_id, lookback=lookback, limit=limit)

    def list_factor_scores(self, inst_id: str, limit: int = DEFAULT_FACTOR_LIMIT):
        return self.storage.list_factor_scores(inst_id, limit=max(int(limit or DEFAULT_FACTOR_LIMIT), 1))

    def list_factor_series(self, inst_id: str, *, lookback: int, limit: int | None = None):
        return build_factor_series_payload(self.storage, inst_id, lookback=lookback, limit=limit)

    def _queue_training_event(self, payload: dict[str, object]) -> None:
        if self._training_loop is None:
            raise RuntimeError("training loop is not initialized")
        self._training_loop.call_soon_threadsafe(
            self._apply_training_event,
            dict(payload),
        )

    def _apply_training_event(self, payload: dict[str, object]) -> None:
        kind = str(payload.get("kind") or "")
        if kind == "stage":
            stage = str(payload["stage"])
            status = str(payload["status"])
            message = str(payload.get("message") or "")
            stats = dict(payload.get("stats") or {})
            if status == "running":
                self._training_tracker.start_stage(stage, message=message)
            elif status == "completed":
                self._training_tracker.finish_stage(
                    stage,
                    message=message,
                    stats=stats,
                )
            elif status == "failed":
                self._training_tracker.fail_run(
                    stage,
                    message or "training stage failed",
                )
            self._emit_update()
            return
        if kind != "epoch":
            return
        self._training_tracker.record_epoch(
            epoch=payload["epoch"],
            total_epochs=payload["total_epochs"],
            train_loss=payload["train_loss"],
            validation_loss=payload["validation_loss"],
        )
        self._emit_update()

    async def start_retrain_model(
        self,
        *,
        lookback: int = DEFAULT_FACTOR_LOOKBACK,
    ):
        if self._training_task is not None and not self._training_task.done():
            raise RuntimeError("trend research training already running")
        self._training_loop = asyncio.get_running_loop()
        self._training_tracker.start_run(
            lookback=lookback,
            total_epochs=DEFAULT_EPOCHS,
        )
        self._emit_update()
        self._training_task = asyncio.create_task(
            self._run_retrain_model_async(lookback),
            name="trend_research_model_train",
        )
        return self.get_training_run()

    async def _run_retrain_model_async(self, lookback: int):
        from .training_runtime import retrain_model_from_storage

        try:
            bundle = await asyncio.to_thread(
                retrain_model_from_storage,
                self.storage,
                tuple(self.whitelist),
                lookback=lookback,
                progress_callback=self._queue_training_event,
            )
            # Allow thread-safe progress callbacks to settle before finalizing run status.
            await asyncio.sleep(0)
            self._training_tracker.start_stage(
                "activate_model",
                message="activating trained model",
            )
            self.set_model_bundle(bundle)
            self._training_tracker.finish_stage(
                "activate_model",
                message="model activated",
                stats={"selected_feature_count": len(bundle.config.feature_names)},
            )
            self._training_tracker.complete_run(message="model activated")
            self._emit_update()
        except Exception as exc:
            current_stage = self.get_training_run().get("current_stage") or "queued"
            if self.get_training_run().get("status") != "failed":
                self._training_tracker.fail_run(current_stage, str(exc))
                self._emit_update()
            raise
        finally:
            self._training_loop = None

    def retrain_model(self, *, lookback: int = DEFAULT_FACTOR_LOOKBACK):
        from .training_runtime import retrain_model_from_storage

        bundle = retrain_model_from_storage(
            self.storage,
            tuple(self.whitelist),
            lookback=lookback,
        )
        self.set_model_bundle(bundle)
        self._emit_update()
        return self.get_model_status()
