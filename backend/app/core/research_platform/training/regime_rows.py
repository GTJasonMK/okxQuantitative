from __future__ import annotations


LOW_REALIZED_VOL_THRESHOLD_BPS = 50.0
HIGH_REALIZED_VOL_THRESHOLD_BPS = 100.0
WIDE_SPREAD_THRESHOLD_BPS = 0.1


def build_regime_row(row: dict[str, object]) -> dict[str, object]:
    return {
        'hour_of_day': int(row['hour_of_day']),
        'day_of_week': int(row['day_of_week']),
        'realized_vol_bin': _resolve_realized_vol_bin(float(row['realized_vol_proxy_2h'])),
        'spread_bin': 0 if float(row['spread_snapshot_bps']) < WIDE_SPREAD_THRESHOLD_BPS else 1,
        'liquidity_bin': int(row['liquidity_snapshot_bin']),
        'funding_regime': str(row['funding_regime']),
    }


def _resolve_realized_vol_bin(realized_vol_proxy_2h: float) -> int:
    if realized_vol_proxy_2h <= LOW_REALIZED_VOL_THRESHOLD_BPS:
        return 0
    if realized_vol_proxy_2h <= HIGH_REALIZED_VOL_THRESHOLD_BPS:
        return 1
    return 2
