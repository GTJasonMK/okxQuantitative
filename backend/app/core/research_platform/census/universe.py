from __future__ import annotations

import re
from typing import Any

from app.utils.preferences_store import load_preferences


PREFERENCES_KEY = 'research_platform_census_settings'
DEFAULT_ENABLED = True
SWAP_PATTERN = re.compile(r'^[A-Z0-9]+-[A-Z0-9]+-SWAP$')


def load_census_universe_settings(cfg) -> dict[str, object]:
    defaults = build_default_census_universe_settings(cfg)
    payload = load_preferences().get(PREFERENCES_KEY)
    if not isinstance(payload, dict):
        return defaults
    return normalize_census_universe_settings(payload, defaults=defaults)


def build_default_census_universe_settings(cfg) -> dict[str, object]:
    return {
        'enabled': DEFAULT_ENABLED,
        'universe': [],
    }


def normalize_census_universe_settings(
    payload: dict[str, Any],
    *,
    defaults: dict[str, object],
) -> dict[str, object]:
    return {
        'enabled': _coerce_bool(payload.get('enabled'), default=bool(defaults['enabled'])),
        'universe': _normalize_universe(payload.get('universe', defaults['universe'])),
    }


class PreferenceBackedCensusUniverseProvider:
    def __init__(self, *, cfg, settings_loader=load_census_universe_settings):
        self._cfg = cfg
        self._settings_loader = settings_loader

    def list_inst_ids(self) -> list[str]:
        settings = self._settings_loader(self._cfg)
        if not settings.get('enabled', DEFAULT_ENABLED):
            return []
        return list(settings.get('universe', []))


def _normalize_universe(raw: Any) -> list[str]:
    items = _coerce_items(raw)
    cleaned: list[str] = []
    seen: set[str] = set()
    for item in items:
        inst_id = str(item or '').strip().upper()
        if not inst_id or inst_id in seen:
            continue
        if not SWAP_PATTERN.match(inst_id):
            raise ValueError(f'非法永续合约: {inst_id}')
        seen.add(inst_id)
        cleaned.append(inst_id)
    return cleaned


def _coerce_items(raw: Any) -> list[object]:
    if isinstance(raw, str):
        return raw.replace(',', '\n').splitlines()
    if isinstance(raw, list):
        return raw
    if raw is None:
        return []
    raise ValueError('census universe 格式无效')


def _coerce_bool(value: Any, *, default: bool) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in {'true', '1', 'yes', 'on'}:
            return True
        if lowered in {'false', '0', 'no', 'off'}:
            return False
    return bool(value)
