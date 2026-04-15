from __future__ import annotations

import math

import numpy as np


REQUIRED_WINDOW_SECONDS = 7200
SUMMARY_WINDOWS = (60, 300, 900, 3600, REQUIRED_WINDOW_SECONDS)
FEATURE_FIELDS = (
    'close_price',
    'high_price',
    'low_price',
    'spread_bps',
    'trade_count',
    'signed_trade_notional',
    'multi_level_book_imbalance',
    'basis_bps',
    'oi_delta',
    'book_age_seconds',
    'state_age_seconds',
)


def build_feature_dataset(*, storage, rows: list[dict[str, object]]) -> dict[str, object]:
    tensors = [load_feature_tensor(storage=storage, row=row) for row in rows]
    matrix = np.vstack([summarize_feature_tensor(tensor['values']) for tensor in tensors])
    return {
        'matrix': matrix,
        'tensors': tensors,
        'feature_fields': list(FEATURE_FIELDS),
        'summary_feature_count': int(matrix.shape[1]),
    }


def load_feature_tensor(*, storage, row: dict[str, object]) -> dict[str, object]:
    decision_ts = int(row['decision_ts'])
    start_ts = decision_ts - REQUIRED_WINDOW_SECONDS
    window_rows = _load_window_rows(
        storage=storage,
        inst_id=str(row['inst_id']),
        session_id=str(row['session_id']),
        decision_ts=decision_ts,
    )
    if not _is_complete_window(window_rows=window_rows, start_ts=start_ts):
        raise ValueError(f"missing second_state window for sample {row['session_id']}:{decision_ts}")
    return {
        'decision_ts': decision_ts,
        'window_shape': [REQUIRED_WINDOW_SECONDS, len(FEATURE_FIELDS)],
        'values': np.asarray(
            [
                [float(window_row[field_name]) for field_name in FEATURE_FIELDS]
                for window_row in window_rows
            ],
            dtype=float,
        ),
    }


def summarize_feature_tensor(tensor: np.ndarray) -> np.ndarray:
    close_price = tensor[:, 0]
    high_price = tensor[:, 1]
    low_price = tensor[:, 2]
    spread_bps = tensor[:, 3]
    trade_count = tensor[:, 4]
    signed_notional = tensor[:, 5]
    imbalance = tensor[:, 6]
    basis_bps = tensor[:, 7]
    oi_delta = tensor[:, 8]
    book_age = tensor[:, 9]
    state_age = tensor[:, 10]
    values: list[float] = []
    for window in SUMMARY_WINDOWS:
        values.extend(
            _summarize_window(
                close_price=close_price[-window:],
                high_price=high_price[-window:],
                low_price=low_price[-window:],
                spread_bps=spread_bps[-window:],
                trade_count=trade_count[-window:],
                signed_notional=signed_notional[-window:],
                imbalance=imbalance[-window:],
                basis_bps=basis_bps[-window:],
            )
        )
    values.extend(
        (
            float(np.mean(oi_delta[-60:])),
            float(np.mean(book_age[-60:])),
            float(np.mean(state_age[-60:])),
        )
    )
    return np.asarray(values, dtype=float)


def _load_window_rows(*, storage, inst_id: str, session_id: str, decision_ts: int) -> list[dict[str, object]]:
    rows = storage.list_research_second_states_for_inst(
        inst_id,
        end_ts=decision_ts,
        lookback_sec=REQUIRED_WINDOW_SECONDS,
    )
    return [row for row in rows if str(row['session_id']) == session_id]


def _is_complete_window(*, window_rows: list[dict[str, object]], start_ts: int) -> bool:
    if len(window_rows) != REQUIRED_WINDOW_SECONDS:
        return False
    for offset, row in enumerate(window_rows):
        if int(row['second_bucket']) != start_ts + offset:
            return False
    return True


def _summarize_window(
    *,
    close_price: np.ndarray,
    high_price: np.ndarray,
    low_price: np.ndarray,
    spread_bps: np.ndarray,
    trade_count: np.ndarray,
    signed_notional: np.ndarray,
    imbalance: np.ndarray,
    basis_bps: np.ndarray,
) -> tuple[float, ...]:
    return (
        _log_return_bps(close_price[0], close_price[-1]),
        _realized_vol_bps(close_price),
        _range_bps(high_price, low_price),
        float(np.mean(spread_bps)),
        float(np.mean(trade_count)),
        float(np.mean(signed_notional)),
        float(np.mean(imbalance)),
        float(np.mean(basis_bps)),
    )


def _log_return_bps(start_value: float, end_value: float) -> float:
    if start_value <= 0.0 or end_value <= 0.0:
        return 0.0
    return math.log(end_value / start_value) * 1e4


def _realized_vol_bps(close_price: np.ndarray) -> float:
    if close_price.size < 2:
        return 0.0
    clipped = np.clip(close_price, a_min=1e-9, a_max=None)
    returns = np.diff(np.log(clipped))
    return float(np.sqrt(np.sum(returns * returns)) * 1e4)


def _range_bps(high_price: np.ndarray, low_price: np.ndarray) -> float:
    high_value = float(np.max(high_price))
    low_value = float(np.min(low_price))
    if low_value <= 0.0 or high_value <= 0.0:
        return 0.0
    return math.log(high_value / low_value) * 1e4
