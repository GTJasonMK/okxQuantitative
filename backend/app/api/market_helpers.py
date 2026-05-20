from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from ..core import CachedDataFetcher, CachedDataManager, DataStorage
from ..core.data_guardian import DEFAULT_TIMEFRAME_PLANS, get_data_guardian
from ..core.market_sync_tasks import get_market_sync_task_manager
from ..models.schemas import InstTypeEnum, SyncModeEnum
from ..utils.watched_symbols_store import (
    load_watched_symbols,
    normalize_watched_symbol,
    remove_watched_symbol,
    save_watched_symbols,
)


def _execute_sync(
    manager: CachedDataManager,
    *,
    inst_id: str,
    timeframe: str,
    days: int,
    inst_type: str,
    mode: str,
    progress_callback=None,
):
    if mode == SyncModeEnum.FULL.value:
        return manager.sync_candles_full(
            inst_id,
            timeframe,
            days,
            inst_type,
            progress_callback=progress_callback,
        )
    if mode == SyncModeEnum.INCREMENTAL.value:
        return manager.sync_candles_incremental(
            inst_id,
            timeframe,
            days,
            inst_type,
            progress_callback=progress_callback,
        )
    return manager.sync_candles_window(
        inst_id,
        timeframe,
        days,
        inst_type,
        progress_callback=progress_callback,
    )


def _build_sync_runner(
    manager: CachedDataManager,
    *,
    inst_id: str,
    timeframe: str,
    days: int,
    inst_type: str,
    mode: str,
):
    return lambda progress_callback: _execute_sync(
        manager,
        inst_id=inst_id,
        timeframe=timeframe,
        days=days,
        inst_type=inst_type,
        mode=mode,
        progress_callback=progress_callback,
    )


def _resolve_watch_sync_plans() -> List[Dict[str, Any]]:
    guardian = get_data_guardian()
    settings = guardian.get_settings()
    plans = settings.get("plans") if isinstance(settings, dict) else None
    if not isinstance(plans, list) or not plans:
        plans = DEFAULT_TIMEFRAME_PLANS

    normalized_plans: List[Dict[str, Any]] = []
    for plan in plans:
        if not isinstance(plan, dict):
            continue
        timeframe = str(plan.get("timeframe") or "").strip()
        if not timeframe:
            continue
        if not bool(plan.get("enabled", True)):
            continue
        archive_mode = str(plan.get("archive_mode") or "rolling").strip().lower()
        if archive_mode not in {"rolling", "full"}:
            archive_mode = "rolling"
        normalized_plans.append({
            "timeframe": timeframe,
            "bootstrap_days": max(int(plan.get("bootstrap_days", 30) or 30), 1),
            "archive_mode": archive_mode,
        })
    return normalized_plans


def _start_watchlist_sync_jobs(
    manager: CachedDataManager,
    watched_symbol: Dict[str, Any],
    *,
    sync_spot: bool,
    sync_swap: bool,
) -> List[Dict[str, Any]]:
    task_manager = get_market_sync_task_manager()
    sync_jobs: List[Dict[str, Any]] = []
    sync_targets = []

    if sync_spot:
        sync_targets.append(("SPOT", watched_symbol.get("spot_inst_id") or watched_symbol["symbol"]))
    if sync_swap:
        sync_targets.append(("SWAP", watched_symbol.get("swap_inst_id") or f"{watched_symbol['symbol']}-SWAP"))

    plans = _resolve_watch_sync_plans()
    if not plans:
        return []

    for inst_type, inst_id in sync_targets:
        for plan in plans:
            sync_mode = "full" if plan.get("archive_mode") == "full" else "window"
            sync_jobs.append(
                task_manager.start_job(
                    inst_id=inst_id,
                    inst_type=inst_type,
                    timeframe=plan["timeframe"],
                    mode=sync_mode,
                    days=plan["bootstrap_days"],
                    runner=_build_sync_runner(
                        manager,
                        inst_id=inst_id,
                        timeframe=plan["timeframe"],
                        days=plan["bootstrap_days"],
                        inst_type=inst_type,
                        mode=sync_mode,
                    ),
                )
            )
    return sync_jobs


def _resolve_related_inst_ids(symbol: str) -> List[str]:
    normalized_symbol = normalize_watched_symbol(symbol)
    if not normalized_symbol:
        return []
    return [normalized_symbol, f"{normalized_symbol}-SWAP"]


def _resolve_inst_type_value(inst_id: str, inst_type: Optional[InstTypeEnum]) -> str:
    if inst_type is not None:
        return inst_type.value
    return "SWAP" if str(inst_id or "").upper().endswith("-SWAP") else "SPOT"


def _request_guardian_run_now_safely(source: str) -> None:
    try:
        guardian = get_data_guardian()
        guardian.request_run_now()
    except Exception as exc:
        print(f"[market] guardian.request_run_now 失败({source}): {exc}")


def _has_remote_market_fetcher(fetcher: Optional[CachedDataFetcher]) -> bool:
    """判断是否具备可用的远端行情抓取器。"""
    if not fetcher:
        return False
    if hasattr(fetcher, "fetcher"):
        return getattr(fetcher, "fetcher") is not None
    return True


def _require_remote_market_fetcher(fetcher: Optional[CachedDataFetcher]) -> CachedDataFetcher:
    if not _has_remote_market_fetcher(fetcher):
        raise HTTPException(status_code=503, detail="行情抓取器不可用")
    return fetcher


def _restore_watched_symbols_snapshot(records: List[Dict[str, Any]]) -> None:
    if not save_watched_symbols(records):
        raise RuntimeError("恢复关注币种快照失败")


def _raise_watchlist_create_rollback(
    *,
    snapshot: List[Dict[str, Any]],
    symbol: str,
    storage: Optional[DataStorage],
    detail: str,
    status_code: int,
):
    rollback_error = None
    try:
        _restore_watched_symbols_snapshot(snapshot)
        if storage is not None and not any(item.get("symbol") == symbol for item in snapshot):
            storage.block_symbol_writes(symbol)
    except Exception as exc:
        rollback_error = exc
    if rollback_error is not None:
        detail = f"{detail}；回滚错误: {rollback_error}"
    raise HTTPException(status_code=status_code, detail=detail)


def _cancel_related_sync_jobs(symbol: str, *, reason: str) -> List[Dict[str, Any]]:
    inst_ids = _resolve_related_inst_ids(symbol)
    if not inst_ids:
        return []
    task_manager = get_market_sync_task_manager()
    return task_manager.cancel_jobs(inst_ids=inst_ids, reason=reason)


def _delete_symbol_inventory_records(
    *,
    storage: DataStorage,
    symbol: str,
    remove_watch: bool,
    cancel_reason: str,
    keep_blocked_on_success: bool,
) -> Dict[str, Any]:
    watched_snapshot = load_watched_symbols()
    await_restore_watch = False
    removed_from_watch = False

    storage.block_symbol_writes(symbol)
    affected_jobs = _cancel_related_sync_jobs(symbol, reason=cancel_reason)

    if remove_watch:
        try:
            removed_record, removed = remove_watched_symbol(symbol)
            if not removed:
                raise RuntimeError("移除关注币种失败")
            removed_from_watch = bool(removed_record)
            await_restore_watch = True
        except Exception:
            storage.unblock_symbol_writes(symbol)
            raise

    try:
        deleted_counts = storage.delete_symbol_related_data(symbol)
    except Exception as exc:
        rollback_error = None
        try:
            if await_restore_watch:
                _restore_watched_symbols_snapshot(watched_snapshot)
        except Exception as rollback_exc:
            rollback_error = rollback_exc
        storage.unblock_symbol_writes(symbol)
        detail = f"{str(exc)}；已回滚关注列表"
        if rollback_error is not None:
            detail = f"{str(exc)}；回滚关注列表失败: {rollback_error}"
        raise RuntimeError(detail) from exc

    if not keep_blocked_on_success:
        storage.unblock_symbol_writes(symbol)

    return {
        "symbol": symbol,
        "removed_from_watch": removed_from_watch,
        "deleted_counts": deleted_counts,
        "active_sync_jobs": affected_jobs,
    }


def _build_inventory_response(storage: DataStorage) -> Dict[str, Any]:
    watched_items = load_watched_symbols()
    watched_symbols = {item["symbol"] for item in watched_items}
    rows = storage.get_symbol_data_inventory()

    table_totals = {
        "candles": 0,
        "sync_records": 0,
        "market_ticker_snapshots": 0,
        "market_recent_trades": 0,
        "local_fills": 0,
        "live_order_records": 0,
        "backtest_results": 0,
        "cost_basis": 0,
        "total": 0,
    }
    total_candles = 0
    total_timeframe_records = 0
    orphan_count = 0
    covered_watched_count = 0

    normalized_rows: List[Dict[str, Any]] = []
    for row in rows:
        symbol = normalize_watched_symbol(row.get("symbol"))
        watched = symbol in watched_symbols
        orphan = not watched
        if watched:
            covered_watched_count += 1
        if orphan:
            orphan_count += 1

        storage_counts = dict(row.get("storage_counts") or {})
        for key in table_totals:
            table_totals[key] += int(storage_counts.get(key, 0) or 0)

        total_candles += int(row.get("candle_count", 0) or 0)
        total_timeframe_records += int(row.get("timeframe_record_count", 0) or 0)

        normalized_rows.append({
            **row,
            "symbol": symbol,
            "watched": watched,
            "orphan": orphan,
        })

    return {
        "summary": {
            "symbol_count": len(normalized_rows),
            "watched_symbol_count": covered_watched_count,
            "watched_list_count": len(watched_symbols),
            "orphan_symbol_count": orphan_count,
            "total_candles": total_candles,
            "total_timeframe_records": total_timeframe_records,
            "table_totals": table_totals,
        },
        "rows": normalized_rows,
    }

