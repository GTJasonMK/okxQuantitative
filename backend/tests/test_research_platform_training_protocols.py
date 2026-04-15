from __future__ import annotations

import pytest

from app.core.research_platform.training.protocol_artifacts import build_candidate_set_bundle
from app.core.research_platform.training.protocols import validate_model_output_contract


def test_validate_model_output_contract_rejects_unimplemented_joint_family():
    with pytest.raises(ValueError, match='unknown model family'):
        validate_model_output_contract('joint_sample_forecaster_v1')


def test_build_candidate_set_bundle_uses_locked_candidate_order():
    bundle = build_candidate_set_bundle(
        run={
            'candidate_set_ref': 'candidate://locked/default-v1',
            'model_family': 'joint_density_model_v1',
            'model_spec_ref': 'model://joint_density_model_v1/default-v1',
            'multiple_comparison_version': 'locked_candidate_set_v1',
        },
        baseline_bundle={
            'baselines': [
                {
                    'baseline_id': 'point_baseline',
                    'baseline_model': 'zero_body_median_shadow_v1',
                },
                {
                    'baseline_id': 'unconditional_distribution_baseline',
                    'baseline_model': 'empirical_joint_distribution_v1',
                },
                {
                    'baseline_id': 'independent_marginal_baseline',
                    'baseline_model': 'independent_marginal_distribution_v1',
                },
            ],
        },
    )

    assert [item['candidate_id'] for item in bundle['candidate_models']] == [
        'joint_density_model_v1',
        'unconditional_distribution_baseline',
        'independent_marginal_baseline',
        'point_baseline',
    ]
