from __future__ import annotations

from .shift_state import parse_shift_state_blob
from .strata import fit_strata_cutpoints

EMPTY_SHIFT_STATE = {
    'slot_15m': 0.0,
    'weekend_flag': 0.0,
    'rv_2h_bps': 0.0,
    'spread_median_60s_bps': 0.0,
    'depth_10bps_log': 0.0,
}


def fit_census_strata_cutpoints(census_rows: list[dict[str, object]]) -> dict[str, list[float]]:
    return fit_strata_cutpoints(shift_states=collect_census_shift_states(census_rows))


def collect_census_shift_states(census_rows: list[dict[str, object]]) -> list[dict[str, float]]:
    states = [parse_shift_state_blob(row) for row in census_rows]
    return states or [dict(EMPTY_SHIFT_STATE)]
