from __future__ import annotations

from .row_validity import row_is_strictly_valid


def rows_cover_window(
    *,
    rows: list[dict[str, object]],
    start_ts: int,
    end_ts: int,
    session_id: str,
    inst_id: str,
) -> bool:
    if not rows or end_ts <= start_ts:
        return False
    if not _rows_match_identity(rows=rows, session_id=session_id, inst_id=inst_id):
        return False
    if not _rows_are_contiguous(rows=rows, start_ts=start_ts, end_ts=end_ts):
        return False
    return all(row_is_strictly_valid(row) for row in rows)


def _rows_match_identity(
    *,
    rows: list[dict[str, object]],
    session_id: str,
    inst_id: str,
) -> bool:
    return all(
        str(row['session_id']) == session_id and str(row['inst_id']) == inst_id
        for row in rows
    )


def _rows_are_contiguous(
    *,
    rows: list[dict[str, object]],
    start_ts: int,
    end_ts: int,
) -> bool:
    expected_count = end_ts - start_ts
    second_buckets = [int(row['second_bucket']) for row in rows]
    if len(second_buckets) != expected_count:
        return False
    if second_buckets[0] != start_ts or second_buckets[-1] != end_ts - 1:
        return False
    return all(
        second_buckets[index] - second_buckets[index - 1] == 1
        for index in range(1, len(second_buckets))
    )
