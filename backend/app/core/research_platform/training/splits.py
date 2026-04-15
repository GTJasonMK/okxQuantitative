from __future__ import annotations

from app.core.research_platform.protocol_versions import OUTER_ORIGIN_SELECTION_POLICY


BOUNDARY_SECONDS = 900
MAX_OUTER_ORIGIN_COUNT = 4


def build_blocked_temporal_hv_v1(
    *,
    decision_ts: list[int],
    embargo_sec: int,
    outer_origin_count: int,
) -> list[dict[str, object]]:
    ordered = sorted({int(ts) for ts in decision_ts})
    outer_test_blocks = _choose_outer_test_blocks(
        ordered,
        embargo_sec=embargo_sec,
        outer_origin_count=outer_origin_count,
    )
    return [
        _build_outer_split(
            ordered=ordered,
            test_block=test_block,
            embargo_sec=embargo_sec,
            block_index=block_index,
        )
        for block_index, test_block in enumerate(outer_test_blocks)
    ]


def count_outer_origin_candidates(
    *,
    decision_ts: list[int],
    embargo_sec: int,
) -> int:
    ordered = sorted({int(ts) for ts in decision_ts})
    if len(ordered) < 2:
        return 0
    candidates = _select_outer_test_candidates(ordered, embargo_sec=embargo_sec)
    if candidates:
        return min(MAX_OUTER_ORIGIN_COUNT, len(candidates))
    return min(MAX_OUTER_ORIGIN_COUNT, len(ordered) - 1)


def _choose_outer_test_blocks(
    ordered: list[int],
    *,
    embargo_sec: int,
    outer_origin_count: int,
) -> list[list[int]]:
    if len(ordered) < 2:
        return []
    candidates = _select_outer_test_candidates(ordered, embargo_sec=embargo_sec)
    if candidates:
        return _partition_contiguous_blocks(candidates, block_count=outer_origin_count)
    return _build_trailing_singleton_blocks(ordered, block_count=outer_origin_count)


def _select_outer_test_candidates(ordered: list[int], *, embargo_sec: int) -> list[int]:
    earliest_full_context_ts = ordered[0] + ((2 * embargo_sec) - BOUNDARY_SECONDS)
    return [
        ts
        for ts in ordered[1:]
        if ts >= earliest_full_context_ts
    ]


def _build_outer_split(
    *,
    ordered: list[int],
    test_block: list[int],
    embargo_sec: int,
    block_index: int,
) -> dict[str, object]:
    origin_ts = test_block[0]
    pre_origin_ts = [ts for ts in ordered if ts < origin_ts]
    validation_start_ts = origin_ts - (2 * embargo_sec) + BOUNDARY_SECONDS
    validation_end_ts = origin_ts - embargo_sec
    pre_origin_fit_end_ts = origin_ts - BOUNDARY_SECONDS
    return {
        'origin_ts': origin_ts,
        'train_start_ts': pre_origin_ts[0],
        'train_end_ts': validation_start_ts - embargo_sec,
        'validation_start_ts': validation_start_ts,
        'validation_end_ts': validation_end_ts,
        'pre_origin_fit_start_ts': pre_origin_ts[0],
        'pre_origin_fit_end_ts': pre_origin_fit_end_ts,
        'test_block_index': block_index,
        'test_start_ts': origin_ts,
        'test_end_ts': test_block[-1],
        'test_block_sample_count': len(test_block),
        'census_window_end_ts': pre_origin_fit_end_ts,
        'inner_validation_folds': build_inner_blocked_validation_schedule(
            pre_origin_ts=pre_origin_ts,
            origin_ts=origin_ts,
            embargo_sec=embargo_sec,
            inner_fold_count=3,
        ),
    }


def build_inner_blocked_validation_schedule(
    *,
    pre_origin_ts: list[int],
    origin_ts: int,
    embargo_sec: int,
    inner_fold_count: int,
) -> list[dict[str, int]]:
    blocks = _partition_temporal_blocks(pre_origin_ts, block_count=inner_fold_count)
    schedule: list[dict[str, int]] = []
    for fold_index, validation_block in enumerate(blocks):
        validation_start_ts = validation_block[0]
        validation_end_ts = validation_block[-1]
        schedule.append(
            {
                'fold_id': f'{origin_ts}:inner:{fold_index}',
                'origin_ts': origin_ts,
                'train_start_ts': pre_origin_ts[0],
                'train_end_ts': validation_start_ts - embargo_sec,
                'validation_start_ts': validation_start_ts,
                'validation_end_ts': validation_end_ts,
                'embargo_sec': embargo_sec,
            }
        )
    return schedule


def _partition_temporal_blocks(pre_origin_ts: list[int], *, block_count: int) -> list[list[int]]:
    effective_count = max(2, min(int(block_count), len(pre_origin_ts)))
    block_size = max(1, len(pre_origin_ts) // effective_count)
    blocks = [
        pre_origin_ts[index:index + block_size]
        for index in range(0, len(pre_origin_ts), block_size)
    ]
    return [block for block in blocks if block]


def _partition_contiguous_blocks(values: list[int], *, block_count: int) -> list[list[int]]:
    effective_count = max(1, min(int(block_count), len(values)))
    base_size = len(values) // effective_count
    remainder = len(values) % effective_count
    blocks: list[list[int]] = []
    start_index = 0
    for block_index in range(effective_count):
        block_size = base_size + (1 if block_index < remainder else 0)
        end_index = start_index + block_size
        blocks.append(values[start_index:end_index])
        start_index = end_index
    return [block for block in blocks if block]


def _build_trailing_singleton_blocks(ordered: list[int], *, block_count: int) -> list[list[int]]:
    effective_count = max(1, min(int(block_count), len(ordered) - 1))
    return [[ts] for ts in ordered[-effective_count:]]
