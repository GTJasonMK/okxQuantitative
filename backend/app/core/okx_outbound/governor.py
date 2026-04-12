from __future__ import annotations

import time
from collections import deque
from threading import Lock
from typing import Callable, TypeVar

from .models import OKXOutboundEvent
from .rules import OKXRateRuleRegistry
from .timeline import OKXOutboundTimelineStore


_T = TypeVar("_T")

DEFAULT_MAX_WAIT_SECONDS = 15.0


def _classify_result(payload) -> str:
    if isinstance(payload, dict):
        code = payload.get("code")
        if code not in (None, 0, "0"):
            return "error"
        if payload.get("success") is False:
            return "error"
    return "ok"


class OKXOutboundGovernor:
    def __init__(
        self,
        *,
        registry: OKXRateRuleRegistry | None = None,
        timeline: OKXOutboundTimelineStore | None = None,
        time_fn: Callable[[], float] | None = None,
        sleep_fn: Callable[[float], None] | None = None,
    ):
        self._registry = registry or OKXRateRuleRegistry()
        self._timeline = timeline or OKXOutboundTimelineStore()
        self._time_fn = time_fn or time.time
        self._sleep_fn = sleep_fn or time.sleep
        self._windows: dict[str, deque[float]] = {}
        self._lock = Lock()

    def _bucket_key(self, rule, *, scope_key: str, inst_id: str) -> str:
        if rule.rule_key != "public_ip_inst":
            return f"{rule.op_key}|{scope_key}"

        normalized_inst_id = str(inst_id or "").strip().upper()
        if not normalized_inst_id:
            raise ValueError(f"{rule.op_key} 需要 inst_id 才能按官方规则限流")
        return f"{rule.op_key}|{scope_key}:{normalized_inst_id}"

    def acquire(
        self,
        op_key: str,
        *,
        scope_key: str,
        inst_id: str = "",
        max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS,
    ):
        rule = self._registry.get(op_key)
        deadline = self._time_fn() + max(max_wait_seconds, 0.0)
        bucket_key = self._bucket_key(rule, scope_key=scope_key, inst_id=inst_id)

        while True:
            now = self._time_fn()
            with self._lock:
                calls = self._windows.setdefault(bucket_key, deque())
                cutoff = now - rule.window_seconds
                while calls and calls[0] <= cutoff:
                    calls.popleft()
                if len(calls) < rule.capacity:
                    calls.append(now)
                    return rule
                next_slot = calls[0] + rule.window_seconds

            wait_seconds = max(0.0, next_slot - now)
            if now + wait_seconds > deadline:
                raise RuntimeError(f"{op_key} 等待官方限流窗口超时")
            self._sleep_fn(wait_seconds)

    def execute_rest(
        self,
        *,
        op_key: str,
        scope_key: str,
        inst_id: str = "",
        mode: str = "",
        operation: Callable[[], _T],
        max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS,
    ) -> _T:
        rule = self.acquire(
            op_key,
            scope_key=scope_key,
            inst_id=inst_id,
            max_wait_seconds=max_wait_seconds,
        )
        started_at = self._time_fn()
        try:
            payload = operation()
        except Exception:
            self._record(rule, started_at, scope_key, inst_id, mode, "error")
            raise
        self._record(rule, started_at, scope_key, inst_id, mode, _classify_result(payload))
        return payload

    async def execute_ws_control(
        self,
        *,
        op_key: str,
        scope_key: str,
        inst_id: str = "",
        mode: str = "",
        operation,
        max_wait_seconds: float = DEFAULT_MAX_WAIT_SECONDS,
    ):
        rule = self.acquire(
            op_key,
            scope_key=scope_key,
            inst_id=inst_id,
            max_wait_seconds=max_wait_seconds,
        )
        started_at = self._time_fn()
        try:
            payload = await operation()
        except Exception:
            self._record(rule, started_at, scope_key, inst_id, mode, "error")
            raise
        self._record(rule, started_at, scope_key, inst_id, mode, _classify_result(payload))
        return payload

    def legacy_rate_limit_stats(self, *, window_seconds: int = 60) -> dict:
        snapshot = self._timeline.snapshot(
            window_seconds=window_seconds,
            now_ts=self._time_fn(),
            limit=100000,
        )
        events = snapshot["events"]
        return {
            "total_calls": len(events),
            "calls_per_minute": len(events),
            "rate_limit": None,
            "remaining_quota": None,
            "usage_percent": 0,
            "mode": "official_rules",
        }

    def debug_snapshot(self) -> dict:
        with self._lock:
            return {key: {"count": len(value)} for key, value in self._windows.items()}

    def timeline(self) -> OKXOutboundTimelineStore:
        return self._timeline

    def _record(
        self,
        rule,
        started_at: float,
        scope_key: str,
        inst_id: str,
        mode: str,
        result: str,
    ):
        latency_ms = max(int((self._time_fn() - started_at) * 1000), 0)
        self._timeline.record(
            OKXOutboundEvent(
                ts=started_at,
                op_key=rule.op_key,
                channel=rule.channel,
                target_group=rule.target_group,
                rule_key=rule.rule_key,
                scope_key=scope_key,
                inst_id=inst_id,
                mode=mode,
                result=result,
                latency_ms=latency_ms,
            )
        )
