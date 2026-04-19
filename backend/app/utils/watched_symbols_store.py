from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

from .preferences_store import load_preferences, merge_preferences


WATCHED_SYMBOLS_KEY = "watched_symbols"
DEFAULT_QUOTE_CCY = "USDT"


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def normalize_watched_symbol(symbol: Any) -> str:
    """把用户输入统一成基础交易对，内部只存 BTC-USDT 这类基础 symbol。"""
    normalized = str(symbol or "").strip().upper()
    if not normalized:
        return ""
    if normalized.endswith("-SWAP"):
        normalized = normalized[:-5]
    if "-" not in normalized:
        normalized = f"{normalized}-{DEFAULT_QUOTE_CCY}"
    return normalized


def build_watched_symbol_record(
    symbol: Any,
    *,
    sync_spot: Optional[bool] = None,
    sync_swap: Optional[bool] = None,
    archive_all_history: Optional[bool] = None,
    existing: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    normalized_symbol = normalize_watched_symbol(symbol)
    if not normalized_symbol:
        raise ValueError("币种不能为空")

    now = _utc_now_iso()
    base_ccy = normalized_symbol.split("-")[0] if "-" in normalized_symbol else normalized_symbol
    existing = existing or {}

    return {
        "symbol": normalized_symbol,
        "base_ccy": base_ccy,
        "spot_inst_id": normalized_symbol,
        "swap_inst_id": f"{normalized_symbol}-SWAP",
        "sync_spot": bool(existing.get("sync_spot", True) if sync_spot is None else sync_spot),
        "sync_swap": bool(existing.get("sync_swap", True) if sync_swap is None else sync_swap),
        "archive_all_history": bool(existing.get("archive_all_history", False) if archive_all_history is None else archive_all_history),
        "created_at": existing.get("created_at") or now,
        "updated_at": existing.get("updated_at") or now,
    }


def normalize_watched_symbols(payload: Any) -> List[Dict[str, Any]]:
    if not isinstance(payload, list):
        payload = []

    records: List[Dict[str, Any]] = []
    seen: set[str] = set()
    for item in payload:
        raw_symbol = item.get("symbol") if isinstance(item, dict) else item
        normalized_symbol = normalize_watched_symbol(raw_symbol)
        if not normalized_symbol or normalized_symbol in seen:
            continue
        seen.add(normalized_symbol)
        existing = item if isinstance(item, dict) else None
        records.append(
            build_watched_symbol_record(
                normalized_symbol,
                sync_spot=bool(item.get("sync_spot", True)) if isinstance(item, dict) else True,
                sync_swap=bool(item.get("sync_swap", True)) if isinstance(item, dict) else True,
                archive_all_history=bool(item.get("archive_all_history", False)) if isinstance(item, dict) else False,
                existing=existing,
            )
        )
    return records


def load_watched_symbols() -> List[Dict[str, Any]]:
    payload = load_preferences()
    return normalize_watched_symbols(payload.get(WATCHED_SYMBOLS_KEY))


def save_watched_symbols(records: List[Dict[str, Any]]) -> bool:
    normalized = normalize_watched_symbols(records)
    return merge_preferences({WATCHED_SYMBOLS_KEY: normalized})


def get_watched_symbol(symbol: Any) -> Optional[Dict[str, Any]]:
    normalized_symbol = normalize_watched_symbol(symbol)
    if not normalized_symbol:
        return None
    for record in load_watched_symbols():
        if record["symbol"] == normalized_symbol:
            return record
    return None


def add_watched_symbol(
    symbol: Any,
    *,
    sync_spot: bool = True,
    sync_swap: bool = True,
    archive_all_history: bool = False,
) -> Tuple[Dict[str, Any], bool]:
    normalized_symbol = normalize_watched_symbol(symbol)
    if not normalized_symbol:
        raise ValueError("币种不能为空")

    records = load_watched_symbols()
    for index, existing in enumerate(records):
        if existing["symbol"] == normalized_symbol:
            # archive_all_history 在首次添加时确定，后续不允许修改
            # 要修改必须先删除再重新添加
            locked_archive = bool(existing.get("archive_all_history", False))
            refreshed = build_watched_symbol_record(
                normalized_symbol,
                sync_spot=sync_spot,
                sync_swap=sync_swap,
                archive_all_history=locked_archive,
                existing=existing,
            )
            config_changed = (
                bool(existing.get("sync_spot", True)) != bool(sync_spot)
                or bool(existing.get("sync_swap", True)) != bool(sync_swap)
            )
            if config_changed:
                refreshed["updated_at"] = _utc_now_iso()
                updated_records = list(records)
                updated_records[index] = refreshed
                if not save_watched_symbols(updated_records):
                    raise RuntimeError("更新关注币种失败")
            else:
                refreshed["updated_at"] = existing.get("updated_at") or refreshed["updated_at"]
            return refreshed, True

    record = build_watched_symbol_record(
        normalized_symbol,
        sync_spot=sync_spot,
        sync_swap=sync_swap,
        archive_all_history=archive_all_history,
    )
    if not save_watched_symbols([*records, record]):
        raise RuntimeError("保存关注币种失败")
    return record, False


def remove_watched_symbol(symbol: Any) -> Tuple[Optional[Dict[str, Any]], bool]:
    normalized_symbol = normalize_watched_symbol(symbol)
    if not normalized_symbol:
        return None, False

    records = load_watched_symbols()
    kept: List[Dict[str, Any]] = []
    removed_record: Optional[Dict[str, Any]] = None

    for record in records:
        if record["symbol"] == normalized_symbol and removed_record is None:
            removed_record = record
            continue
        kept.append(record)

    if removed_record is None:
        return None, False

    if not save_watched_symbols(kept):
        raise RuntimeError("删除关注币种失败")
    return removed_record, True


def list_watched_symbol_values() -> List[str]:
    return [record["symbol"] for record in load_watched_symbols()]
