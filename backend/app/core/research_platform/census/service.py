from __future__ import annotations

import json
import math
from datetime import datetime, timezone

from app.core.research_platform.dataset.shift_state import SHIFT_STATE_FIELDS_V1
from app.core.research_platform.dataset.shift_state import validate_shift_state_schema
from app.core.research_platform.dataset.row_validity import row_is_strictly_valid

from app.core.data_center_collection.integrity_policy import get_integrity_policy

from .constants import INDEPENDENT_CENSUS_SOURCE_KIND


LOOKBACK_SECONDS = 7200
SHORT_WINDOW_SECONDS = 900
STALE_WINDOW_SECONDS = 60
FUNDING_INTERVAL_SECONDS = 8 * 3600
NEAR_FUNDING_MINUTES = 60


class ResearchCensusService:
    def __init__(self, *, storage, observation_reader, session_activity_provider):
        self._storage = storage
        self._observation_reader = observation_reader
        self._session_activity_provider = session_activity_provider
        self.enabled = True
        self.last_decision_ts: int | None = None

    async def start(self) -> None:
        return None

    async def stop(self) -> None:
        return None

    async def run_once(self, *, inst_id: str, decision_ts: int) -> dict[str, object]:
        rows = self._observation_reader.list_for_inst(
            inst_id,
            end_ts=decision_ts,
            lookback_sec=LOOKBACK_SECONDS,
        )
        session_active_flag = self._session_activity_provider.is_active(inst_id, decision_ts)
        shift_state = build_compact_boundary_state_v1(
            rows=rows,
            decision_ts=decision_ts,
            session_active_flag=session_active_flag,
        )
        row = build_target_census_row(
            inst_id=inst_id,
            decision_ts=decision_ts,
            shift_state=shift_state,
            observation_source_kind=INDEPENDENT_CENSUS_SOURCE_KIND,
        )
        self._storage.save_research_target_census(**row)
        self.last_decision_ts = int(decision_ts)
        return row


def build_compact_boundary_state_v1(
    *,
    rows: list[dict[str, object]],
    decision_ts: int,
    session_active_flag: bool,
) -> dict[str, object]:
    policy = _resolve_integrity_policy(rows)
    window_validity = _check_observation_window(rows=rows, decision_ts=decision_ts)
    short_rows = [row for row in rows if int(row['second_bucket']) >= decision_ts - SHORT_WINDOW_SECONDS]
    stale_rows = [row for row in rows if int(row['second_bucket']) >= decision_ts - STALE_WINDOW_SECONDS]
    latest = rows[-1] if rows else None
    latest_close = _get_float(latest, 'close_price')
    short_close = _get_float(short_rows[0], 'close_price') if short_rows else latest_close
    long_close = _get_float(rows[0], 'close_price') if rows else latest_close
    bid_depth = _get_float(latest, 'bid_depth_10bps')
    ask_depth = _get_float(latest, 'ask_depth_10bps')
    depth_total = bid_depth + ask_depth
    funding_countdown_min = _funding_countdown_minutes(decision_ts)
    book_stale_ratio = _stale_ratio(
        stale_rows,
        'book_age_seconds',
        threshold=float(policy['book_stale_threshold_sec']),
    )
    state_stale_ratio = _stale_ratio(
        stale_rows,
        'state_age_seconds',
        threshold=float(policy['state_stale_threshold_sec']),
    )
    source_health_flag = 1 if latest and book_stale_ratio == 0.0 and state_stale_ratio == 0.0 else 0
    return {
        'slot_15m': int((decision_ts % 86400) // SHORT_WINDOW_SECONDS),
        'weekend_flag': 1 if datetime.fromtimestamp(decision_ts, tz=timezone.utc).weekday() >= 5 else 0,
        'ret_15m_bps': _log_return_bps(short_close, latest_close),
        'ret_2h_bps': _log_return_bps(long_close, latest_close),
        'rv_15m_bps': _realized_vol_bps(short_rows),
        'rv_2h_bps': _realized_vol_bps(rows),
        'range_15m_bps': _range_bps(short_rows),
        'range_2h_bps': _range_bps(rows),
        'spread_last_bps': _get_float(latest, 'spread_bps'),
        'spread_median_60s_bps': _median([_get_float(row, 'spread_bps') for row in stale_rows]),
        'depth_10bps_log': math.log1p(max(depth_total, 0.0)),
        'imbalance_10bps': _resolve_depth_imbalance(bid_depth=bid_depth, ask_depth=ask_depth),
        'trade_count_60s': int(sum(_get_float(row, 'trade_count') for row in stale_rows)),
        'trade_notional_60s_log': math.log1p(sum(_total_trade_notional(row) for row in stale_rows)),
        'funding_countdown_min': funding_countdown_min,
        'near_funding_flag': 1 if funding_countdown_min <= NEAR_FUNDING_MINUTES else 0,
        'book_stale_ratio_60s': book_stale_ratio,
        'state_stale_ratio_60s': state_stale_ratio,
        'source_health_flag': source_health_flag,
        'session_active_flag': 1 if session_active_flag else 0,
        '_window_2h_complete': window_validity['window_2h_complete'],
        '_window_15m_complete': window_validity['window_15m_complete'],
        '_window_invalid_reason': window_validity['invalid_reason'],
    }


def build_target_census_row(
    *,
    inst_id: str,
    decision_ts: int,
    shift_state: dict[str, object],
    observation_source_kind: str = INDEPENDENT_CENSUS_SOURCE_KIND,
) -> dict[str, object]:
    funding_regime = 'neutral'
    if shift_state['near_funding_flag']:
        funding_regime = 'near_funding'
    window_2h_complete = bool(shift_state.get('_window_2h_complete', False))
    window_15m_complete = bool(shift_state.get('_window_15m_complete', False))
    window_invalid_reason = str(shift_state.get('_window_invalid_reason', ''))
    source_healthy = bool(shift_state['source_health_flag'])
    eligible = source_healthy and window_2h_complete and window_15m_complete
    deployment_eligible = 1 if eligible else 0
    invalid_reasons: list[str] = []
    if not source_healthy:
        invalid_reasons.append('source_unhealthy')
    if window_invalid_reason:
        invalid_reasons.append(window_invalid_reason)
    invalid_reason = ';'.join(invalid_reasons)
    return {
        'census_id': f'{inst_id}:{decision_ts}',
        'inst_id': inst_id,
        'decision_ts': int(decision_ts),
        'deployment_eligible': deployment_eligible,
        'census_policy_version': 'deployment_eligible_boundary_census_v1',
        'shift_state_definition_version': 'compact_boundary_state_v1',
        'shift_state_blob_json': json.dumps(
            _strip_internal_keys(shift_state), ensure_ascii=False, sort_keys=True,
        ),
        'hour_of_day': int(datetime.fromtimestamp(decision_ts, tz=timezone.utc).hour),
        'day_of_week': int(datetime.fromtimestamp(decision_ts, tz=timezone.utc).weekday()),
        'realized_vol_proxy_2h': float(shift_state['rv_2h_bps']),
        'spread_snapshot_bps': float(shift_state['spread_last_bps']),
        'liquidity_snapshot_bin': _liquidity_bin(float(shift_state['depth_10bps_log'])),
        'funding_regime': funding_regime,
        'session_active_flag': int(shift_state['session_active_flag']),
        'source_health_flag': int(shift_state['source_health_flag']),
        'invalid_reason': invalid_reason,
        'observation_source_kind': observation_source_kind,
    }


def _get_float(row: dict[str, object] | None, key: str) -> float:
    if row is None:
        return 0.0
    return float(row.get(key, 0.0) or 0.0)


def _check_observation_window(
    *,
    rows: list[dict[str, object]],
    decision_ts: int,
) -> dict[str, object]:
    """校验 [t-7200, t) 和 [t-900, t) 观测窗口的连续完整性和严格秒条有效性。

    除了要求桶连续存在外，还要求每一秒都满足 integrity policy
    的严格有效性（is_valid_second=1、required fields、stale、clock skew）。
    """
    if not rows:
        return {
            'window_2h_complete': False,
            'window_15m_complete': False,
            'invalid_reason': 'observation_window_empty',
        }
    row_map = {int(row['second_bucket']): row for row in rows}
    expected_2h = set(range(decision_ts - LOOKBACK_SECONDS, decision_ts))
    expected_15m = set(range(decision_ts - SHORT_WINDOW_SECONDS, decision_ts))
    present_2h = expected_2h & set(row_map.keys())
    present_15m = expected_15m & set(row_map.keys())
    missing_2h = expected_2h - present_2h
    missing_15m = expected_15m - present_15m
    invalid_2h = {
        bucket for bucket in present_2h
        if not row_is_strictly_valid(row_map[bucket])
    }
    invalid_15m = {
        bucket for bucket in present_15m
        if not row_is_strictly_valid(row_map[bucket])
    }
    window_2h_complete = not missing_2h and not invalid_2h
    window_15m_complete = not missing_15m and not invalid_15m
    if window_2h_complete and window_15m_complete:
        return {
            'window_2h_complete': True,
            'window_15m_complete': True,
            'invalid_reason': '',
        }
    reasons: list[str] = []
    if missing_2h:
        reasons.append(f'observation_window_2h_incomplete:{len(missing_2h)}_missing')
    if invalid_2h:
        reasons.append(f'observation_window_2h_integrity_failures:{len(invalid_2h)}_invalid')
    if missing_15m:
        reasons.append(f'observation_window_15m_incomplete:{len(missing_15m)}_missing')
    if invalid_15m:
        reasons.append(f'observation_window_15m_integrity_failures:{len(invalid_15m)}_invalid')
    return {
        'window_2h_complete': window_2h_complete,
        'window_15m_complete': window_15m_complete,
        'invalid_reason': ';'.join(reasons),
    }


def _strip_internal_keys(shift_state: dict[str, object]) -> dict[str, object]:
    """移除以 _ 开头的内部键，并校验剩余字段精确匹配 SHIFT_STATE_FIELDS_V1。"""
    public = {key: value for key, value in shift_state.items() if not key.startswith('_')}
    validate_shift_state_schema(public)
    return public


def _log_return_bps(start_value: float, end_value: float) -> float:
    if start_value <= 0.0 or end_value <= 0.0:
        return 0.0
    return math.log(end_value / start_value) * 1e4


def _realized_vol_bps(rows: list[dict[str, object]]) -> float:
    if len(rows) < 2:
        return 0.0
    returns = [
        _log_return_bps(_get_float(rows[idx - 1], 'close_price'), _get_float(rows[idx], 'close_price')) / 1e4
        for idx in range(1, len(rows))
    ]
    return math.sqrt(sum(value * value for value in returns)) * 1e4


def _range_bps(rows: list[dict[str, object]]) -> float:
    if not rows:
        return 0.0
    high_value = max(_get_float(row, 'high_price') for row in rows)
    low_value = min(_get_float(row, 'low_price') for row in rows)
    return _log_return_bps(low_value, high_value)


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2 == 1:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


def _resolve_depth_imbalance(*, bid_depth: float, ask_depth: float) -> float:
    total_depth = bid_depth + ask_depth
    if total_depth <= 0.0:
        return 0.0
    return (bid_depth - ask_depth) / total_depth


def _stale_ratio(
    rows: list[dict[str, object]],
    key: str,
    *,
    threshold: float,
) -> float:
    if not rows:
        return 1.0
    stale_count = sum(1 for row in rows if _get_float(row, key) > threshold)
    return stale_count / len(rows)


def _total_trade_notional(row: dict[str, object]) -> float:
    return _get_float(row, 'buy_notional') + _get_float(row, 'sell_notional')


def _resolve_integrity_policy(rows: list[dict[str, object]]) -> dict[str, object]:
    if not rows:
        return get_integrity_policy('strict_v1')
    return get_integrity_policy(str(rows[-1].get('integrity_policy_version', 'strict_v1')))


def _funding_countdown_minutes(decision_ts: int) -> int:
    seconds_since_boundary = int(decision_ts % FUNDING_INTERVAL_SECONDS)
    remaining_seconds = FUNDING_INTERVAL_SECONDS - seconds_since_boundary
    return max(int(remaining_seconds // 60), 0)


def _liquidity_bin(depth_log: float) -> int:
    if depth_log < 2.0:
        return 0
    if depth_log < 3.0:
        return 1
    return 2
