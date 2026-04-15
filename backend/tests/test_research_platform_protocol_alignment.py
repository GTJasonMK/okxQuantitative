from __future__ import annotations

import pytest

from app.core.research_platform.protocol_registry import validate_protocol_bundle
from app.core.research_platform.training.artifacts import build_split_artifact


def test_build_split_artifact_uses_versioned_outer_origin_selection_policy():
    artifact = build_split_artifact(
        manifest={
            'split_definition_version': 'blocked_temporal_hv_v1',
            'embargo_sec': 8100,
            'refit_policy_version': 'expanding_refit_recompute_all_statistics_v1',
        },
        qualified_rows=[
            {'decision_ts': 1713000900 + (index * 900)}
            for index in range(24)
        ],
    )

    assert artifact['outer_origin_selection_policy'] == 'max_4_eligible_test_blocks_v1'
    assert len(artifact['origins']) == 4


def test_validate_protocol_bundle_accepts_versioned_outer_origin_selection_policy():
    validate_protocol_bundle(
        scope='dataset_manifest',
        payload={
            'outer_origin_selection_policy': 'max_4_eligible_test_blocks_v1',
        },
    )


def test_validate_protocol_bundle_rejects_unknown_outer_origin_selection_policy():
    with pytest.raises(ValueError, match='outer_origin_selection_policy=legacy_unknown'):
        validate_protocol_bundle(
            scope='dataset_manifest',
            payload={
                'outer_origin_selection_policy': 'legacy_unknown',
            },
        )
