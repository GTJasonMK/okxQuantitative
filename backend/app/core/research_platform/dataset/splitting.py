from __future__ import annotations


VALIDATION_FRACTION = 0.2
TEST_FRACTION = 0.2


def build_dataset_splits(
    *,
    labeled_rows: list[dict[str, object]],
    embargo_sec: int,
    sampling_stride_sec: int,
) -> dict[str, list[dict[str, object]]]:
    ordered = sorted(labeled_rows, key=lambda row: int(row['decision_ts']))
    if not ordered:
        return {'train': [], 'val': [], 'test': []}
    test_rows = _select_tail_block(ordered, fraction=TEST_FRACTION)
    test_start_ts = int(test_rows[0]['decision_ts'])
    validation_pool = [
        row for row in ordered
        if int(row['decision_ts']) < test_start_ts - int(embargo_sec)
    ]
    if not validation_pool:
        return {'train': [], 'val': [], 'test': test_rows}
    val_rows = _select_tail_block(validation_pool, fraction=VALIDATION_FRACTION)
    val_start_ts = int(val_rows[0]['decision_ts'])
    train_pool = [
        row for row in validation_pool
        if int(row['decision_ts']) < val_start_ts - int(embargo_sec)
    ]
    return {
        'train': _apply_stride(train_pool, sampling_stride_sec=sampling_stride_sec),
        'val': val_rows,
        'test': test_rows,
    }


def _select_tail_block(
    ordered: list[dict[str, object]],
    *,
    fraction: float,
) -> list[dict[str, object]]:
    block_size = max(1, int(len(ordered) * fraction))
    return ordered[-block_size:]


def _apply_stride(
    rows: list[dict[str, object]],
    *,
    sampling_stride_sec: int,
) -> list[dict[str, object]]:
    if not rows:
        return []
    stride = max(int(sampling_stride_sec), 1)
    selected: list[dict[str, object]] = []
    last_selected_ts: int | None = None
    for row in rows:
        decision_ts = int(row['decision_ts'])
        if last_selected_ts is None or decision_ts - last_selected_ts >= stride:
            selected.append(row)
            last_selected_ts = decision_ts
    return selected
