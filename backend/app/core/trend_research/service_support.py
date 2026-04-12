from __future__ import annotations

import asyncio
import time

from .models import ContractStateSnapshot


def row_inst_id(row) -> str:
    if isinstance(row, dict):
        return str(row.get("inst_id", ""))
    return str(getattr(row, "inst_id", ""))


def row_second_bucket(row) -> int:
    if isinstance(row, dict):
        return int(row.get("second_bucket", 0) or 0)
    return int(getattr(row, "second_bucket", 0) or 0)


def sort_inference_rows(rows):
    return sorted(rows, key=lambda row: (-row_second_bucket(row), row_inst_id(row)))


def append_recent_bar(recent_bars_by_inst: dict, bar, *, limit: int):
    inst_rows = recent_bars_by_inst.setdefault(bar.inst_id, [])
    inst_rows.append(bar)
    if len(inst_rows) > limit:
        del inst_rows[:-limit]
    return tuple(inst_rows)


def settings_dict(*, enabled, whitelist, feature_bar_seconds, state_sync_seconds, book_channel):
    return {
        "enabled": bool(enabled),
        "whitelist": list(whitelist),
        "feature_bar_seconds": max(int(feature_bar_seconds or 1), 1),
        "state_sync_seconds": max(int(state_sync_seconds or 30), 5),
        "book_channel": str(book_channel or "books5"),
    }


async def cancel_task(task) -> None:
    if task is None:
        return
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        return


def build_contract_state_snapshot(fetcher, inst_id: str) -> ContractStateSnapshot:
    mark = fetcher.get_mark_price(inst_id)
    index = fetcher.get_index_price(inst_id)
    oi = fetcher.get_open_interest(inst_id)
    funding = fetcher.get_funding_rate(inst_id)
    return ContractStateSnapshot(
        inst_id=inst_id,
        ts_exchange=float(mark["ts"]) / 1000.0,
        ts_local=time.time(),
        mark_price=float(mark["mark_price"]),
        index_price=float(index["index_price"]),
        open_interest=float(oi["open_interest"]),
        funding_rate=float(funding["funding_rate"]),
        premium=float(funding.get("premium", 0.0)),
    )
