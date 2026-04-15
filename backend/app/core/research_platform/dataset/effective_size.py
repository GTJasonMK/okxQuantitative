from __future__ import annotations


def estimate_effective_sample_size(
    *,
    sequence: list[float],
    truncation_rule: str,
) -> float:
    if truncation_rule != 'initial_positive_sequence_v1':
        raise ValueError(f'unsupported truncation rule: {truncation_rule}')
    if len(sequence) <= 1:
        return float(len(sequence))
    variance = _variance(sequence)
    if variance <= 0.0:
        return float(len(sequence))
    rho_sum = _positive_autocorrelation_sum(sequence, variance)
    tau = max(1.0, 1.0 + (2.0 * rho_sum))
    return min(float(len(sequence)), float(len(sequence)) / tau)


def build_effective_size_summary(
    *,
    train_rows: list[dict[str, object]],
    val_rows: list[dict[str, object]],
    test_rows: list[dict[str, object]],
) -> dict[str, object]:
    return {
        'truncation_rule': 'initial_positive_sequence_v1',
        'sequence_definitions': {
            'primary_validation_score_sequence': {
                'materialized_in_stage': 'training_run',
                'sequence_role': 'model_selection_objective',
            },
            'label_r_close_sequence': {
                'field_name': 'r_close',
                'materialized_in_stage': 'dataset_manifest',
                'sequence_role': 'data_dependence_proxy',
                'estimates': {
                    'train': estimate_effective_sample_size(
                        sequence=_extract_r_close(train_rows),
                        truncation_rule='initial_positive_sequence_v1',
                    ),
                    'val': estimate_effective_sample_size(
                        sequence=_extract_r_close(val_rows),
                        truncation_rule='initial_positive_sequence_v1',
                    ),
                    'test': estimate_effective_sample_size(
                        sequence=_extract_r_close(test_rows),
                        truncation_rule='initial_positive_sequence_v1',
                    ),
                },
            },
            'model_comparison_delta_sequence': {
                'materialized_in_stage': 'training_run',
                'sequence_role': 'pairwise_model_difference',
            },
        },
    }


def _extract_r_close(rows: list[dict[str, object]]) -> list[float]:
    return [float(row['r_close']) for row in rows]


def _positive_autocorrelation_sum(sequence: list[float], variance: float) -> float:
    rho_sum = 0.0
    for lag in range(1, len(sequence)):
        rho = _autocorrelation(sequence, variance, lag)
        if rho <= 0.0:
            break
        rho_sum += rho
    return rho_sum


def _autocorrelation(sequence: list[float], variance: float, lag: int) -> float:
    center = sum(sequence) / len(sequence)
    numerator = 0.0
    for index in range(lag, len(sequence)):
        numerator += (sequence[index] - center) * (sequence[index - lag] - center)
    denominator = (len(sequence) - lag) * variance
    return numerator / denominator if denominator > 0 else 0.0


def _variance(sequence: list[float]) -> float:
    center = sum(sequence) / len(sequence)
    return sum((value - center) ** 2 for value in sequence) / len(sequence)
