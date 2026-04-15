from __future__ import annotations

import numpy as np

from .shift_state import SHIFT_STATE_FIELDS_V1
from .shift_state import parse_shift_state_blob


PROPENSITY_METHOD = 'blocked_temporal_logistic_auc_v1'
PROPENSITY_SPLIT_VERSION = 'domainwise_session_temporal_two_fold_v1'
PROPENSITY_MIN_SAMPLE_COUNT = 2
PROPENSITY_EXCESS_AUC_THRESHOLD = 0.10
PROPENSITY_EPOCHS = 200
PROPENSITY_LEARNING_RATE = 0.05
PROPENSITY_L2_REGULARIZATION = 0.01
PROPENSITY_LOGIT_CLIP = 40.0
PROPENSITY_EMBARGO_SECONDS = 8100
ROBUST_SCALE_FLOOR = 1e-6


def run_propensity_check(
    *,
    labeled_shift_rows: list[dict[str, object]],
    census_shift_rows: list[dict[str, object]],
) -> dict[str, object]:
    source_rows = sorted(labeled_shift_rows, key=lambda row: int(row['decision_ts']))
    target_rows = sorted(census_shift_rows, key=lambda row: int(row['decision_ts']))
    if min(len(source_rows), len(target_rows)) < PROPENSITY_MIN_SAMPLE_COUNT:
        return _build_failed_propensity_result(reason='insufficient_samples')
    source_folds = _split_domain_folds(source_rows, domain_prefix='source')
    target_folds = _split_domain_folds(target_rows, domain_prefix='target')
    if any(not fold['rows'] for fold in source_folds + target_folds):
        return _build_failed_propensity_result(reason='insufficient_fold_coverage')
    oof_scores: list[float] = []
    oof_labels: list[int] = []
    folds = []
    for holdout_index in range(2):
        fold_summary = _build_fold_summary(
            holdout_index=holdout_index,
            source_folds=source_folds,
            target_folds=target_folds,
        )
        train_rows, train_labels = _merge_domain_folds(
            source_folds,
            target_folds,
            include_fold=1 - holdout_index,
        )
        eval_rows, eval_labels = _merge_domain_folds(
            source_folds,
            target_folds,
            include_fold=holdout_index,
        )
        if not _fold_is_outside_embargo(fold_summary=fold_summary):
            return _build_failed_propensity_result(reason='insufficient_temporal_separation')
        probabilities = _fit_and_score_logistic_oof(
            train_rows=train_rows,
            train_labels=train_labels,
            eval_rows=eval_rows,
        )
        oof_scores.extend(probabilities.tolist())
        oof_labels.extend(eval_labels)
        folds.append(fold_summary)
    auc = _compute_binary_auc(labels=np.asarray(oof_labels, dtype=np.int8), scores=np.asarray(oof_scores, dtype=np.float64))
    excess_auc = abs(auc - 0.5)
    return {
        'name': 'propensity_check',
        'method': PROPENSITY_METHOD,
        'status': 'acceptable' if excess_auc <= PROPENSITY_EXCESS_AUC_THRESHOLD else 'failed',
        'score': excess_auc,
        'threshold': PROPENSITY_EXCESS_AUC_THRESHOLD,
        'score_direction': 'lower_is_better',
        'auc': auc,
        'split_version': PROPENSITY_SPLIT_VERSION,
        'feature_names': list(SHIFT_STATE_FIELDS_V1),
        'fold_count': 2,
        'oof_sample_count': len(oof_scores),
        'folds': folds,
    }


def _split_domain_folds(rows: list[dict[str, object]], *, domain_prefix: str) -> list[dict[str, object]]:
    blocks = _materialize_blocks(rows, domain_prefix=domain_prefix)
    midpoint = len(blocks) // 2
    return [
        _merge_blocks(blocks[:midpoint]),
        _merge_blocks(blocks[midpoint:]),
    ]


def _materialize_blocks(rows: list[dict[str, object]], *, domain_prefix: str) -> list[dict[str, object]]:
    grouped: dict[str, dict[str, object]] = {}
    for row in rows:
        block_id = _resolve_block_id(row=row, domain_prefix=domain_prefix)
        block = grouped.setdefault(
            block_id,
            {
                'block_id': block_id,
                'rows': [],
                'start_ts': int(row['decision_ts']),
                'end_ts': int(row['decision_ts']),
            },
        )
        decision_ts = int(row['decision_ts'])
        block['rows'].append(row)
        block['start_ts'] = min(int(block['start_ts']), decision_ts)
        block['end_ts'] = max(int(block['end_ts']), decision_ts)
    blocks = list(grouped.values())
    blocks.sort(key=lambda block: (int(block['start_ts']), int(block['end_ts']), str(block['block_id'])))
    return blocks


def _resolve_block_id(*, row: dict[str, object], domain_prefix: str) -> str:
    session_id = str(row.get('session_id', '')).strip()
    if session_id:
        return session_id
    return f"{domain_prefix}-{int(row['decision_ts'])}"


def _merge_blocks(blocks: list[dict[str, object]]) -> dict[str, object]:
    if not blocks:
        return {'rows': [], 'block_ids': [], 'start_ts': None, 'end_ts': None}
    rows = [
        row
        for block in blocks
        for row in block['rows']
    ]
    rows.sort(key=lambda row: int(row['decision_ts']))
    return {
        'rows': rows,
        'block_ids': [str(block['block_id']) for block in blocks],
        'start_ts': min(int(block['start_ts']) for block in blocks),
        'end_ts': max(int(block['end_ts']) for block in blocks),
    }


def _merge_domain_folds(
    source_folds: list[list[dict[str, object]]],
    target_folds: list[list[dict[str, object]]],
    *,
    include_fold: int | None = None,
    exclude_fold: int | None = None,
) -> tuple[list[dict[str, object]], list[int]]:
    rows: list[dict[str, object]] = []
    labels: list[int] = []
    for fold_index, source_fold in enumerate(source_folds):
        if include_fold is not None and fold_index != include_fold:
            continue
        if exclude_fold is not None and fold_index == exclude_fold:
            continue
        rows.extend(source_fold['rows'])
        labels.extend([0] * len(source_fold['rows']))
    for fold_index, target_fold in enumerate(target_folds):
        if include_fold is not None and fold_index != include_fold:
            continue
        if exclude_fold is not None and fold_index == exclude_fold:
            continue
        rows.extend(target_fold['rows'])
        labels.extend([1] * len(target_fold['rows']))
    return rows, labels


def _build_fold_summary(
    *,
    holdout_index: int,
    source_folds: list[dict[str, object]],
    target_folds: list[dict[str, object]],
) -> dict[str, object]:
    source_eval = source_folds[holdout_index]
    target_eval = target_folds[holdout_index]
    source_train = source_folds[1 - holdout_index]
    target_train = target_folds[1 - holdout_index]
    eval_start_ts = min(
        value
        for value in (source_eval['start_ts'], target_eval['start_ts'])
        if value is not None
    )
    eval_end_ts = max(
        value
        for value in (source_eval['end_ts'], target_eval['end_ts'])
        if value is not None
    )
    return {
        'fold_index': holdout_index,
        'source_train_session_ids': list(source_train['block_ids']),
        'source_eval_session_ids': list(source_eval['block_ids']),
        'target_train_block_ids': list(target_train['block_ids']),
        'target_eval_block_ids': list(target_eval['block_ids']),
        'source_eval_row_count': len(source_eval['rows']),
        'target_eval_row_count': len(target_eval['rows']),
        'train_start_ts': min(
            value
            for value in (source_train['start_ts'], target_train['start_ts'])
            if value is not None
        ),
        'train_end_ts': max(
            value
            for value in (source_train['end_ts'], target_train['end_ts'])
            if value is not None
        ),
        'eval_start_ts': eval_start_ts,
        'eval_end_ts': eval_end_ts,
        'embargo_sec': PROPENSITY_EMBARGO_SECONDS,
    }


def _fit_and_score_logistic_oof(
    *,
    train_rows: list[dict[str, object]],
    train_labels: list[int],
    eval_rows: list[dict[str, object]],
) -> np.ndarray:
    train_matrix = _build_domain_matrix(train_rows)
    eval_matrix = _build_domain_matrix(eval_rows)
    scaled_train, scaled_eval = _fit_robust_scaler(train_matrix, eval_matrix)
    weights, bias = _fit_logistic_regression(scaled_train, np.asarray(train_labels, dtype=np.float64))
    logits = np.clip((scaled_eval @ weights) + bias, -PROPENSITY_LOGIT_CLIP, PROPENSITY_LOGIT_CLIP)
    return 1.0 / (1.0 + np.exp(-logits))


def _build_domain_matrix(rows: list[dict[str, object]]) -> np.ndarray:
    matrix = []
    for row in rows:
        state = row['shift_state'] if 'shift_state' in row else parse_shift_state_blob(row)
        matrix.append([float(state[feature_name]) for feature_name in SHIFT_STATE_FIELDS_V1])
    return np.asarray(matrix, dtype=np.float64)


def _fit_robust_scaler(
    train_matrix: np.ndarray,
    eval_matrix: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    median = np.median(train_matrix, axis=0)
    mad = np.median(np.abs(train_matrix - median), axis=0)
    scale = np.where(mad > ROBUST_SCALE_FLOOR, mad, 1.0)
    return (train_matrix - median) / scale, (eval_matrix - median) / scale


def _fit_logistic_regression(matrix: np.ndarray, labels: np.ndarray) -> tuple[np.ndarray, float]:
    weights = np.zeros(matrix.shape[1], dtype=np.float64)
    bias = 0.0
    sample_count = float(len(matrix))
    for _ in range(PROPENSITY_EPOCHS):
        logits = np.clip((matrix @ weights) + bias, -PROPENSITY_LOGIT_CLIP, PROPENSITY_LOGIT_CLIP)
        probabilities = 1.0 / (1.0 + np.exp(-logits))
        residual = probabilities - labels
        grad_weights = (matrix.T @ residual) / sample_count + (PROPENSITY_L2_REGULARIZATION * weights)
        grad_bias = float(np.sum(residual) / sample_count)
        weights -= PROPENSITY_LEARNING_RATE * grad_weights
        bias -= PROPENSITY_LEARNING_RATE * grad_bias
    return weights, bias


def _compute_binary_auc(*, labels: np.ndarray, scores: np.ndarray) -> float:
    positive_scores = scores[labels == 1]
    negative_scores = scores[labels == 0]
    if len(positive_scores) == 0 or len(negative_scores) == 0:
        return 1.0
    pairwise = positive_scores[:, None] - negative_scores[None, :]
    wins = float(np.sum(pairwise > 0.0))
    ties = float(np.sum(pairwise == 0.0))
    return (wins + (0.5 * ties)) / float(len(positive_scores) * len(negative_scores))


def _build_failed_propensity_result(*, reason: str) -> dict[str, object]:
    return {
        'name': 'propensity_check',
        'method': PROPENSITY_METHOD,
        'status': 'failed',
        'score': 1.0,
        'threshold': PROPENSITY_EXCESS_AUC_THRESHOLD,
        'score_direction': 'lower_is_better',
        'auc': None,
        'split_version': PROPENSITY_SPLIT_VERSION,
        'feature_names': list(SHIFT_STATE_FIELDS_V1),
        'fold_count': 2,
        'oof_sample_count': 0,
        'reason': reason,
        'folds': [],
    }


def _fold_is_outside_embargo(*, fold_summary: dict[str, object]) -> bool:
    train_end_ts = int(fold_summary['train_end_ts'])
    eval_start_ts = int(fold_summary['eval_start_ts'])
    if train_end_ts <= eval_start_ts - PROPENSITY_EMBARGO_SECONDS:
        return True
    train_start_ts = int(fold_summary['train_start_ts'])
    eval_end_ts = int(fold_summary['eval_end_ts'])
    return train_start_ts >= eval_end_ts + PROPENSITY_EMBARGO_SECONDS
