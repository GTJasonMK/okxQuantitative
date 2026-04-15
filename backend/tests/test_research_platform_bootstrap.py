from __future__ import annotations

import pytest

from app.core.research_platform.training.bootstrap import stationary_block_bootstrap_mean


def test_stationary_block_bootstrap_reports_ci():
    result = stationary_block_bootstrap_mean(
        values=[0.1, 0.2, 0.3, 0.4, 0.5],
        avg_block_length=9,
        bootstrap_repeats=200,
    )

    assert result['definition_version'] == 'stationary_block_bootstrap_min9_v1'
    assert result['avg_block_length'] == 9
    assert result['bootstrap_repeats'] == 200
    assert 'mean' in result
    assert 'ci_95' in result


def test_stationary_block_bootstrap_rejects_short_block_length():
    with pytest.raises(ValueError, match='avg_block_length must be at least 9'):
        stationary_block_bootstrap_mean(
            values=[0.1, 0.2, 0.3],
            avg_block_length=8,
            bootstrap_repeats=100,
        )
