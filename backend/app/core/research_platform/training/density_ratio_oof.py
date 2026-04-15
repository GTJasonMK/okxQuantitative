from __future__ import annotations

import numpy as np


FOLD_COUNT = 2
DOMAIN_CLASS_COUNT = 2
CLASS_PRIOR_PI = 0.5
LOGISTIC_EPOCHS = 300
LOGISTIC_LEARNING_RATE = 0.05
LOGISTIC_L2_REGULARIZATION = 0.01
LOGIT_CLIP = 40.0
ROBUST_SCALE_FLOOR = 1e-6
PROBABILITY_FLOOR = 1e-6
SOURCE_DOMAIN_LABEL = 0
TARGET_DOMAIN_LABEL = 1
OOF_EMBARGO_SECONDS = 8100
SAMPLING_SCHEME = 'balanced_1_to_1'
CALIBRATION_METHOD = 'none'
WEIGHT_FORMULA = '((1-pi)/pi) * eta / (1-eta)'


def fit_blocked_density_ratio_origin(
    *,
    rows: list[dict[str, object]],
    vector_builder,
    categorical_feature_names: list[str],
    continuous_feature_names: list[str],
) -> tuple[dict[str, object], dict[str, object]]:
    matrix = _build_feature_matrix(rows=rows, vector_builder=vector_builder)
    labels = _build_label_vector(rows=rows)
    folds = _build_blocked_folds(rows=rows)
    eta_oof = _score_oof_predictions(matrix=matrix, labels=labels, folds=folds)
    full_fit = _fit_logistic_bundle(matrix=matrix, labels=labels)
    return (
        _build_fit_artifact(
            fit=full_fit,
            eta_oof=eta_oof,
            folds=folds,
            categorical_feature_names=categorical_feature_names,
            continuous_feature_names=continuous_feature_names,
        ),
        build_weight_fit_from_eta_oof(eta_oof=eta_oof.tolist()),
    )


def score_density_ratio_feature_vector(
    *,
    vector: list[float],
    fit: dict[str, object],
) -> float:
    matrix = np.asarray([vector], dtype=np.float64)
    eta = _score_probability(
        matrix=matrix,
        scaler_center=np.asarray(fit['scaler_center'], dtype=np.float64),
        scaler_scale=np.asarray(fit['scaler_scale'], dtype=np.float64),
        weights=np.asarray(fit['coef'][0], dtype=np.float64),
        bias=float(fit['intercept'][0]),
    )[0]
    return _density_ratio_from_eta(eta=eta)


def build_weight_fit_from_eta_oof(*, eta_oof: list[float]) -> dict[str, object]:
    return {
        'eta_oof': eta_oof,
        'raw_density_ratio': [_density_ratio_from_eta(eta=value) for value in eta_oof],
        'class_prior_pi': CLASS_PRIOR_PI,
        'sampling_scheme': SAMPLING_SCHEME,
        'calibration_method': CALIBRATION_METHOD,
        'weight_formula': WEIGHT_FORMULA,
        'oof_row_count': len(eta_oof),
    }


def _build_feature_matrix(*, rows: list[dict[str, object]], vector_builder) -> np.ndarray:
    return np.asarray([vector_builder(row) for row in rows], dtype=np.float64)


def _build_label_vector(*, rows: list[dict[str, object]]) -> np.ndarray:
    labels = np.asarray([float(int(row['domain_label'])) for row in rows], dtype=np.float64)
    if not np.any(labels == SOURCE_DOMAIN_LABEL) or not np.any(labels == TARGET_DOMAIN_LABEL):
        raise ValueError('density ratio classifier requires both source and target domain rows')
    return labels


def _build_blocked_folds(*, rows: list[dict[str, object]]) -> list[dict[str, object]]:
    source_blocks = _split_domain_blocks(rows=rows, domain_label=SOURCE_DOMAIN_LABEL)
    target_blocks = _split_domain_blocks(rows=rows, domain_label=TARGET_DOMAIN_LABEL)
    return [
        _build_fold_payload(
            fold_index=fold_index,
            source_blocks=source_blocks,
            target_blocks=target_blocks,
        )
        for fold_index in range(FOLD_COUNT)
    ]


def _split_domain_blocks(
    *,
    rows: list[dict[str, object]],
    domain_label: int,
) -> list[list[dict[str, object]]]:
    blocks = _materialize_session_blocks(rows=rows, domain_label=domain_label)
    midpoint = len(blocks) // FOLD_COUNT
    if midpoint == 0 or midpoint == len(blocks):
        raise ValueError('density ratio OOF requires at least 2 session blocks per domain')
    return [blocks[:midpoint], blocks[midpoint:]]


def _materialize_session_blocks(
    *,
    rows: list[dict[str, object]],
    domain_label: int,
) -> list[dict[str, object]]:
    blocks: dict[str, dict[str, object]] = {}
    for row_index, row in enumerate(rows):
        if int(row['domain_label']) != domain_label:
            continue
        session_id = str(row['session_id'])
        block = blocks.setdefault(
            session_id,
            {
                'session_id': session_id,
                'domain_label': domain_label,
                'row_indices': [],
                'start_ts': int(row['decision_ts']),
                'end_ts': int(row['decision_ts']),
            },
        )
        decision_ts = int(row['decision_ts'])
        block['row_indices'].append(row_index)
        block['start_ts'] = min(int(block['start_ts']), decision_ts)
        block['end_ts'] = max(int(block['end_ts']), decision_ts)
    ordered = list(blocks.values())
    ordered.sort(key=lambda block: (int(block['start_ts']), int(block['end_ts']), str(block['session_id'])))
    return ordered


def _build_fold_payload(
    *,
    fold_index: int,
    source_blocks: list[list[dict[str, object]]],
    target_blocks: list[list[dict[str, object]]],
) -> dict[str, object]:
    eval_blocks = source_blocks[fold_index] + target_blocks[fold_index]
    eval_start_ts = min(int(block['start_ts']) for block in eval_blocks)
    eval_end_ts = max(int(block['end_ts']) for block in eval_blocks)
    train_blocks = _filter_blocks_outside_embargo(
        blocks=source_blocks[1 - fold_index] + target_blocks[1 - fold_index],
        eval_start_ts=eval_start_ts,
        eval_end_ts=eval_end_ts,
        embargo_sec=OOF_EMBARGO_SECONDS,
    )
    if not train_blocks:
        raise ValueError('density ratio OOF requires temporal train blocks outside embargo')
    eval_indices = _collect_row_indices(blocks=eval_blocks)
    train_indices = _collect_row_indices(blocks=train_blocks)
    train_start_ts = min(int(block['start_ts']) for block in train_blocks)
    train_end_ts = max(int(block['end_ts']) for block in train_blocks)
    return {
        'fold_index': fold_index,
        'train_indices': train_indices,
        'eval_indices': eval_indices,
        'train_session_ids': sorted({str(block['session_id']) for block in train_blocks}),
        'eval_session_ids': sorted({str(block['session_id']) for block in eval_blocks}),
        'train_row_count': len(train_indices),
        'eval_row_count': len(eval_indices),
        'train_domain_row_counts': _count_rows_by_label(train_blocks),
        'eval_domain_row_counts': _count_rows_by_domain(source_blocks[fold_index], target_blocks[fold_index]),
        'train_start_ts': train_start_ts,
        'train_end_ts': train_end_ts,
        'eval_start_ts': eval_start_ts,
        'eval_end_ts': eval_end_ts,
        'embargo_sec': OOF_EMBARGO_SECONDS,
    }


def _collect_row_indices(*, blocks: list[dict[str, object]]) -> list[int]:
    row_indices: list[int] = []
    for block in blocks:
        row_indices.extend(int(row_index) for row_index in block['row_indices'])
    return sorted(row_indices)


def _count_rows_by_domain(
    source_blocks: list[dict[str, object]],
    target_blocks: list[dict[str, object]],
) -> dict[str, int]:
    return {
        str(SOURCE_DOMAIN_LABEL): sum(len(block['row_indices']) for block in source_blocks),
        str(TARGET_DOMAIN_LABEL): sum(len(block['row_indices']) for block in target_blocks),
    }


def _count_rows_by_label(blocks: list[dict[str, object]]) -> dict[str, int]:
    source_blocks = [block for block in blocks if int(block['domain_label']) == SOURCE_DOMAIN_LABEL]
    target_blocks = [block for block in blocks if int(block['domain_label']) == TARGET_DOMAIN_LABEL]
    return _count_rows_by_domain(source_blocks, target_blocks)


def _filter_blocks_outside_embargo(
    *,
    blocks: list[dict[str, object]],
    eval_start_ts: int,
    eval_end_ts: int,
    embargo_sec: int,
) -> list[dict[str, object]]:
    return [
        block
        for block in blocks
        if _block_is_outside_embargo(
            block=block,
            eval_start_ts=eval_start_ts,
            eval_end_ts=eval_end_ts,
            embargo_sec=embargo_sec,
        )
    ]


def _block_is_outside_embargo(
    *,
    block: dict[str, object],
    eval_start_ts: int,
    eval_end_ts: int,
    embargo_sec: int,
) -> bool:
    block_end_ts = int(block['end_ts'])
    if block_end_ts <= eval_start_ts - embargo_sec:
        return True
    return int(block['start_ts']) >= eval_end_ts + embargo_sec


def _score_oof_predictions(
    *,
    matrix: np.ndarray,
    labels: np.ndarray,
    folds: list[dict[str, object]],
) -> np.ndarray:
    eta_oof = np.full(len(matrix), np.nan, dtype=np.float64)
    for fold in folds:
        train_indices = np.asarray(fold['train_indices'], dtype=np.int64)
        eval_indices = np.asarray(fold['eval_indices'], dtype=np.int64)
        fit = _fit_logistic_bundle(matrix=matrix[train_indices], labels=labels[train_indices])
        eta_oof[eval_indices] = _score_probability(
            matrix=matrix[eval_indices],
            scaler_center=fit['scaler_center'],
            scaler_scale=fit['scaler_scale'],
            weights=fit['weights'],
            bias=fit['bias'],
        )
    if np.isnan(eta_oof).any():
        raise ValueError('density ratio OOF left uncovered rows')
    return eta_oof


def _fit_logistic_bundle(*, matrix: np.ndarray, labels: np.ndarray) -> dict[str, np.ndarray | float]:
    scaler_center = np.median(matrix, axis=0)
    median_abs_dev = np.median(np.abs(matrix - scaler_center), axis=0)
    scaler_scale = np.where(median_abs_dev > ROBUST_SCALE_FLOOR, median_abs_dev, 1.0)
    scaled_matrix = (matrix - scaler_center) / scaler_scale
    weights, bias = _fit_logistic_regression(matrix=scaled_matrix, labels=labels)
    return {
        'scaler_center': scaler_center,
        'scaler_scale': scaler_scale,
        'weights': weights,
        'bias': bias,
    }


def _fit_logistic_regression(*, matrix: np.ndarray, labels: np.ndarray) -> tuple[np.ndarray, float]:
    weights = np.zeros(matrix.shape[1], dtype=np.float64)
    bias = 0.0
    sample_weights = _build_balanced_sample_weights(labels=labels)
    total_weight = float(np.sum(sample_weights))
    for _ in range(LOGISTIC_EPOCHS):
        logits = np.clip((matrix @ weights) + bias, -LOGIT_CLIP, LOGIT_CLIP)
        probabilities = 1.0 / (1.0 + np.exp(-logits))
        residual = (probabilities - labels) * sample_weights
        grad_weights = (matrix.T @ residual) / total_weight
        grad_bias = float(np.sum(residual) / total_weight)
        weights -= LOGISTIC_LEARNING_RATE * (grad_weights + (LOGISTIC_L2_REGULARIZATION * weights))
        bias -= LOGISTIC_LEARNING_RATE * grad_bias
    return weights, bias


def _build_balanced_sample_weights(*, labels: np.ndarray) -> np.ndarray:
    sample_count = float(len(labels))
    source_count = float(np.sum(labels == SOURCE_DOMAIN_LABEL))
    target_count = float(np.sum(labels == TARGET_DOMAIN_LABEL))
    if source_count == 0.0 or target_count == 0.0:
        raise ValueError('density ratio classifier requires both source and target samples in each fold')
    source_weight = sample_count / (DOMAIN_CLASS_COUNT * source_count)
    target_weight = sample_count / (DOMAIN_CLASS_COUNT * target_count)
    return np.where(labels == TARGET_DOMAIN_LABEL, target_weight, source_weight)


def _score_probability(
    *,
    matrix: np.ndarray,
    scaler_center: np.ndarray,
    scaler_scale: np.ndarray,
    weights: np.ndarray,
    bias: float,
) -> np.ndarray:
    scaled_matrix = (matrix - scaler_center) / scaler_scale
    logits = np.clip((scaled_matrix @ weights) + bias, -LOGIT_CLIP, LOGIT_CLIP)
    return 1.0 / (1.0 + np.exp(-logits))


def _build_fit_artifact(
    *,
    fit: dict[str, np.ndarray | float],
    eta_oof: np.ndarray,
    folds: list[dict[str, object]],
    categorical_feature_names: list[str],
    continuous_feature_names: list[str],
) -> dict[str, object]:
    return {
        'scaler_center': fit['scaler_center'].tolist(),
        'scaler_scale': fit['scaler_scale'].tolist(),
        'coef': [fit['weights'].tolist()],
        'intercept': [float(fit['bias'])],
        'categorical_feature_names': categorical_feature_names,
        'continuous_feature_names': continuous_feature_names,
        'class_prior_pi': CLASS_PRIOR_PI,
        'sampling_scheme': SAMPLING_SCHEME,
        'calibration_method': CALIBRATION_METHOD,
        'eta_oof_summary': _summarize_probabilities(values=eta_oof),
        'folds': [_strip_fold_indices(fold=fold) for fold in folds],
    }


def _strip_fold_indices(*, fold: dict[str, object]) -> dict[str, object]:
    return {
        key: value
        for key, value in fold.items()
        if key not in {'train_indices', 'eval_indices'}
    }


def _summarize_probabilities(*, values: np.ndarray) -> dict[str, float]:
    return {
        'count': int(len(values)),
        'min': float(np.min(values)),
        'max': float(np.max(values)),
        'mean': float(np.mean(values)),
    }


def _density_ratio_from_eta(*, eta: float) -> float:
    return ((1.0 - CLASS_PRIOR_PI) / CLASS_PRIOR_PI) * eta / max(PROBABILITY_FLOOR, 1.0 - eta)
