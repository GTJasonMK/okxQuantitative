from __future__ import annotations

from .candidate_sets import ordered_locked_baselines
from .candidate_sets import resolve_locked_candidate_set
from .comparison import MULTIPLE_COMPARISON_VERSION, RETAINED_MODEL_RULE
from .decision_policy import EXECUTION_ASSUMPTION_VERSION


HOLD_WINDOW_SEC = 900


def build_execution_assumption_bundle(
    *,
    execution_assumption_version: str,
) -> dict[str, object]:
    if execution_assumption_version != EXECUTION_ASSUMPTION_VERSION:
        raise ValueError(
            'unsupported execution assumption version: '
            f'{execution_assumption_version}'
        )
    return {
        'execution_assumption_version': execution_assumption_version,
        'decision_boundary': 'exchange_fixed_15m_boundary',
        'anchor_price_source': 'last_feature_bar_close_price',
        'rebalance_timing': 'at_boundary_t',
        'hold_window_sec': HOLD_WINDOW_SEC,
        'position_transition': 'rebalance_then_hold_to_close',
        'intrabar_rebalance_allowed': False,
        'intrabar_stop_loss_allowed': False,
        'intrabar_take_profit_allowed': False,
        'intrabar_queue_model_allowed': False,
        'next_rebalance_rule': 'next_15m_boundary_only',
    }


def build_candidate_set_bundle(
    *,
    run: dict[str, object],
    baseline_bundle: dict[str, object],
) -> dict[str, object]:
    multiple_comparison_version = str(run['multiple_comparison_version'])
    if multiple_comparison_version != MULTIPLE_COMPARISON_VERSION:
        raise ValueError(
            'unsupported multiple comparison version: '
            f'{multiple_comparison_version}'
        )
    candidate_set_ref = str(run['candidate_set_ref'])
    if not candidate_set_ref:
        raise ValueError('candidate_set_ref must be non-empty')
    candidate_set = resolve_locked_candidate_set(candidate_set_ref)
    baselines = ordered_locked_baselines(
        candidate_set_ref=candidate_set_ref,
        baseline_bundle=baseline_bundle,
    )
    candidate_models = [
        {
            'candidate_id': str(candidate_set['challenger_model_family']),
            'candidate_kind': 'challenger',
            'model_id': str(candidate_set['challenger_model_family']),
            'model_spec_ref': str(run['model_spec_ref']),
        },
        *[
            {
                'candidate_id': baseline['baseline_id'],
                'candidate_kind': 'baseline',
                'model_id': baseline['baseline_model'],
                'model_spec_ref': '',
            }
            for baseline in baselines
        ],
    ]
    candidate_count = len(candidate_models)
    return {
        'candidate_set_ref': candidate_set_ref,
        'multiple_comparison_version': multiple_comparison_version,
        'frozen_before_outer_test': True,
        'freeze_scope': 'outer_test_pre_start',
        'challenger': {
            'model_family': str(candidate_set['challenger_model_family']),
            'model_spec_ref': str(run['model_spec_ref']),
        },
        'baselines': baselines,
        'candidate_models': candidate_models,
        'candidate_count': candidate_count,
        'retained_model_set_required': candidate_count > 2,
        'retained_model_rule': RETAINED_MODEL_RULE,
        'reporting_scope': 'candidate_ranking_and_retained_model_set',
    }
