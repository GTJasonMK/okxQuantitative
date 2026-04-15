from __future__ import annotations

import math


def fit_strata_cutpoints(
    *,
    shift_states: list[dict[str, float]],
) -> dict[str, list[float]]:
    rv_values = [float(state['rv_2h_bps']) for state in shift_states]
    liquidity_values = [compute_liquidity_score(state) for state in shift_states]
    return {
        'rv_2h_bps': _tertile_cutpoints(rv_values),
        'liquidity_score': _tertile_cutpoints(liquidity_values),
    }


def compute_liquidity_score(shift_state: dict[str, float]) -> float:
    return float(shift_state['depth_10bps_log']) - math.log1p(
        max(float(shift_state['spread_median_60s_bps']), 0.0)
    )


def build_strata_v1(
    *,
    shift_state: dict[str, float],
    fit_cutpoints: dict[str, list[float]],
) -> dict[str, int]:
    slot_15m = int(shift_state['slot_15m'])
    return {
        'tod_bucket_6h': slot_15m // 24,
        'weekend_flag': int(shift_state['weekend_flag']),
        'rv_2h_bin_3': bucketize(
            float(shift_state['rv_2h_bps']),
            fit_cutpoints['rv_2h_bps'],
        ),
        'liquidity_bin_3': bucketize(
            compute_liquidity_score(shift_state),
            fit_cutpoints['liquidity_score'],
        ),
    }


def build_strata_key(strata: dict[str, int]) -> str:
    return ':'.join(str(value) for value in strata.values())


def bucketize(value: float, cutpoints: list[float]) -> int:
    if value <= cutpoints[0]:
        return 0
    if value <= cutpoints[1]:
        return 1
    return 2


def _tertile_cutpoints(values: list[float]) -> list[float]:
    ordered_values = sorted(float(value) for value in values)
    if not ordered_values:
        return [0.0, 0.0]
    first_index = min(len(ordered_values) - 1, len(ordered_values) // 3)
    second_index = min(len(ordered_values) - 1, (len(ordered_values) * 2) // 3)
    return [ordered_values[first_index], ordered_values[second_index]]
