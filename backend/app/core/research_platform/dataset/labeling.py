from __future__ import annotations

import math

from .constants import LABEL_WINDOW_SECONDS_15M
from .models import BoundaryTarget15m
from .windowing import rows_cover_window


def build_boundary_target_15m(
    *,
    session_id: str,
    inst_id: str,
    decision_ts: int,
    input_rows: list[dict[str, object]],
    label_rows: list[dict[str, object]],
    label_definition_version: str,
) -> BoundaryTarget15m:
    anchor_row = _read_anchor_row(input_rows=input_rows, decision_ts=decision_ts)
    label_complete = rows_cover_window(
        rows=label_rows,
        start_ts=decision_ts,
        end_ts=decision_ts + LABEL_WINDOW_SECONDS_15M,
        session_id=session_id,
        inst_id=inst_id,
    )
    prices = _read_label_prices(label_rows)
    return BoundaryTarget15m(
        target_id=f'{session_id}:{decision_ts}',
        session_id=session_id,
        inst_id=inst_id,
        decision_ts=decision_ts,
        anchor_second_bucket=int(anchor_row['second_bucket']),
        anchor_close_price=float(anchor_row['close_price']),
        label_start_ts=decision_ts,
        label_end_ts=decision_ts + LABEL_WINDOW_SECONDS_15M,
        open_price=prices['open_price'],
        high_price=prices['high_price'],
        low_price=prices['low_price'],
        close_price=prices['close_price'],
        r_open=math.log(prices['open_price'] / float(anchor_row['close_price'])),
        r_close=math.log(prices['close_price'] / float(anchor_row['close_price'])),
        u=math.log(prices['high_price'] / max(prices['open_price'], prices['close_price'])),
        d=math.log(min(prices['open_price'], prices['close_price']) / prices['low_price']),
        label_complete=label_complete,
        invalid_reason='' if label_complete else 'label_seconds_missing',
        label_definition_version=label_definition_version,
    )


def _read_anchor_row(
    *,
    input_rows: list[dict[str, object]],
    decision_ts: int,
) -> dict[str, object]:
    if not input_rows:
        raise ValueError('input_rows must contain the anchor second')
    anchor_row = input_rows[-1]
    if int(anchor_row['second_bucket']) != decision_ts - 1:
        raise ValueError('input_rows must end at decision_ts - 1')
    return anchor_row


def _read_label_prices(label_rows: list[dict[str, object]]) -> dict[str, float]:
    if not label_rows:
        raise ValueError('label_rows must not be empty')
    return {
        'open_price': float(label_rows[0]['open_price']),
        'high_price': max(float(row['high_price']) for row in label_rows),
        'low_price': min(float(row['low_price']) for row in label_rows),
        'close_price': float(label_rows[-1]['close_price']),
    }
