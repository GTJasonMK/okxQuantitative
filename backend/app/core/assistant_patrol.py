from __future__ import annotations

import asyncio
from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from typing import TYPE_CHECKING, Any, Awaitable, Callable, Dict, List, Optional
from uuid import uuid4

from ..agent.queries import AgentQueryService
from ..agent.schemas import AgentOpportunityPatrolRequest
from ..utils.mode import coerce_mode
from ..utils.preferences_store import load_preferences, merge_preferences

if TYPE_CHECKING:
    from .app_context import AppContext


PREFERENCES_KEY = "assistant_patrol_settings"
AssistantPatrolListener = Callable[[Dict[str, Any]], Awaitable[None] | None]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_now_ms() -> int:
    return int(datetime.now(timezone.utc).timestamp() * 1000)


def _clamp_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, numeric))


def _clamp_float(value: Any, *, default: float, minimum: float, maximum: float) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, numeric))


def _normalize_timeframes(value: Any) -> List[str]:
    if not isinstance(value, list):
        value = []
    cleaned = [str(item or "").strip() for item in value if str(item or "").strip()]
    return cleaned or ["1H", "4H"]


def build_default_assistant_patrol_settings() -> Dict[str, Any]:
    return {
        "enabled": False,
        "interval_seconds": 300,
        "scan_limit": 24,
        "candidate_limit": 3,
        "inst_type": "SWAP",
        "timeframes": ["1H", "4H"],
        "candles_limit": 240,
        "recent_trade_limit": 40,
        "orderbook_depth": 30,
        "mode": "simulated",
        "min_priority_score": 55.0,
        "notification_cooldown_seconds": 900,
    }


def normalize_assistant_patrol_settings(payload: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    defaults = build_default_assistant_patrol_settings()
    payload = payload or {}
    inst_type = str(payload.get("inst_type", defaults["inst_type"]) or defaults["inst_type"]).strip().upper()
    if inst_type not in {"SPOT", "SWAP"}:
        inst_type = defaults["inst_type"]

    return {
        "enabled": bool(payload.get("enabled", defaults["enabled"])),
        "interval_seconds": _clamp_int(
            payload.get("interval_seconds"),
            default=defaults["interval_seconds"],
            minimum=60,
            maximum=3600,
        ),
        "scan_limit": _clamp_int(
            payload.get("scan_limit"),
            default=defaults["scan_limit"],
            minimum=1,
            maximum=200,
        ),
        "candidate_limit": _clamp_int(
            payload.get("candidate_limit"),
            default=defaults["candidate_limit"],
            minimum=1,
            maximum=20,
        ),
        "inst_type": inst_type,
        "timeframes": _normalize_timeframes(payload.get("timeframes", defaults["timeframes"])),
        "candles_limit": _clamp_int(
            payload.get("candles_limit"),
            default=defaults["candles_limit"],
            minimum=60,
            maximum=2000,
        ),
        "recent_trade_limit": _clamp_int(
            payload.get("recent_trade_limit"),
            default=defaults["recent_trade_limit"],
            minimum=1,
            maximum=100,
        ),
        "orderbook_depth": _clamp_int(
            payload.get("orderbook_depth"),
            default=defaults["orderbook_depth"],
            minimum=1,
            maximum=200,
        ),
        "mode": coerce_mode(payload.get("mode"), defaults["mode"]),
        "min_priority_score": _clamp_float(
            payload.get("min_priority_score"),
            default=defaults["min_priority_score"],
            minimum=0.0,
            maximum=100.0,
        ),
        "notification_cooldown_seconds": _clamp_int(
            payload.get("notification_cooldown_seconds"),
            default=defaults["notification_cooldown_seconds"],
            minimum=60,
            maximum=86400,
        ),
    }


def load_assistant_patrol_settings() -> Dict[str, Any]:
    payload = load_preferences()
    settings = payload.get(PREFERENCES_KEY)
    if not isinstance(settings, dict):
        settings = {}
    return normalize_assistant_patrol_settings(settings)


def save_assistant_patrol_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    normalized = normalize_assistant_patrol_settings(settings)
    if not merge_preferences({PREFERENCES_KEY: normalized}):
        raise RuntimeError("保存巡检配置失败")
    return normalized


class AssistantOpportunityPatrol:
    """后台主动巡检关注币种，并把候选机会推送到前端。"""

    def __init__(self, ctx: "AppContext") -> None:
        self._ctx = ctx
        self._status_lock = Lock()
        self._listeners_lock = Lock()
        self._task: Optional[asyncio.Task] = None
        self._stop_event: Optional[asyncio.Event] = None
        self._wake_event: Optional[asyncio.Event] = None
        self._listeners: List[AssistantPatrolListener] = []
        self._recent_emissions: Dict[str, int] = {}
        self._settings = build_default_assistant_patrol_settings()
        self._status = self._build_initial_status()
        self.apply_settings(load_assistant_patrol_settings(), persist=False)

    def _build_initial_status(self) -> Dict[str, Any]:
        defaults = build_default_assistant_patrol_settings()
        return {
            "enabled": defaults["enabled"],
            "running": False,
            "current_phase": "idle",
            "settings": defaults,
            "last_run_started_at": None,
            "last_run_finished_at": None,
            "last_run_summary": {},
            "last_error": "",
            "recent_events": [],
            "recent_result": {},
        }

    def _update_status(self, **kwargs: Any) -> None:
        with self._status_lock:
            self._status.update(kwargs)

    def _prepend_status_item(self, field: str, item: Dict[str, Any], *, limit: int = 10) -> None:
        with self._status_lock:
            current = list(self._status.get(field, []))
            current.insert(0, item)
            self._status[field] = current[:limit]

    def get_status(self) -> Dict[str, Any]:
        with self._status_lock:
            snapshot = deepcopy(self._status)
        snapshot["running"] = bool(self._task and not self._task.done())
        return snapshot

    def get_settings(self) -> Dict[str, Any]:
        return deepcopy(self._settings)

    def apply_settings(self, settings: Dict[str, Any], *, persist: bool = False) -> Dict[str, Any]:
        normalized = normalize_assistant_patrol_settings(settings)
        if persist:
            normalized = save_assistant_patrol_settings(normalized)
        self._settings = normalized
        self._update_status(
            enabled=normalized["enabled"],
            settings=deepcopy(normalized),
        )
        self.wake()
        return self.get_settings()

    def reload_settings(self) -> Dict[str, Any]:
        return self.apply_settings(load_assistant_patrol_settings(), persist=False)

    def add_listener(self, listener: AssistantPatrolListener) -> None:
        with self._listeners_lock:
            if listener not in self._listeners:
                self._listeners.append(listener)

    def remove_listener(self, listener: AssistantPatrolListener) -> None:
        with self._listeners_lock:
            if listener in self._listeners:
                self._listeners.remove(listener)

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stop_event = asyncio.Event()
        self._wake_event = asyncio.Event()
        self._update_status(running=True, current_phase="idle")
        self._task = asyncio.create_task(self._run_loop(), name="assistant-opportunity-patrol")

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
            self._update_status(running=False, current_phase="idle")

    def wake(self) -> None:
        if self._wake_event:
            self._wake_event.set()

    def _cleanup_recent_emissions(self, cooldown_seconds: int) -> None:
        now_ms = _utc_now_ms()
        cutoff = now_ms - max(60, int(cooldown_seconds)) * 1000
        stale_keys = [key for key, ts in self._recent_emissions.items() if ts < cutoff]
        for key in stale_keys:
            self._recent_emissions.pop(key, None)

    def _build_candidate_fingerprint(self, candidate: Dict[str, Any]) -> str:
        return "|".join([
            str(candidate.get("symbol") or candidate.get("inst_id") or ""),
            str(candidate.get("bias") or ""),
            f"{float(candidate.get('entry_reference') or 0):.8f}",
            f"{float(candidate.get('invalidation_reference') or 0):.8f}",
        ])

    def _filter_new_candidates(self, candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        cooldown_seconds = int(self._settings["notification_cooldown_seconds"])
        self._cleanup_recent_emissions(cooldown_seconds)
        now_ms = _utc_now_ms()
        threshold = now_ms - cooldown_seconds * 1000

        fresh: List[Dict[str, Any]] = []
        for candidate in candidates:
            fingerprint = self._build_candidate_fingerprint(candidate)
            last_sent_ms = int(self._recent_emissions.get(fingerprint, 0) or 0)
            if last_sent_ms >= threshold:
                continue
            self._recent_emissions[fingerprint] = now_ms
            fresh.append(candidate)
        return fresh

    def _build_notification_payload(
        self,
        *,
        trigger: str,
        result: Dict[str, Any],
        candidates: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        top = candidates[0] if candidates else {}
        summary = result.get("summary") or {}
        title = (
            f"主动巡检发现 {len(candidates)} 个候选机会"
            if candidates else
            "主动巡检未发现高质量候选机会"
        )
        top_fragments = []
        for item in candidates[:3]:
            symbol = item.get("symbol") or item.get("inst_id") or "--"
            bias = "偏多" if item.get("bias") == "bullish" else ("偏空" if item.get("bias") == "bearish" else "中性")
            action = item.get("action") or "继续观察"
            top_fragments.append(f"{symbol} {bias}，{action}")
        message = "；".join(top_fragments) if top_fragments else (summary.get("message") or "本轮未发现符合条件的机会。")

        return {
            "id": f"assistant-patrol-{uuid4().hex[:12]}",
            "type": "assistant_patrol",
            "title": title,
            "message": message,
            "trigger": trigger,
            "created_at": _utc_now_iso(),
            "inst_type": self._settings["inst_type"],
            "mode": self._settings["mode"],
            "summary": summary,
            "top_candidate": top,
            "candidates": candidates,
        }

    async def _emit_event(self, payload: Dict[str, Any]) -> None:
        with self._listeners_lock:
            listeners = list(self._listeners)

        for listener in listeners:
            try:
                maybe_awaitable = listener(payload)
                if asyncio.iscoroutine(maybe_awaitable):
                    await maybe_awaitable
            except Exception as exc:
                print(f"[AssistantPatrol] 推送监听器执行失败: {exc}")

    async def run_cycle(self, *, trigger: str = "scheduled", force: bool = False) -> Dict[str, Any]:
        settings = self.get_settings()
        if not settings["enabled"] and not force:
            result = {
                "summary": {"message": "主动巡检未启用。", "candidate_count": 0, "scan_count": 0},
                "candidates": [],
            }
            self._update_status(current_phase="idle", recent_result=result)
            return result

        self._update_status(
            current_phase="scanning",
            last_run_started_at=_utc_now_iso(),
            last_error="",
        )

        request = AgentOpportunityPatrolRequest(
            inst_type=settings["inst_type"],
            scan_limit=settings["scan_limit"],
            candidate_limit=settings["candidate_limit"],
            timeframes=settings["timeframes"],
            candles_limit=settings["candles_limit"],
            recent_trade_limit=settings["recent_trade_limit"],
            orderbook_depth=settings["orderbook_depth"],
            mode=settings["mode"],
        )

        try:
            result = await asyncio.to_thread(
                AgentQueryService(self._ctx).patrol_market_opportunities,
                request,
            )
            candidates = [
                item for item in (result.get("candidates") or [])
                if float(item.get("priority_score") or 0) >= float(settings["min_priority_score"])
            ]
            result = {
                **result,
                "candidates": candidates,
                "summary": {
                    **(result.get("summary") or {}),
                    "filtered_candidate_count": len(candidates),
                    "min_priority_score": settings["min_priority_score"],
                },
            }
            should_emit = bool(candidates)
            emitted_candidates = candidates if trigger == "manual" else self._filter_new_candidates(candidates)
            event_payload = None
            if should_emit and emitted_candidates:
                event_payload = self._build_notification_payload(
                    trigger=trigger,
                    result=result,
                    candidates=emitted_candidates,
                )

            run_id = f"assistant-patrol-run-{uuid4().hex[:16]}"
            if event_payload:
                event_payload = {
                    **event_payload,
                    "run_id": run_id,
                }

            storage = self._ctx.storage()
            run_id = storage.create_assistant_patrol_run(
                run_id=run_id,
                trigger=trigger,
                inst_type=settings["inst_type"],
                mode=settings["mode"],
                summary=result.get("summary") or {},
                candidates=candidates,
                result={**result, "run_id": run_id},
                event=event_payload,
                settings=settings,
            )
            result = {
                **result,
                "run_id": run_id,
            }
            if event_payload:
                await self._emit_event(event_payload)
                self._prepend_status_item("recent_events", event_payload, limit=12)

            self._update_status(
                current_phase="idle",
                last_run_finished_at=_utc_now_iso(),
                last_run_summary={
                    **(result.get("summary") or {}),
                    "emitted_candidate_count": len(emitted_candidates),
                    "trigger": trigger,
                },
                recent_result=result,
            )
            return {
                **result,
                "event": event_payload,
            }
        except Exception as exc:
            error_text = str(exc)
            self._update_status(
                current_phase="idle",
                last_run_finished_at=_utc_now_iso(),
                last_error=error_text,
            )
            raise

    async def run_now(self) -> Dict[str, Any]:
        return await self.run_cycle(trigger="manual", force=True)

    async def _run_loop(self) -> None:
        while self._stop_event and not self._stop_event.is_set():
            settings = self.get_settings()
            if settings["enabled"]:
                try:
                    await self.run_cycle(trigger="scheduled", force=False)
                except Exception as exc:
                    self._update_status(last_error=str(exc), current_phase="idle")
                    print(f"[AssistantPatrol] 后台巡检失败: {exc}")
            else:
                self._update_status(current_phase="idle")

            try:
                await asyncio.wait_for(
                    self._wake_event.wait(),
                    timeout=max(60, int(settings["interval_seconds"])),
                )
            except asyncio.TimeoutError:
                pass

            if self._wake_event:
                self._wake_event.clear()


_assistant_patrol: Optional[AssistantOpportunityPatrol] = None
_assistant_patrol_lock = Lock()


def get_assistant_patrol(ctx: Optional["AppContext"] = None) -> AssistantOpportunityPatrol:
    global _assistant_patrol
    if _assistant_patrol is None:
        with _assistant_patrol_lock:
            if _assistant_patrol is None:
                if ctx is None:
                    from .app_context import get_app_context
                    ctx = get_app_context()
                _assistant_patrol = AssistantOpportunityPatrol(ctx)
    return _assistant_patrol
