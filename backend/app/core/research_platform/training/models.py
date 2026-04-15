from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchTrainingRun:
    run_id: str
    dataset_id: str
    model_family: str
    model_spec_ref: str
    candidate_set_ref: str
    training_seed: int
    status: str
    progress_stage: str
    failure_reason: str
    split_definition_version: str
    evaluation_protocol_version: str
    refit_policy_version: str
    outer_origin_selection_policy: str
    weighting_version: str
    weight_definition: str
    weight_estimator_version: str
    weight_fit_ref: str
    domain_classifier_version: str
    domain_classifier_fit_ref: str
    score_definition_version: str
    prerank_definition_version: str
    regime_definition_version: str
    bootstrap_definition_version: str
    policy_definition_version: str
    policy_parameter_ref: str
    decision_utility_version: str
    utility_parameter_ref: str
    execution_assumption_version: str
    multiple_comparison_version: str
    split_artifact_ref: str
    forecast_metrics_ref: str
    decision_metrics_ref: str
    diagnostics_ref: str
    bootstrap_result_ref: str
    baseline_result_ref: str
    comparison_result_ref: str
    created_at: float
    started_at: float | None
    finished_at: float | None
