from __future__ import annotations

from dataclasses import is_dataclass


def _row_inst_id(row) -> str:
    if row is None:
        return ""
    if isinstance(row, dict):
        return str(row.get("inst_id") or "")
    if is_dataclass(row):
        return str(getattr(row, "inst_id", "") or "")
    return str(getattr(row, "inst_id", "") or "")


class TrendResearchRuntime:
    def __init__(self, *, builders, projector):
        self._builders = builders
        self._projector = projector

    def on_trade(self, inst_id: str, event):
        builder = self._builders.get(inst_id)
        if builder is None:
            return None
        builder.apply_trade(event)
        return self._projector.record_trade_input(
            inst_id,
            emitted_at=event.ts_local,
        )

    def on_book(self, inst_id: str, event):
        builder = self._builders.get(inst_id)
        if builder is None:
            return None
        builder.apply_book(event)
        return self._projector.record_book_input(
            inst_id,
            emitted_at=event.ts_local,
        )

    def apply_contract_states(self, snapshots):
        events = []
        for inst_id, snapshot in snapshots:
            builder = self._builders.get(inst_id)
            if builder is None:
                continue
            builder.apply_contract_state(snapshot)
            events.append(
                self._projector.record_state_sync(
                    inst_id,
                    emitted_at=snapshot.ts_local,
                )
            )
        return events

    def record_flush(self, bars, rows):
        events = []
        row_inst_ids = {_row_inst_id(row) for row in rows}
        for bar in bars:
            events.append(
                self._projector.record_feature_emitted(
                    bar.inst_id,
                    bucket=bar.second_bucket,
                    emitted_at=bar.ts_local,
                )
            )
            if bar.inst_id in row_inst_ids:
                events.append(
                    self._projector.record_inference_emitted(
                        bar.inst_id,
                        bucket=bar.second_bucket,
                        emitted_at=bar.ts_local,
                    )
                )
        return events

    def build_snapshot(
        self,
        *,
        inst_id: str | None = None,
        timeline_limit: int = 40,
    ) -> dict:
        return self._projector.build_snapshot(
            inst_id=inst_id,
            timeline_limit=timeline_limit,
        )
