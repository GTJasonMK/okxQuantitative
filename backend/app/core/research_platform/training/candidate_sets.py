from __future__ import annotations


LOCKED_BASELINE_MODELS = (
    ('unconditional_distribution_baseline', 'empirical_joint_distribution_v1'),
    ('independent_marginal_baseline', 'independent_marginal_distribution_v1'),
    ('point_baseline', 'zero_body_median_shadow_v1'),
)
LOCKED_DEFAULT_CANDIDATE_SET = {
    'canonical_ref': 'candidate://locked/default-v1',
    'accepted_refs': (
        'candidate://locked/default-v1',
        'artifact://candidate-set/locked-v1.json',
    ),
    'challenger_model_family': 'joint_density_model_v1',
    'baseline_models': LOCKED_BASELINE_MODELS,
}


def resolve_locked_candidate_set(candidate_set_ref: str) -> dict[str, object]:
    normalized_ref = str(candidate_set_ref)
    if normalized_ref in LOCKED_DEFAULT_CANDIDATE_SET['accepted_refs']:
        return dict(LOCKED_DEFAULT_CANDIDATE_SET)
    raise ValueError(f'unsupported candidate_set_ref: {candidate_set_ref}')


def validate_candidate_set_request(*, candidate_set_ref: str, model_family: str) -> None:
    candidate_set = resolve_locked_candidate_set(candidate_set_ref)
    expected_model_family = str(candidate_set['challenger_model_family'])
    if str(model_family) != expected_model_family:
        raise ValueError(
            'candidate_set_ref requires challenger model_family '
            f'{expected_model_family}, got {model_family}'
        )


def ordered_locked_baselines(
    *,
    candidate_set_ref: str,
    baseline_bundle: dict[str, object],
) -> list[dict[str, str]]:
    candidate_set = resolve_locked_candidate_set(candidate_set_ref)
    baseline_map = {
        str(baseline['baseline_id']): str(baseline['baseline_model'])
        for baseline in baseline_bundle.get('baselines', [])
    }
    ordered = []
    missing = []
    for baseline_id, baseline_model in candidate_set['baseline_models']:
        actual_model = baseline_map.get(baseline_id)
        if actual_model is None:
            missing.append(baseline_id)
            continue
        ordered.append(
            {
                'baseline_id': baseline_id,
                'baseline_model': actual_model or baseline_model,
            }
        )
    if missing:
        raise ValueError(f'candidate_set_ref missing baseline artifacts: {missing}')
    return ordered
