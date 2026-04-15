from __future__ import annotations


EXPANDING_REFIT_POLICY_VERSION = 'expanding_refit_recompute_all_statistics_v1'


def build_refit_policy_bundle(*, refit_policy_version: str) -> dict[str, object]:
    if refit_policy_version != EXPANDING_REFIT_POLICY_VERSION:
        raise ValueError(f'unsupported refit policy version: {refit_policy_version}')
    return {
        'refit_policy_version': refit_policy_version,
        'window_type': 'expanding',
        'fit_scope': 'all_rows_strictly_before_origin',
        'recompute_statistics_per_origin': True,
        'recomputed_components': [
            'feature_statistics',
            'strata_cutpoints',
            'weighting_fit',
            'forecast_model',
            'decision_policy_parameters',
            'decision_utility_parameters',
        ],
        'model_frozen_within_test_block': True,
    }
