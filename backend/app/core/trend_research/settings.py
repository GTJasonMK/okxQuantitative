from __future__ import annotations

import re
from typing import Any, Dict

from ...utils.preferences_store import load_preferences, merge_preferences


PREFERENCES_KEY = "trend_research_settings"
DEFAULT_BOOK_CHANNEL = "books5"
MIN_FEATURE_BAR_SECONDS = 1
MIN_STATE_SYNC_SECONDS = 5
SWAP_PATTERN = re.compile(r"^[A-Z0-9]+-[A-Z0-9]+-SWAP$")


def build_default_trend_research_settings(cfg) -> Dict[str, Any]:
    return {
        "enabled": bool(cfg.enabled),
        "whitelist": list(cfg.whitelist),
        "feature_bar_seconds": max(int(cfg.feature_bar_seconds or 1), MIN_FEATURE_BAR_SECONDS),
        "state_sync_seconds": max(int(cfg.state_sync_seconds or 30), MIN_STATE_SYNC_SECONDS),
        "book_channel": str(cfg.book_channel or DEFAULT_BOOK_CHANNEL).strip() or DEFAULT_BOOK_CHANNEL,
    }


def _parse_whitelist(raw: Any) -> list[str]:
    if isinstance(raw, str):
        items = raw.replace(",", "\n").splitlines()
    elif isinstance(raw, list):
        items = raw
    elif raw is None:
        items = []
    else:
        raise ValueError("趋势研究白名单格式无效")

    cleaned = []
    invalid = []
    seen = set()
    for item in items:
        symbol = str(item or "").strip().upper()
        if not symbol:
            continue
        if not SWAP_PATTERN.match(symbol):
            invalid.append(symbol)
            continue
        if symbol in seen:
            continue
        seen.add(symbol)
        cleaned.append(symbol)
    if invalid:
        raise ValueError(f"非法永续合约: {', '.join(invalid)}")
    return cleaned


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {"true", "1", "yes", "on"}:
            return True
        if lowered in {"false", "0", "no", "off"}:
            return False
    return bool(value)


def normalize_trend_research_settings(payload: Dict[str, Any] | None, *, defaults: Dict[str, Any]) -> Dict[str, Any]:
    payload = payload or {}
    return {
        "enabled": _coerce_bool(payload.get("enabled"), default=bool(defaults["enabled"])),
        "whitelist": _parse_whitelist(payload.get("whitelist", defaults["whitelist"])),
        "feature_bar_seconds": max(
            int(payload.get("feature_bar_seconds", defaults["feature_bar_seconds"]) or defaults["feature_bar_seconds"]),
            MIN_FEATURE_BAR_SECONDS,
        ),
        "state_sync_seconds": max(
            int(payload.get("state_sync_seconds", defaults["state_sync_seconds"]) or defaults["state_sync_seconds"]),
            MIN_STATE_SYNC_SECONDS,
        ),
        "book_channel": str(payload.get("book_channel", defaults["book_channel"]) or defaults["book_channel"]).strip() or DEFAULT_BOOK_CHANNEL,
    }


def load_trend_research_settings(cfg) -> Dict[str, Any]:
    defaults = build_default_trend_research_settings(cfg)
    payload = load_preferences()
    settings = payload.get(PREFERENCES_KEY)
    if not isinstance(settings, dict):
        return defaults
    return normalize_trend_research_settings(settings, defaults=defaults)


def save_trend_research_settings(settings: Dict[str, Any], *, cfg) -> Dict[str, Any]:
    defaults = build_default_trend_research_settings(cfg)
    normalized = normalize_trend_research_settings(settings, defaults=defaults)
    if not merge_preferences({PREFERENCES_KEY: normalized}):
        raise RuntimeError("保存趋势研究配置失败")
    return normalized
