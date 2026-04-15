from __future__ import annotations

from .baselines import select_reference_baseline
from .bootstrap import stationary_block_bootstrap_mean

MULTIPLE_COMPARISON_VERSION = 'locked_candidate_set_v1'
RETAINED_MODEL_RULE = 'best_relative_stationary_block_ci_v1'


def build_comparison_result(
    *,
    challenger_scores: list[float],
    baseline_scores: list[float],
    candidate_set_ref: str,
    retained_model_set: list[str],
    delta_by_origin: list[float] | None = None,
) -> dict[str, object]:
    _validate_score_lengths(
        challenger_scores=challenger_scores,
        baseline_scores=baseline_scores,
    )
    diff = [challenger - baseline for challenger, baseline in zip(challenger_scores, baseline_scores)]
    delta_mean = sum(diff) / len(diff) if diff else 0.0
    return {
        'delta_mean': delta_mean,
        'delta_sequence': diff,
        'delta_by_origin': list(delta_by_origin or diff),
        'retained_model_set': list(retained_model_set),
        'candidate_set_ref': candidate_set_ref,
        'multiple_comparison_version': MULTIPLE_COMPARISON_VERSION,
        'paired_block_bootstrap_ref': 'artifact://paired-bootstrap',
        'paired_block_bootstrap_result': stationary_block_bootstrap_mean(
            values=diff,
            avg_block_length=9,
            bootstrap_repeats=200,
        ),
    }


def build_locked_candidate_comparison_result(
    *,
    challenger_origins: list[dict[str, object]],
    challenger_id: str,
    baseline_bundle: dict[str, object],
    candidate_set_ref: str,
) -> dict[str, object]:
    baseline = select_reference_baseline(baseline_bundle)
    candidate_entries = _build_candidate_entries(
        challenger_origins=challenger_origins,
        challenger_id=challenger_id,
        baseline_bundle=baseline_bundle,
    )
    ranking = _build_candidate_ranking(candidate_entries)
    best_candidate_id = str(ranking[0]['candidate_id'])
    pairwise_results = _build_pairwise_results_against_best(
        candidate_entries=candidate_entries,
        best_candidate_id=best_candidate_id,
        candidate_set_ref=candidate_set_ref,
    )
    retained_model_set = _build_retained_model_set(
        best_candidate_id=best_candidate_id,
        pairwise_results=pairwise_results,
    )
    baseline_pair = build_comparison_result(
        challenger_scores=_flatten_forecast_score_sequences(challenger_origins),
        baseline_scores=_flatten_forecast_score_sequences(list(baseline['origins'])),
        candidate_set_ref=candidate_set_ref,
        retained_model_set=retained_model_set,
        delta_by_origin=_extract_origin_metric_deltas(
            challenger_origins=challenger_origins,
            baseline_origins=list(baseline['origins']),
        ),
    )
    return {
        **baseline_pair,
        'baseline_id': str(baseline['baseline_id']),
        'best_candidate_id': best_candidate_id,
        'reference_candidate_id': best_candidate_id,
        'candidate_ranking': ranking,
        'pairwise_results': pairwise_results,
        'retained_model_set': retained_model_set,
        'data_snooping_control': {
            'candidate_set_locked_before_outer_test': True,
            'candidate_count': len(candidate_entries),
            'retention_rule': RETAINED_MODEL_RULE,
            'reporting_scope': 'candidate_ranking_and_retained_model_set',
        },
    }


def _build_candidate_entries(
    *,
    challenger_origins: list[dict[str, object]],
    challenger_id: str,
    baseline_bundle: dict[str, object],
) -> list[dict[str, object]]:
    entries = [
        {
            'candidate_id': challenger_id,
            'candidate_kind': 'challenger',
            'model_id': challenger_id,
            'origins': list(challenger_origins),
        }
    ]
    for baseline in baseline_bundle.get('baselines', []):
        baseline_origins = list(baseline['origins'])
        _validate_origin_alignment(
            challenger_origins=challenger_origins,
            baseline_origins=baseline_origins,
        )
        entries.append(
            {
                'candidate_id': str(baseline['baseline_id']),
                'candidate_kind': 'baseline',
                'model_id': str(baseline.get('baseline_model', baseline['baseline_id'])),
                'origins': baseline_origins,
            }
        )
    return entries


def _build_candidate_ranking(
    candidate_entries: list[dict[str, object]],
) -> list[dict[str, object]]:
    ranked = sorted(
        candidate_entries,
        key=_ranking_key,
    )
    return [
        {
            'rank': rank + 1,
            'candidate_id': str(entry['candidate_id']),
            'candidate_kind': str(entry['candidate_kind']),
            'model_id': str(entry['model_id']),
            'joint_nll_mean': _mean(_extract_joint_nll_scores(entry['origins'])),
        }
        for rank, entry in enumerate(ranked)
    ]


def _ranking_key(entry: dict[str, object]) -> tuple[float, int, str]:
    kind_priority = 0 if str(entry['candidate_kind']) == 'challenger' else 1
    return (
        _mean(_extract_joint_nll_scores(entry['origins'])),
        kind_priority,
        str(entry['candidate_id']),
    )


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _build_pairwise_results_against_best(
    *,
    candidate_entries: list[dict[str, object]],
    best_candidate_id: str,
    candidate_set_ref: str,
) -> list[dict[str, object]]:
    reference_entry = _find_candidate_entry(
        candidate_entries=candidate_entries,
        candidate_id=best_candidate_id,
    )
    reference_scores = _extract_joint_nll_scores(reference_entry['origins'])
    results = []
    for entry in candidate_entries:
        if str(entry['candidate_id']) == best_candidate_id:
            continue
        pair = build_comparison_result(
            challenger_scores=_flatten_forecast_score_sequences(entry['origins']),
            baseline_scores=_flatten_forecast_score_sequences(reference_entry['origins']),
            candidate_set_ref=candidate_set_ref,
            retained_model_set=[],
            delta_by_origin=_extract_origin_metric_deltas(
                challenger_origins=entry['origins'],
                baseline_origins=reference_entry['origins'],
            ),
        )
        results.append(
            {
                'candidate_id': str(entry['candidate_id']),
                'candidate_kind': str(entry['candidate_kind']),
                'model_id': str(entry['model_id']),
                'reference_candidate_id': best_candidate_id,
                'delta_mean': float(pair['delta_mean']),
                'delta_by_origin': list(pair['delta_by_origin']),
                'paired_block_bootstrap_ref': str(pair['paired_block_bootstrap_ref']),
                'paired_block_bootstrap_result': dict(pair['paired_block_bootstrap_result']),
            }
        )
    return results


def _find_candidate_entry(
    *,
    candidate_entries: list[dict[str, object]],
    candidate_id: str,
) -> dict[str, object]:
    for entry in candidate_entries:
        if str(entry['candidate_id']) == candidate_id:
            return entry
    raise ValueError(f'candidate not found: {candidate_id}')


def _build_retained_model_set(
    *,
    best_candidate_id: str,
    pairwise_results: list[dict[str, object]],
) -> list[str]:
    retained = [best_candidate_id]
    for pair in pairwise_results:
        ci_low, ci_high = pair['paired_block_bootstrap_result']['ci_95']
        if ci_low <= 0.0 <= ci_high:
            retained.append(str(pair['candidate_id']))
    return retained


def _validate_score_lengths(
    *,
    challenger_scores: list[float],
    baseline_scores: list[float],
) -> None:
    if len(challenger_scores) != len(baseline_scores):
        raise ValueError('score sequences must have the same length')
    if not challenger_scores:
        raise ValueError('score sequences must be non-empty')


def _validate_origin_alignment(
    *,
    challenger_origins: list[dict[str, object]],
    baseline_origins: list[dict[str, object]],
) -> None:
    challenger_origin_ts = [int(origin['origin_ts']) for origin in challenger_origins]
    baseline_origin_ts = [int(origin['origin_ts']) for origin in baseline_origins]
    if challenger_origin_ts != baseline_origin_ts:
        raise ValueError('origin sequences must align by origin_ts')


def _extract_origin_metric_deltas(
    *,
    challenger_origins: list[dict[str, object]],
    baseline_origins: list[dict[str, object]],
) -> list[float]:
    _validate_origin_alignment(
        challenger_origins=challenger_origins,
        baseline_origins=baseline_origins,
    )
    return [
        float(challenger_origin['forecast_metrics']['joint_nll'])
        - float(baseline_origin['forecast_metrics']['joint_nll'])
        for challenger_origin, baseline_origin in zip(challenger_origins, baseline_origins)
    ]


def _extract_joint_nll_scores(origins: list[dict[str, object]]) -> list[float]:
    return [float(origin['forecast_metrics']['joint_nll']) for origin in origins]


def _flatten_forecast_score_sequences(origins: list[dict[str, object]]) -> list[float]:
    sequences: list[float] = []
    for origin in origins:
        score_sequence = origin.get('forecast_score_sequence')
        if not score_sequence:
            raise ValueError(f"origin {origin['origin_ts']} missing forecast_score_sequence")
        sequences.extend(float(value) for value in score_sequence)
    return sequences
