from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import replace
from time import time

from .diagnostics_models import (
    DEFAULT_STALE_SECONDS,
    KIND_ERROR,
    KIND_RECOVERY,
    LABEL_BOOK,
    LABEL_ERROR,
    LABEL_FEATURE,
    LABEL_INFERENCE,
    LABEL_RECOVERY,
    LABEL_STATE,
    LABEL_TRADE,
    TrendInstrumentRuntimeState,
    TrendTimelineEntry,
    model_to_dict,
)
from .diagnostics_snapshot import (
    build_details_dict,
    build_global_health,
    build_health_dict,
)


class TrendDiagnosticsProjector:
    def __init__(
        self,
        *,
        timeline_window: int = 60,
        stale_seconds: float = DEFAULT_STALE_SECONDS,
    ):
        self._timeline_window = max(int(timeline_window or 60), 1)
        self._stale_seconds = float(stale_seconds or DEFAULT_STALE_SECONDS)
        self._sequence = 0
        self._inst_ids: tuple[str, ...] = ()
        self._states: dict[str, TrendInstrumentRuntimeState] = {}
        self._timeline = defaultdict(lambda: deque(maxlen=self._timeline_window))

    def reset_instruments(self, inst_ids) -> None:
        normalized = tuple(str(inst_id) for inst_id in inst_ids or ())
        self._inst_ids = normalized
        self._states = {
            inst_id: TrendInstrumentRuntimeState(inst_id=inst_id)
            for inst_id in normalized
        }
        self._timeline = defaultdict(lambda: deque(maxlen=self._timeline_window))

    def _state_for(self, inst_id: str) -> TrendInstrumentRuntimeState:
        if inst_id not in self._states:
            self._states[inst_id] = TrendInstrumentRuntimeState(inst_id=inst_id)
            self._inst_ids = (*self._inst_ids, inst_id)
        return self._states[inst_id]

    def _replace_state(self, inst_id: str, **changes) -> TrendInstrumentRuntimeState:
        state = replace(self._state_for(inst_id), **changes)
        self._states[inst_id] = state
        return state

    def _next_sequence(self) -> int:
        self._sequence += 1
        return self._sequence

    def _append_timeline(
        self,
        inst_id: str,
        *,
        kind: str,
        emitted_at: float,
        label: str,
        message: str = "",
        second_bucket: int | None = None,
    ) -> TrendTimelineEntry:
        entry = TrendTimelineEntry(
            sequence=self._next_sequence(),
            inst_id=inst_id,
            kind=kind,
            emitted_at=float(emitted_at),
            label=label,
            message=message,
            second_bucket=second_bucket,
        )
        self._timeline[inst_id].append(entry)
        return entry

    def _build_event(
        self,
        *,
        inst_id: str,
        event_type: str,
        entry: TrendTimelineEntry,
        payload: dict | None = None,
    ) -> dict:
        instruments = [
            self._health_dict(current_inst_id, entry.emitted_at)
            for current_inst_id in self._inst_ids
        ]
        health_map = {item["inst_id"]: item for item in instruments}
        return {
            "event_type": event_type,
            "inst_id": inst_id,
            "emitted_at": entry.emitted_at,
            "sequence": entry.sequence,
            "instruments": instruments,
            "payload": {
                "instrument_health": health_map.get(
                    inst_id,
                    self._health_dict(inst_id, entry.emitted_at),
                ),
                "global_health": build_global_health(instruments),
                "details": self._details_dict(inst_id),
                **(payload or {}),
            },
        }

    def _details_dict(self, inst_id: str) -> dict:
        return build_details_dict(self._state_for(inst_id))

    def _health_dict(self, inst_id: str, now_ts: float) -> dict:
        return build_health_dict(
            inst_id,
            self._state_for(inst_id),
            now_ts=now_ts,
            stale_seconds=self._stale_seconds,
        )
    def record_trade_input(self, inst_id: str, *, emitted_at: float) -> dict:
        self._replace_state(inst_id, last_trade_at=float(emitted_at))
        entry = self._append_timeline(
            inst_id,
            kind="trade",
            emitted_at=emitted_at,
            label=LABEL_TRADE,
        )
        return self._build_event(
            inst_id=inst_id,
            event_type="timeline_appended",
            entry=entry,
            payload={"timeline_entry": model_to_dict(entry)},
        )

    def record_book_input(self, inst_id: str, *, emitted_at: float) -> dict:
        self._replace_state(inst_id, last_book_at=float(emitted_at))
        entry = self._append_timeline(
            inst_id,
            kind="book",
            emitted_at=emitted_at,
            label=LABEL_BOOK,
        )
        return self._build_event(
            inst_id=inst_id,
            event_type="timeline_appended",
            entry=entry,
            payload={"timeline_entry": model_to_dict(entry)},
        )

    def record_state_sync(self, inst_id: str, *, emitted_at: float) -> dict:
        self._replace_state(inst_id, last_state_at=float(emitted_at))
        entry = self._append_timeline(
            inst_id,
            kind="state",
            emitted_at=emitted_at,
            label=LABEL_STATE,
        )
        return self._build_event(
            inst_id=inst_id,
            event_type="health_changed",
            entry=entry,
            payload={"timeline_entry": model_to_dict(entry)},
        )

    def record_feature_emitted(
        self,
        inst_id: str,
        *,
        bucket: int,
        emitted_at: float,
    ) -> dict:
        self._replace_state(
            inst_id,
            last_feature_at=float(emitted_at),
            last_feature_bucket=int(bucket),
        )
        entry = self._append_timeline(
            inst_id,
            kind="feature",
            emitted_at=emitted_at,
            label=LABEL_FEATURE,
            second_bucket=int(bucket),
        )
        return self._build_event(
            inst_id=inst_id,
            event_type="feature_emitted",
            entry=entry,
            payload={
                "timeline_entry": model_to_dict(entry),
                "details": self._details_dict(inst_id),
            },
        )

    def record_inference_emitted(
        self,
        inst_id: str,
        *,
        bucket: int,
        emitted_at: float,
    ) -> dict:
        self._replace_state(
            inst_id,
            last_inference_at=float(emitted_at),
            last_inference_bucket=int(bucket),
        )
        entry = self._append_timeline(
            inst_id,
            kind="inference",
            emitted_at=emitted_at,
            label=LABEL_INFERENCE,
            second_bucket=int(bucket),
        )
        return self._build_event(
            inst_id=inst_id,
            event_type="inference_emitted",
            entry=entry,
            payload={
                "timeline_entry": model_to_dict(entry),
                "details": self._details_dict(inst_id),
            },
        )

    def record_runtime_error(
        self,
        inst_id: str,
        *,
        message: str,
        emitted_at: float,
    ) -> dict:
        self._replace_state(
            inst_id,
            current_error=str(message or ""),
            last_error_at=float(emitted_at),
        )
        kind = KIND_ERROR if message else KIND_RECOVERY
        label = LABEL_ERROR if message else LABEL_RECOVERY
        entry = self._append_timeline(
            inst_id,
            kind=kind,
            emitted_at=emitted_at,
            label=label,
            message=str(message or ""),
        )
        return self._build_event(
            inst_id=inst_id,
            event_type="runtime_error_changed",
            entry=entry,
            payload={
                "timeline_entry": model_to_dict(entry),
                "current_error": str(message or ""),
            },
        )

    def build_snapshot(
        self,
        *,
        inst_id: str | None,
        timeline_limit: int,
        now_ts: float | None = None,
    ) -> dict:
        resolved_now = float(now_ts if now_ts is not None else time())
        selected_inst_id = str(inst_id or (self._inst_ids[0] if self._inst_ids else ""))
        instruments = [
            self._health_dict(current_inst_id, resolved_now)
            for current_inst_id in self._inst_ids
        ]
        health_map = {item["inst_id"]: item for item in instruments}
        timeline = [
            model_to_dict(entry)
            for entry in list(self._timeline.get(selected_inst_id, ()))
        ][-max(int(timeline_limit or 1), 1):]
        return {
            "selected_inst_id": selected_inst_id,
            "instruments": instruments,
            "global_health": build_global_health(instruments),
            "instrument_health": health_map.get(
                selected_inst_id,
                self._health_dict(selected_inst_id, resolved_now),
            ),
            "timeline": timeline,
            "details": self._details_dict(selected_inst_id),
            "emitted_at": resolved_now,
        }
