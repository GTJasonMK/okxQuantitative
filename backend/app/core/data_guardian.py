from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from threading import Lock
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..config import config
from ..utils.preferences_store import load_preferences, merge_preferences
from ..utils.watched_symbols_store import load_watched_symbols

if TYPE_CHECKING:
    from .app_context import AppContext


PREFERENCES_KEY = "data_guardian_settings"
TIMEFRAME_ORDER = {
    "1m": 1,
    "3m": 2,
    "5m": 3,
    "15m": 4,
    "30m": 5,
    "1H": 6,
    "2H": 7,
    "4H": 8,
    "6H": 9,
    "12H": 10,
    "1D": 11,
    "1W": 12,
    "1M": 13,
}
DEFAULT_TIMEFRAME_PLANS: List[Dict[str, Any]] = [
    {"timeframe": "1D", "enabled": True, "bootstrap_days": 365, "archive_mode": "full"},
    {"timeframe": "4H", "enabled": True, "bootstrap_days": 365, "archive_mode": "full"},
    {"timeframe": "1H", "enabled": True, "bootstrap_days": 180, "archive_mode": "full"},
    {"timeframe": "15m", "enabled": True, "bootstrap_days": 45, "archive_mode": "full"},
    {"timeframe": "5m", "enabled": True, "bootstrap_days": 14, "archive_mode": "rolling"},
    {"timeframe": "1m", "enabled": True, "bootstrap_days": 3, "archive_mode": "rolling"},
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


from ..utils.numbers import clamp_int as _clamp_int


def _sort_plans(plans: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(plans, key=lambda item: TIMEFRAME_ORDER.get(item["timeframe"], 999))


def build_default_guardian_settings() -> Dict[str, Any]:
    return {
        "enabled": True,
        "scan_interval_seconds": max(120, int(config.cache.sync_cooldown)),
        "max_full_backfill_jobs_per_cycle": 3,
        "plans": deepcopy(DEFAULT_TIMEFRAME_PLANS),
    }


def normalize_guardian_settings(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    defaults = build_default_guardian_settings()
    payload = payload or {}

    plans_payload = payload.get("plans")
    if not isinstance(plans_payload, list):
        plans_payload = payload.get("timeframe_plans")
    if not isinstance(plans_payload, list):
        plans_payload = []

    raw_plans_by_timeframe: Dict[str, Dict[str, Any]] = {}
    for raw_plan in plans_payload:
        if not isinstance(raw_plan, dict):
            continue
        timeframe = str(raw_plan.get("timeframe") or "").strip()
        if not timeframe:
            continue
        raw_plans_by_timeframe[timeframe] = raw_plan

    normalized_plans: List[Dict[str, Any]] = []
    for default_plan in defaults["plans"]:
        raw_plan = raw_plans_by_timeframe.get(default_plan["timeframe"], {})
        archive_mode = str(
            raw_plan.get("archive_mode")
            or raw_plan.get("archiveMode")
            or default_plan["archive_mode"]
        ).strip().lower()
        if archive_mode not in {"rolling", "full"}:
            archive_mode = default_plan["archive_mode"]

        normalized_plans.append(
            {
                "timeframe": default_plan["timeframe"],
                "enabled": bool(raw_plan.get("enabled", default_plan["enabled"])),
                "bootstrap_days": _clamp_int(
                    raw_plan.get("bootstrap_days", raw_plan.get("bootstrapDays")),
                    default=default_plan["bootstrap_days"],
                    minimum=1,
                    maximum=3650,
                ),
                "archive_mode": archive_mode,
            }
        )

    return {
        "enabled": bool(payload.get("enabled", defaults["enabled"])),
        "scan_interval_seconds": _clamp_int(
            payload.get("scan_interval_seconds", payload.get("scanIntervalSeconds")),
            default=defaults["scan_interval_seconds"],
            minimum=60,
            maximum=3600,
        ),
        "max_full_backfill_jobs_per_cycle": _clamp_int(
            payload.get(
                "max_full_backfill_jobs_per_cycle",
                payload.get("maxFullBackfillJobsPerCycle"),
            ),
            default=defaults["max_full_backfill_jobs_per_cycle"],
            minimum=1,
            maximum=20,
        ),
        "plans": _sort_plans(normalized_plans),
    }


def load_data_guardian_settings() -> Dict[str, Any]:
    payload = load_preferences()
    settings = payload.get(PREFERENCES_KEY)
    if not isinstance(settings, dict):
        settings = {}
    return normalize_guardian_settings(settings)


def save_data_guardian_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_guardian_settings(settings)
    if not merge_preferences({PREFERENCES_KEY: normalized}):
        raise RuntimeError("保存数据守护器配置失败")
    return normalized


@dataclass(frozen=True)
class WatchTarget:
    symbol: str
    inst_id: str
    inst_type: str
    archive_all_history: bool = False


@dataclass
class CycleAction:
    key: str
    target: WatchTarget
    timeframe: str
    bootstrap_days: int
    desired_mode: str
    selected_mode: str


class MarketDataGuardian:
    """后台常驻数据守护器。

    目标：
    - 自动读取行情监控页监控池，维护本地 K 线仓
    - 支持可配置的滚动窗口 / 全量归档策略
    - 通过回补队列限制重型全量任务的并发度
    """

    def __init__(self, ctx: "AppContext") -> None:
        self._ctx = ctx
        self._status_lock = Lock()
        self._task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._wake_event: Optional[asyncio.Event] = None
        self._backfill_cursor = 0
        self._settings = build_default_guardian_settings()
        self._active_plans: List[Dict[str, Any]] = []
        self._scan_interval_seconds = self._settings["scan_interval_seconds"]
        self._max_full_backfill_jobs_per_cycle = self._settings["max_full_backfill_jobs_per_cycle"]
        self._status: Dict[str, Any] = self._build_initial_status()
        self.apply_settings(load_data_guardian_settings(), persist=False)

    def _build_initial_status(self) -> Dict[str, Any]:
        defaults = build_default_guardian_settings()
        return {
            "enabled": defaults["enabled"],
            "running": False,
            "active": False,
            "exchange_available": False,
            "scan_interval_seconds": defaults["scan_interval_seconds"],
            "max_full_backfill_jobs_per_cycle": defaults["max_full_backfill_jobs_per_cycle"],
            "policy_summary": "",
            "settings": defaults,
            "timeframes": [],
            "full_backfill_timeframes": [],
            "rolling_window_timeframes": [],
            "watched_symbols": [],
            "watched_instruments": [],
            "watched_count": 0,
            "inst_type": "SPOT",
            "current_inst_id": "",
            "current_timeframe": "",
            "current_mode": "",
            "current_phase": "idle",
            "cycle_completed_units": 0,
            "cycle_total_units": 0,
            "backfill_queue_size": 0,
            "backfill_queue_preview": [],
            "last_run_started_at": None,
            "last_run_finished_at": None,
            "last_successful_run_at": None,
            "last_triggered_at": None,
            "last_run_summary": {
                "success_count": 0,
                "error_count": 0,
                "total_units": 0,
            },
            "last_sync_results": [],
            "last_errors": [],
        }

    def _update_status(self, **kwargs: Any) -> None:
        with self._status_lock:
            self._status.update(kwargs)

    def _append_status_item(self, field: str, payload: Dict[str, Any], *, limit: int = 20) -> None:
        with self._status_lock:
            items = list(self._status.get(field, []))
            items.insert(0, payload)
            self._status[field] = items[:limit]

    def get_status(self) -> Dict[str, Any]:
        with self._status_lock:
            snapshot = deepcopy(self._status)
        snapshot["running"] = bool(self._task and not self._task.done())
        return snapshot

    def get_settings(self) -> Dict[str, Any]:
        return deepcopy(self._settings)

    def get_default_settings(self) -> Dict[str, Any]:
        return build_default_guardian_settings()

    def _build_policy_summary(self, settings: Dict[str, Any]) -> str:
        enabled_plans = [plan for plan in settings["plans"] if plan["enabled"]]
        if not enabled_plans:
            return "当前未启用任何周期，守护器只会待机。"

        full_items = [plan["timeframe"] for plan in enabled_plans if plan["archive_mode"] == "full"]
        rolling_items = [plan["timeframe"] for plan in enabled_plans if plan["archive_mode"] != "full"]

        summary_parts = [
            f"启用 {len(enabled_plans)} 个周期",
            f"每轮最多执行 {settings['max_full_backfill_jobs_per_cycle']} 个全量回补任务",
        ]
        if full_items:
            summary_parts.append(f"全量归档：{' / '.join(full_items)}")
        if rolling_items:
            summary_parts.append(f"滚动维护：{' / '.join(rolling_items)}")
        return "；".join(summary_parts)

    def apply_settings(self, settings: Dict[str, Any], *, persist: bool = False) -> Dict[str, Any]:
        normalized = normalize_guardian_settings(settings)
        if persist:
            normalized = save_data_guardian_settings(normalized)

        self._settings = normalized
        self._scan_interval_seconds = normalized["scan_interval_seconds"]
        self._max_full_backfill_jobs_per_cycle = normalized["max_full_backfill_jobs_per_cycle"]
        self._active_plans = [plan for plan in normalized["plans"] if plan["enabled"]]

        enabled_timeframes = [plan["timeframe"] for plan in self._active_plans]
        full_backfill_timeframes = [
            plan["timeframe"] for plan in self._active_plans if plan["archive_mode"] == "full"
        ]
        rolling_window_timeframes = [
            plan["timeframe"] for plan in self._active_plans if plan["archive_mode"] != "full"
        ]

        self._update_status(
            enabled=normalized["enabled"],
            scan_interval_seconds=self._scan_interval_seconds,
            max_full_backfill_jobs_per_cycle=self._max_full_backfill_jobs_per_cycle,
            settings=deepcopy(normalized),
            timeframes=enabled_timeframes,
            full_backfill_timeframes=full_backfill_timeframes,
            rolling_window_timeframes=rolling_window_timeframes,
            policy_summary=self._build_policy_summary(normalized),
        )
        return self.get_settings()

    def reload_settings(self) -> Dict[str, Any]:
        return self.apply_settings(load_data_guardian_settings(), persist=False)

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event = asyncio.Event()
        self._wake_event = asyncio.Event()
        self._update_status(running=True, current_phase="idle")
        self._task = asyncio.create_task(self._run_loop(), name="market-data-guardian")

    async def stop(self) -> None:
        if not self._task:
            return
        if self._stop_event:
            self._stop_event.set()
        if self._wake_event:
            self._wake_event.set()
        try:
            await self._task
        finally:
            self._task = None
            self._update_status(
                running=False,
                active=False,
                current_phase="stopped",
                current_inst_id="",
                current_timeframe="",
                current_mode="",
                cycle_completed_units=0,
                cycle_total_units=0,
            )

    def request_run_now(self) -> Dict[str, Any]:
        self._update_status(last_triggered_at=_utc_now_iso())
        if self._wake_event:
            self._wake_event.set()
        return self.get_status()

    async def _run_loop(self) -> None:
        while self._stop_event and not self._stop_event.is_set():
            try:
                await self._run_scan_cycle()
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                self._record_error("guardian_loop", exc)

            if not self._stop_event or self._stop_event.is_set():
                break

            timeout = self._scan_interval_seconds
            try:
                if self._wake_event:
                    await asyncio.wait_for(self._wake_event.wait(), timeout=timeout)
            except asyncio.TimeoutError:
                pass
            finally:
                if self._wake_event and self._wake_event.is_set():
                    self._wake_event.clear()

    async def _run_scan_cycle(self) -> None:
        self.reload_settings()

        if not self._settings["enabled"]:
            now = _utc_now_iso()
            self._update_status(
                active=False,
                current_phase="disabled",
                cycle_completed_units=0,
                cycle_total_units=0,
                backfill_queue_size=0,
                backfill_queue_preview=[],
                last_run_finished_at=now,
            )
            return

        market_settings = self._load_market_settings()
        watched_symbols = self._load_watched_symbols()
        watch_targets, inst_type = self._build_watch_targets(market_settings, watched_symbols)
        fetcher_wrapper = self._ctx.fetcher()
        exchange_available = bool(fetcher_wrapper and fetcher_wrapper.fetcher)
        run_started_at = _utc_now_iso()
        watched_symbol_values = self._collect_unique_symbols(watch_targets)

        if not exchange_available:
            self._record_error("exchange", RuntimeError("公共行情抓取器不可用，数据守护器本轮跳过"))
            self._update_status(
                exchange_available=False,
                active=False,
                current_phase="idle",
                watched_symbols=watched_symbol_values,
                watched_instruments=[target.inst_id for target in watch_targets],
                watched_count=len(watched_symbol_values),
                inst_type=inst_type,
                last_run_started_at=run_started_at,
                last_run_finished_at=_utc_now_iso(),
            )
            return

        actions = self._build_cycle_actions(watch_targets)
        total_units = len(actions)

        self._update_status(
            exchange_available=True,
            active=True,
            current_phase="scan",
            watched_symbols=watched_symbol_values,
            watched_instruments=[target.inst_id for target in watch_targets],
            watched_count=len(watched_symbol_values),
            inst_type=inst_type,
            cycle_completed_units=0,
            cycle_total_units=total_units,
            last_run_started_at=run_started_at,
            last_run_summary={
                "success_count": 0,
                "error_count": 0,
                "total_units": total_units,
            },
        )

        if total_units == 0:
            finished_at = _utc_now_iso()
            self._update_status(
                active=False,
                current_phase="idle",
                current_inst_id="",
                current_timeframe="",
                current_mode="",
                last_run_finished_at=finished_at,
                last_successful_run_at=finished_at,
            )
            return

        success_count = 0
        error_count = 0
        completed_units = 0

        for action in actions:
            if self._stop_event and self._stop_event.is_set():
                break

            self._update_status(
                current_inst_id=action.target.inst_id,
                current_timeframe=action.timeframe,
                current_mode=action.selected_mode,
            )

            try:
                result = await asyncio.to_thread(self._sync_action, action)
                success_count += 1
                self._append_status_item("last_sync_results", result, limit=24)
            except Exception as exc:
                error_count += 1
                self._record_error(f"{action.target.inst_id}:{action.timeframe}", exc)
                self._append_status_item(
                    "last_sync_results",
                    {
                        "inst_id": action.target.inst_id,
                        "inst_type": action.target.inst_type,
                        "timeframe": action.timeframe,
                        "desired_mode": action.desired_mode,
                        "selected_mode": action.selected_mode,
                        "status": "error",
                        "error": str(exc),
                        "finished_at": _utc_now_iso(),
                    },
                    limit=24,
                )

            completed_units += 1
            self._update_status(
                cycle_completed_units=completed_units,
                last_run_summary={
                    "success_count": success_count,
                    "error_count": error_count,
                    "total_units": total_units,
                },
            )

        finished_at = _utc_now_iso()

        # 每轮扫描结束后清理过期的 ticker 快照和逐笔成交，防止表无限膨胀
        try:
            self._ctx.storage().purge_stale_market_streams(max_age_hours=48)
        except Exception as exc:
            self._record_error("purge_streams", exc)

        self._update_status(
            active=False,
            current_phase="idle",
            current_inst_id="",
            current_timeframe="",
            current_mode="",
            last_run_finished_at=finished_at,
        )
        if error_count == 0:
            self._update_status(last_successful_run_at=finished_at)

    def _load_market_settings(self) -> Dict[str, Any]:
        payload = load_preferences()
        market_settings = payload.get("market_settings")
        if isinstance(market_settings, dict):
            return market_settings
        return {}

    def _load_watched_symbols(self) -> List[Dict[str, Any]]:
        return load_watched_symbols()

    @staticmethod
    def _normalize_symbol(symbol: Any) -> str:
        return str(symbol or "").strip().upper()

    def _resolve_inst_id(self, symbol: str, inst_type: str) -> str:
        normalized = self._normalize_symbol(symbol)
        if not normalized:
            return ""
        if inst_type == "SWAP":
            return normalized if normalized.endswith("-SWAP") else f"{normalized}-SWAP"
        if normalized.endswith("-SWAP"):
            return normalized[:-5]
        return normalized

    @staticmethod
    def _collect_unique_symbols(watch_targets: List[WatchTarget]) -> List[str]:
        return list(dict.fromkeys(target.symbol for target in watch_targets if target.symbol))

    def _build_watch_targets(
        self,
        market_settings: Dict[str, Any],
        watched_symbols: Optional[List[Dict[str, Any]]] = None,
    ) -> tuple[List[WatchTarget], str]:
        explicit_watchlist = watched_symbols is not None
        watched_symbols = watched_symbols if watched_symbols is not None else self._load_watched_symbols()
        normalized_watched_symbols: List[str] = []
        sync_preferences: Dict[str, Dict[str, bool]] = {}
        for item in watched_symbols:
            raw_symbol = item.get("symbol") if isinstance(item, dict) else item
            normalized_symbol = self._normalize_symbol(raw_symbol).replace("-SWAP", "")
            if normalized_symbol:
                normalized_watched_symbols.append(normalized_symbol)
                sync_preferences[normalized_symbol] = {
                    "sync_spot": bool(item.get("sync_spot", True)) if isinstance(item, dict) else True,
                    "sync_swap": bool(item.get("sync_swap", True)) if isinstance(item, dict) else True,
                    "archive_all_history": bool(item.get("archive_all_history", False)) if isinstance(item, dict) else False,
                }

        if normalized_watched_symbols:
            targets: List[WatchTarget] = []
            seen: set[str] = set()
            for symbol in normalized_watched_symbols:
                if symbol in seen:
                    continue
                seen.add(symbol)
                preference = sync_preferences.get(symbol, {"sync_spot": True, "sync_swap": True, "archive_all_history": False})
                symbol_archive = bool(preference.get("archive_all_history", False))
                if preference.get("sync_spot", True):
                    targets.append(
                        WatchTarget(
                            symbol=symbol,
                            inst_id=self._resolve_inst_id(symbol, "SPOT"),
                            inst_type="SPOT",
                            archive_all_history=symbol_archive,
                        )
                    )
                if preference.get("sync_swap", True):
                    targets.append(
                        WatchTarget(
                            symbol=symbol,
                            inst_id=self._resolve_inst_id(symbol, "SWAP"),
                            inst_type="SWAP",
                            archive_all_history=symbol_archive,
                        )
                    )
            return targets, "MIXED"
        if explicit_watchlist:
            return [], "MIXED"

        inst_type = str(market_settings.get("marketInstType") or "SPOT").strip().upper()
        if inst_type not in {"SPOT", "SWAP"}:
            inst_type = "SPOT"

        raw_symbols = [
            *(market_settings.get("selectedSymbols") or []),
            market_settings.get("activeSymbol") or "",
            *(market_settings.get("customSymbols") or []),
        ]

        targets: List[WatchTarget] = []
        seen: set[str] = set()
        for raw_symbol in raw_symbols:
            symbol = self._normalize_symbol(raw_symbol).replace("-SWAP", "")
            if not symbol or symbol in seen:
                continue
            seen.add(symbol)
            targets.append(
                WatchTarget(
                    symbol=symbol,
                    inst_id=self._resolve_inst_id(symbol, inst_type),
                    inst_type=inst_type,
                )
            )
        return targets, inst_type

    def _find_plan(self, timeframe: str) -> Dict[str, Any]:
        for plan in self._settings["plans"]:
            if plan["timeframe"] == timeframe:
                return plan
        return {
            "timeframe": timeframe,
            "enabled": False,
            "bootstrap_days": 30,
            "archive_mode": "rolling",
        }

    def _select_sync_mode(
        self,
        sync_record: Optional[Dict[str, Any]],
        plan: Dict[str, Any],
        *,
        archive_all_history: bool = False,
    ) -> str:
        if not sync_record or int(sync_record.get("candle_count", 0) or 0) <= 0:
            return "window"
        if bool(sync_record.get("history_complete", False)):
            return "incremental"
        # 币种级全量归档：只要历史尚未拉完，始终走 full 模式
        if archive_all_history:
            return "full"
        if plan.get("archive_mode") == "full":
            return "full"
        return "incremental"

    def _select_backfill_keys(self, full_actions: List[CycleAction]) -> set[str]:
        if not full_actions:
            self._update_status(backfill_queue_size=0, backfill_queue_preview=[])
            return set()

        queue_size = len(full_actions)
        limit = min(self._max_full_backfill_jobs_per_cycle, queue_size)
        start = self._backfill_cursor % queue_size
        selected_keys = {
            full_actions[(start + offset) % queue_size].key
            for offset in range(limit)
        }
        self._backfill_cursor = (start + limit) % queue_size

        queue_preview = []
        for offset in range(queue_size):
            action = full_actions[(start + offset) % queue_size]
            queue_preview.append(
                {
                    "inst_id": action.target.inst_id,
                    "inst_type": action.target.inst_type,
                    "timeframe": action.timeframe,
                    "bootstrap_days": action.bootstrap_days,
                    "selected_this_cycle": action.key in selected_keys,
                }
            )

        self._update_status(
            backfill_queue_size=queue_size,
            backfill_queue_preview=queue_preview[:24],
        )
        return selected_keys

    def _build_cycle_actions(self, watch_targets: List[WatchTarget]) -> List[CycleAction]:
        if not self._active_plans or not watch_targets:
            self._update_status(backfill_queue_size=0, backfill_queue_preview=[])
            return []

        storage = self._ctx.storage()
        actions: List[CycleAction] = []
        full_actions: List[CycleAction] = []

        for target in watch_targets:
            for plan in self._active_plans:
                sync_record = storage.get_sync_record(target.inst_id, plan["timeframe"], target.inst_type)
                desired_mode = self._select_sync_mode(
                    sync_record, plan,
                    archive_all_history=target.archive_all_history,
                )

                # rolling 模式已有数据但 history_complete 未标记时，补标为完成
                # （rolling 不追求全量历史，有窗口数据即视为完整）
                if (
                    desired_mode == "incremental"
                    and sync_record
                    and int(sync_record.get("candle_count", 0) or 0) > 0
                    and not bool(sync_record.get("history_complete", False))
                    and plan.get("archive_mode") != "full"
                ):
                    storage.update_sync_record(
                        target.inst_id, plan["timeframe"], target.inst_type,
                        history_complete=True,
                    )

                action = CycleAction(
                    key=f"{target.inst_type}:{target.inst_id}:{plan['timeframe']}",
                    target=target,
                    timeframe=plan["timeframe"],
                    bootstrap_days=plan["bootstrap_days"],
                    desired_mode=desired_mode,
                    selected_mode=desired_mode,
                )
                actions.append(action)
                if desired_mode == "full":
                    full_actions.append(action)

        selected_backfill_keys = self._select_backfill_keys(full_actions)
        # 未排到的 full 任务直接跳过（不降级为其他模式），等下轮轮转
        return [
            action for action in actions
            if action.desired_mode != "full" or action.key in selected_backfill_keys
        ]

    def _sync_action(self, action: CycleAction) -> Dict[str, Any]:
        manager = self._ctx.manager()
        if action.selected_mode == "full":
            result = manager.sync_candles_full(
                action.target.inst_id,
                action.timeframe,
                days=action.bootstrap_days,
                inst_type=action.target.inst_type,
            )
        elif action.selected_mode == "incremental":
            result = manager.sync_candles_incremental(
                action.target.inst_id,
                action.timeframe,
                days=action.bootstrap_days,
                inst_type=action.target.inst_type,
            )
        else:
            result = manager.sync_candles_window(
                action.target.inst_id,
                action.timeframe,
                days=action.bootstrap_days,
                inst_type=action.target.inst_type,
            )

        return {
            "inst_id": action.target.inst_id,
            "inst_type": action.target.inst_type,
            "timeframe": action.timeframe,
            "desired_mode": action.desired_mode,
            "selected_mode": action.selected_mode,
            "status": "success",
            "finished_at": _utc_now_iso(),
            **(result or {}),
        }

    def _record_error(self, scope: str, exc: Exception) -> None:
        self._append_status_item(
            "last_errors",
            {
                "scope": scope,
                "message": str(exc),
                "when": _utc_now_iso(),
            },
            limit=12,
        )


_guardian: Optional[MarketDataGuardian] = None
_guardian_lock = Lock()


def get_data_guardian(ctx: Optional["AppContext"] = None) -> MarketDataGuardian:
    global _guardian
    if _guardian is None:
        with _guardian_lock:
            if _guardian is None:
                if ctx is None:
                    from .app_context import get_app_context

                    ctx = get_app_context()
                _guardian = MarketDataGuardian(ctx)
    return _guardian
