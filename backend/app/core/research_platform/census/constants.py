from __future__ import annotations


INDEPENDENT_CENSUS_SOURCE_KIND = 'independent_census_runtime_v1'
LEGACY_CENSUS_SOURCE_KIND = 'legacy_session_coupled_v0'


def normalize_inst_ids(inst_ids) -> list[str]:
    """去重、去空白、保序地归一化品种 ID 列表。"""
    seen: set[str] = set()
    normalized: list[str] = []
    for inst_id in inst_ids or []:
        value = str(inst_id or '').strip()
        if not value or value in seen:
            continue
        seen.add(value)
        normalized.append(value)
    return normalized
