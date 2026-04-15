from __future__ import annotations

from app.core.research_platform.training.weighting import build_density_ratio_feature_row

from .shift_state import parse_shift_state_blob
from .strata import build_strata_key
from .strata import build_strata_v1


def select_fit_rows(
    rows: list[dict[str, object]],
    *,
    split_row: dict[str, object],
) -> list[dict[str, object]]:
    start_ts = int(split_row['pre_origin_fit_start_ts'])
    end_ts = int(split_row['pre_origin_fit_end_ts'])
    return [
        row
        for row in rows
        if start_ts <= int(row['decision_ts']) <= end_ts
    ]


def select_origin_census_rows(
    rows: list[dict[str, object]],
    *,
    split_row: dict[str, object],
) -> list[dict[str, object]]:
    cutoff_ts = int(split_row['census_window_end_ts'])
    return [
        row
        for row in rows
        if int(row['decision_ts']) <= cutoff_ts
    ]


def build_strata_key_from_row(
    row: dict[str, object],
    *,
    fit_cutpoints: dict[str, list[float]],
) -> str:
    return build_strata_key(build_strata_v1(shift_state=row['shift_state'], fit_cutpoints=fit_cutpoints))


def build_strata_key_from_census(
    row: dict[str, object],
    *,
    fit_cutpoints: dict[str, list[float]],
) -> str:
    shift_state = parse_shift_state_blob(row)
    return build_strata_key(build_strata_v1(shift_state=shift_state, fit_cutpoints=fit_cutpoints))


def build_classifier_rows(
    *,
    origin_ts: int,
    fit_rows: list[dict[str, object]],
    census_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    rows = [_build_classifier_row(origin_ts=origin_ts, row=row, domain_label=0) for row in fit_rows]
    rows.extend(_build_classifier_row(origin_ts=origin_ts, row=row, domain_label=1) for row in census_rows)
    return rows


def _build_classifier_row(
    *,
    origin_ts: int,
    row: dict[str, object],
    domain_label: int,
) -> dict[str, object]:
    shift_state = row['shift_state'] if 'shift_state' in row else parse_shift_state_blob(row)
    decision_ts = int(row['decision_ts'])
    return {
        'origin_ts': origin_ts,
        'decision_ts': decision_ts,
        'session_id': str(row.get('session_id', f'census-{decision_ts}')),
        'domain_label': domain_label,
        **build_density_ratio_feature_row(shift_state=shift_state),
    }
