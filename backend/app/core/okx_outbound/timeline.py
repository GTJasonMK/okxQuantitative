from __future__ import annotations

import time
from collections import Counter, deque
from threading import Lock

from .models import OKXOutboundEvent


class OKXOutboundTimelineStore:
    def __init__(self, max_events: int = 12000):
        self._events: deque[OKXOutboundEvent] = deque(maxlen=max_events)
        self._lock = Lock()

    def record(self, event: OKXOutboundEvent):
        with self._lock:
            self._events.append(event)

    def record_event_for_test(
        self,
        *,
        op_key: str,
        channel: str,
        target_group: str,
        rule_key: str,
        scope_key: str,
        inst_id: str = "",
        mode: str = "",
        result: str = "ok",
        latency_ms: int = 0,
        ts: float | None = None,
    ):
        self.record(
            OKXOutboundEvent(
                ts=time.time() if ts is None else ts,
                op_key=op_key,
                channel=channel,
                target_group=target_group,
                rule_key=rule_key,
                scope_key=scope_key,
                inst_id=inst_id,
                mode=mode,
                result=result,
                latency_ms=latency_ms,
            )
        )

    def snapshot(self, *, window_seconds: int, now_ts: float, limit: int) -> dict:
        lower_bound = now_ts - max(int(window_seconds or 1), 1)
        normalized_limit = max(int(limit or 1), 1)
        with self._lock:
            events = [
                item.to_dict()
                for item in self._events
                if item.ts >= lower_bound
            ][-normalized_limit:]

        counts = Counter(item["op_key"] for item in events)
        slowest = sorted(
            events,
            key=lambda item: (int(item.get("latency_ms", 0) or 0), item["ts"]),
            reverse=True,
        )[:5]
        return {
            "window_seconds": max(int(window_seconds or 1), 1),
            "generated_at": now_ts,
            "events": events,
            "summary": {
                "event_count": len(events),
                "error_count": sum(1 for item in events if item.get("result") != "ok"),
                "success_count": sum(1 for item in events if item.get("result") == "ok"),
                "top_operations": [
                    {"op_key": op_key, "count": count}
                    for op_key, count in counts.most_common(5)
                ],
                "slowest_operations": [
                    {
                        "op_key": item["op_key"],
                        "latency_ms": int(item.get("latency_ms", 0) or 0),
                    }
                    for item in slowest
                ],
            },
        }
