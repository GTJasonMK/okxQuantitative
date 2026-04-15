from __future__ import annotations

from decimal import Decimal
from pathlib import Path

import pytest

from app.core.data_storage import DataStorage
from app.core.research_platform.dataset.service import ResearchDatasetService
from app.core.research_platform.training.service import ResearchTrainingService
from tests.research_platform_dataset_helpers import close_storage
from tests.research_platform_dataset_helpers import build_second_rows
from tests.research_platform_dataset_helpers import save_second_rows
from tests.research_platform_manifest_helpers import (
    DEFAULT_DECISION_TS,
    DEFAULT_INPUT_SECONDS,
    DEFAULT_INST_ID,
    DEFAULT_LABEL_SECONDS,
    DEFAULT_SESSION_ID,
    create_dataset_manifest,
)


TRAINING_SAMPLE_COUNT = 24


@pytest.fixture
def storage(tmp_path: Path):
    instance = DataStorage(tmp_path / 'research_training_run.db')
    yield instance
    close_storage(instance)


@pytest.fixture
def dataset_service(storage):
    return ResearchDatasetService(storage=storage)


@pytest.fixture
def dataset_manifest(storage):
    return create_dataset_manifest(storage, sample_count=TRAINING_SAMPLE_COUNT)


@pytest.fixture
def training_service(storage, dataset_service):
    return ResearchTrainingService(storage=storage, dataset_service=dataset_service)


def _seed_training_second_windows(storage) -> None:
    last_decision_ts = DEFAULT_DECISION_TS + ((TRAINING_SAMPLE_COUNT - 1) * DEFAULT_LABEL_SECONDS)
    start_ts = DEFAULT_DECISION_TS - DEFAULT_INPUT_SECONDS
    save_second_rows(
        storage,
        build_second_rows(
            start_ts=start_ts,
            count=last_decision_ts - start_ts,
        ),
    )


def test_start_training_run_copies_protocol_bundle_from_manifest(
    training_service,
    dataset_manifest,
):
    run = training_service.start_training_run(
        {
            'dataset_id': dataset_manifest['dataset_id'],
            'candidate_set_ref': 'artifact://candidate-set/locked-v1.json',
            'model_family': 'joint_density_model_v1',
            'model_spec_ref': 'model://joint_density_model_v1/defaults',
            'training_seed': 7,
        }
    )

    assert run['status'] == 'queued'
    assert run['evaluation_protocol_version'] == dataset_manifest['evaluation_protocol_version']
    assert run['score_definition_version'] == dataset_manifest['score_definition_version']
    assert run['policy_definition_version'] == dataset_manifest['policy_definition_version']
    assert run['decision_utility_version'] == dataset_manifest['decision_utility_version']
    assert run['regime_definition_version'] == dataset_manifest['regime_definition_version']
    assert run['outer_origin_selection_policy'] == dataset_manifest['outer_origin_selection_policy']
    assert run['multiple_comparison_version'] == dataset_manifest['multiple_comparison_version']


def test_start_training_run_rejects_baseline_only_challenger(training_service, dataset_manifest):
    with pytest.raises(ValueError, match='baseline-only model families cannot be registered as official challengers'):
        training_service.start_training_run(
            {
                'dataset_id': dataset_manifest['dataset_id'],
                'candidate_set_ref': 'artifact://candidate-set/locked-v1.json',
                'model_family': 'independent_four_head_regression_v1',
                'model_spec_ref': 'model://independent-four-head/defaults',
                'training_seed': 7,
            }
        )


def test_start_training_run_rejects_joint_distribution_baseline_challenger(training_service, dataset_manifest):
    with pytest.raises(ValueError, match='baseline-only model families cannot be registered as official challengers'):
        training_service.start_training_run(
            {
                'dataset_id': dataset_manifest['dataset_id'],
                'candidate_set_ref': 'artifact://candidate-set/locked-v1.json',
                'model_family': 'joint_distribution_baseline',
                'model_spec_ref': 'model://joint_distribution_baseline/defaults',
                'training_seed': 7,
            }
        )


def test_start_training_run_rejects_manifest_with_unsupported_protocol_value(
    training_service,
    dataset_manifest,
    monkeypatch,
):
    broken_manifest = dict(dataset_manifest)
    broken_manifest['evaluation_protocol_version'] = 'rolling_origin_v9'
    monkeypatch.setattr(
        training_service._dataset_service,
        'get_dataset_manifest',
        lambda _dataset_id: broken_manifest,
    )

    with pytest.raises(ValueError, match='unsupported protocol bundle'):
        training_service.start_training_run(
            {
                'dataset_id': dataset_manifest['dataset_id'],
                'candidate_set_ref': 'artifact://candidate-set/locked-v1.json',
                'model_family': 'joint_density_model_v1',
                'model_spec_ref': 'model://joint_density_model_v1/defaults',
                'training_seed': 7,
            }
        )


def test_training_run_detail_requires_materialized_second_state_windows(
    training_service,
    dataset_manifest,
):
    run = training_service.start_training_run(
        {
            'dataset_id': dataset_manifest['dataset_id'],
            'candidate_set_ref': 'artifact://candidate-set/locked-v1.json',
            'model_family': 'joint_density_model_v1',
            'model_spec_ref': 'model://joint_density_model_v1/defaults',
            'training_seed': 7,
        }
    )

    with pytest.raises(ValueError, match='missing second_state window'):
        training_service.get_training_run_detail(run['run_id'])


def test_start_training_run_rejects_dataset_without_complete_inner_validation_folds(
    storage,
    training_service,
):
    small_manifest = create_dataset_manifest(storage)

    with pytest.raises(ValueError, match='protocol-invalid: rolling-origin split requires at least one complete inner-validation fold per origin'):
        training_service.start_training_run(
            {
                'dataset_id': small_manifest['dataset_id'],
                'candidate_set_ref': 'artifact://candidate-set/locked-v1.json',
                'model_family': 'joint_density_model_v1',
                'model_spec_ref': 'model://joint_density_model_v1/defaults',
                'training_seed': 7,
            }
        )


def test_training_run_detail_split_artifact_uses_dataset_qualified_rows_only(
    storage,
    training_service,
    dataset_manifest,
):
    _seed_training_second_windows(storage)
    orphan_decision_ts = DEFAULT_DECISION_TS + (TRAINING_SAMPLE_COUNT * DEFAULT_LABEL_SECONDS)
    storage.save_research_sample_index_15m(
        sample_id=f'{DEFAULT_SESSION_ID}:{orphan_decision_ts}',
        session_id=DEFAULT_SESSION_ID,
        inst_id=DEFAULT_INST_ID,
        decision_ts=orphan_decision_ts,
        input_start_ts=orphan_decision_ts - 7200,
        input_end_ts=orphan_decision_ts,
        label_start_ts=orphan_decision_ts,
        label_end_ts=orphan_decision_ts + DEFAULT_LABEL_SECONDS,
        input_second_count=7200,
        label_second_count=DEFAULT_LABEL_SECONDS,
        input_complete_7200=1,
        label_complete_900=1,
        sample_valid=1,
        ready_for_inference=1,
        ready_for_training=1,
        invalid_reason='',
        prev_sample_overlap_seconds=6300,
        stride_seconds=DEFAULT_LABEL_SECONDS,
    )
    run = training_service.start_training_run(
        {
            'dataset_id': dataset_manifest['dataset_id'],
            'candidate_set_ref': 'artifact://candidate-set/locked-v1.json',
            'model_family': 'joint_density_model_v1',
            'model_spec_ref': 'model://joint_density_model_v1/defaults',
            'training_seed': 7,
        }
    )

    detail = training_service.get_training_run_detail(run['run_id'])
    origin_ts = [origin['origin_ts'] for origin in detail['artifacts']['split_artifact']['origins']]

    assert orphan_decision_ts not in origin_ts


def test_training_run_detail_materializes_run_local_refs_and_origin_evaluation(
    storage,
    training_service,
    dataset_manifest,
):
    _seed_training_second_windows(storage)
    run = training_service.start_training_run(
        {
            'dataset_id': dataset_manifest['dataset_id'],
            'candidate_set_ref': 'artifact://candidate-set/locked-v1.json',
            'model_family': 'joint_density_model_v1',
            'model_spec_ref': 'model://joint_density_model_v1/defaults',
            'training_seed': 7,
        }
    )

    detail = training_service.get_training_run_detail(run['run_id'])
    rolling_origin = detail['artifacts']['rolling_origin_evaluation']

    assert detail['policy_parameter_ref'] == f"artifact://training-run/{run['run_id']}/policy-params-by-origin.json"
    assert detail['utility_parameter_ref'] == f"artifact://training-run/{run['run_id']}/utility-params-by-origin.json"
    assert detail['artifacts']['policy_parameter_bundle']['policy_parameter_ref'] == detail['policy_parameter_ref']
    assert detail['artifacts']['utility_parameter_bundle']['utility_parameter_ref'] == detail['utility_parameter_ref']
    assert 'tau_entry' in detail['artifacts']['policy_parameter_bundle']['by_origin'][0]['policy_parameters']
    assert detail['artifacts']['utility_parameter_bundle']['by_origin'][0]['utility_parameters']['lambda_ae'] in {0.25, 0.5, 1.0}
    assert detail['artifacts']['policy_parameter_bundle']['by_origin'][0]['selection_summary']['selection_method'] == 'inner_validation_grid_search_v1'
    assert detail['artifacts']['policy_parameter_bundle']['by_origin'][0]['selection_summary']['selected_fold_count'] > 0
    assert detail['artifacts']['policy_parameter_bundle']['by_origin'][0]['selection_summary']['candidate_count'] >= 1
    assert detail['artifacts']['utility_parameter_bundle']['by_origin'][0]['selection_summary']['selection_method'] == 'inner_validation_grid_search_v1'
    assert detail['artifacts']['utility_parameter_bundle']['by_origin'][0]['selection_summary']['selected_fold_count'] > 0
    assert detail['artifacts']['utility_parameter_bundle']['by_origin'][0]['selection_summary']['selection_source'] == 'inner_validation'
    assert detail['artifacts']['execution_assumption_bundle']['execution_assumption_version'] == detail['execution_assumption_version']
    assert detail['artifacts']['execution_assumption_bundle']['hold_window_sec'] == 900
    assert detail['artifacts']['execution_assumption_bundle']['intrabar_rebalance_allowed'] is False
    assert detail['artifacts']['candidate_set_bundle']['candidate_set_ref'] == run['candidate_set_ref']
    assert detail['artifacts']['candidate_set_bundle']['multiple_comparison_version'] == detail['multiple_comparison_version']
    assert detail['artifacts']['candidate_set_bundle']['frozen_before_outer_test'] is True
    assert detail['artifacts']['candidate_set_bundle']['challenger']['model_family'] == run['model_family']
    assert detail['artifacts']['candidate_set_bundle']['candidate_count'] == 4
    assert detail['artifacts']['candidate_set_bundle']['candidate_models'][0]['candidate_kind'] == 'challenger'
    assert len(detail['artifacts']['candidate_set_bundle']['candidate_models']) == 4
    assert detail['artifacts']['candidate_set_bundle']['retained_model_rule'] == 'best_relative_stationary_block_ci_v1'
    assert rolling_origin['origins'][0]['forecast_generation']['feature_source'] == 'research_second_states'
    assert rolling_origin['origins'][0]['forecast_generation']['input_window_shape'][0] == 7200
    assert rolling_origin['origins'][0]['forecast_generation']['sample_count'] == 32
    assert detail['weight_fit_ref'] == f"artifact://training-run/{run['run_id']}/weight-fit-by-origin.json"
    assert detail['artifacts']['weight_fit_bundle']['weight_fit_ref'] == detail['weight_fit_ref']
    assert detail['artifacts']['weight_fit_bundle']['by_origin']
    assert 'weight_fit' in detail['artifacts']['weight_fit_bundle']['by_origin'][0]
    assert detail['artifacts']['baseline_result']['baselines']
    assert (
        detail['artifacts']['baseline_result']['baselines'][0]['aggregate']['forecast_metrics']['joint_nll']['mean']
        > detail['artifacts']['forecast_metrics']['joint_nll']['mean']
    )
    assert 'net_return' in detail['artifacts']['baseline_result']['baselines'][0]['aggregate']['decision_metrics']
    assert 'max_drawdown' in detail['artifacts']['baseline_result']['baselines'][0]['aggregate']['decision_metrics']
    assert rolling_origin['evaluation_protocol_version'] == 'rolling_origin_v1'
    assert rolling_origin['origins']
    assert 'split' in rolling_origin['origins'][0]
    assert 'weighting' in rolling_origin['origins'][0]
    assert 'forecast_metrics' in rolling_origin['origins'][0]
    assert 'decision_metrics' in rolling_origin['origins'][0]
    assert 'net_return' in rolling_origin['origins'][0]['decision_metrics']
    assert 'max_drawdown' in rolling_origin['origins'][0]['decision_metrics']
    assert 'hit_rate' in rolling_origin['origins'][0]['decision_metrics']
    assert 'exposure_rate' in rolling_origin['origins'][0]['decision_metrics']
    assert 'downside_tail_risk' in rolling_origin['origins'][0]['decision_metrics']
    baseline_origin = detail['artifacts']['baseline_result']['baselines'][0]['origins'][0]
    expected_delta_mean = _build_decimal_delta_mean(
        challenger_scores=rolling_origin['origins'][0]['forecast_score_sequence'],
        baseline_scores=baseline_origin['forecast_score_sequence'],
    )
    assert (
        rolling_origin['origins'][0]['n_eff_summary']['sequences']['model_comparison_delta_sequence']['value_summary']['mean']
        == expected_delta_mean
    )
    assert 'net_return' in detail['artifacts']['decision_metrics']
    assert 'max_drawdown' in detail['artifacts']['decision_metrics']
    assert 'turnover_mean' in detail['artifacts']['decision_metrics']
    assert 'hit_rate' in detail['artifacts']['decision_metrics']
    assert 'exposure_rate' in detail['artifacts']['decision_metrics']
    assert 'downside_tail_risk' in detail['artifacts']['decision_metrics']
    assert detail['artifacts']['comparison_result']['best_candidate_id']
    assert detail['artifacts']['comparison_result']['reference_candidate_id']
    assert detail['artifacts']['comparison_result']['candidate_ranking']
    assert detail['artifacts']['comparison_result']['pairwise_results']
    assert detail['artifacts']['comparison_result']['data_snooping_control']['candidate_set_locked_before_outer_test'] is True


def test_training_run_detail_comparison_uses_locked_baseline_origin_scores(
    storage,
    training_service,
    dataset_manifest,
):
    _seed_training_second_windows(storage)
    run = training_service.start_training_run(
        {
            'dataset_id': dataset_manifest['dataset_id'],
            'candidate_set_ref': 'artifact://candidate-set/locked-v1.json',
            'model_family': 'joint_density_model_v1',
            'model_spec_ref': 'model://joint_density_model_v1/defaults',
            'training_seed': 7,
        }
    )

    detail = training_service.get_training_run_detail(run['run_id'])
    rolling_origins = detail['artifacts']['rolling_origin_evaluation']['origins']
    baseline = detail['artifacts']['baseline_result']['baselines'][0]
    comparison = detail['artifacts']['comparison_result']
    expected_delta = [
        float(challenger_origin['forecast_metrics']['joint_nll'])
        - float(baseline_origin['forecast_metrics']['joint_nll'])
        for challenger_origin, baseline_origin in zip(rolling_origins, baseline['origins'])
    ]

    unconditional_pair = next(
        pair
        for pair in comparison['pairwise_results']
        if pair['candidate_id'] == baseline['baseline_id']
    )

    assert comparison['baseline_id'] == baseline['baseline_id']
    assert comparison['best_candidate_id'] == comparison['reference_candidate_id']
    assert comparison['best_candidate_id'] == comparison['candidate_ranking'][0]['candidate_id']
    assert comparison['best_candidate_id'] in comparison['retained_model_set']
    assert unconditional_pair['reference_candidate_id'] == comparison['best_candidate_id']
    if comparison['best_candidate_id'] == run['model_family']:
        assert unconditional_pair['delta_by_origin'] == [-delta for delta in expected_delta]


def _build_decimal_delta_mean(
    *,
    challenger_scores: list[float],
    baseline_scores: list[float],
) -> float:
    deltas = [
        Decimal(str(challenger_score)) - Decimal(str(baseline_score))
        for challenger_score, baseline_score in zip(challenger_scores, baseline_scores)
    ]
    return float(sum(deltas) / len(deltas))
