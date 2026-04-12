from __future__ import annotations


def build_diagnostics_snapshot_event(snapshot: dict) -> dict:
    return {
        "event_type": "snapshot",
        "inst_id": str(snapshot.get("selected_inst_id") or ""),
        "emitted_at": snapshot.get("emitted_at"),
        "sequence": 0,
        **snapshot,
    }


def build_diagnostics_ws_message(payload: dict) -> dict:
    return {
        "type": "trend_diagnostics",
        "data": payload,
    }
