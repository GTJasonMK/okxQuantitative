from __future__ import annotations

import time

from app.core.research_platform.artifact_store import (
    load_training_artifacts,
    save_training_artifacts,
)
from app.core.research_platform.dataset.qualified_rows import load_qualified_rows

from .artifacts import build_training_artifacts
from .artifacts import build_split_artifact
from .protocols import (
    validate_model_output_contract,
    validate_training_candidate_request,
    validate_training_protocol_bundle,
)


class ResearchTrainingService:
    def __init__(self, *, storage, dataset_service):
        self._storage = storage
        self._dataset_service = dataset_service

    def start_training_run(self, payload: dict[str, object]) -> dict[str, object]:
        manifest = self._dataset_service.get_dataset_manifest(str(payload['dataset_id']))
        if manifest is None:
            raise ValueError(f"unknown dataset manifest: {payload['dataset_id']}")
        validate_training_protocol_bundle(manifest)
        validate_model_output_contract(str(payload['model_family']))
        validate_training_candidate_request(
            candidate_set_ref=str(payload['candidate_set_ref']),
            model_family=str(payload['model_family']),
        )
        _validate_inner_validation_preconditions(
            storage=self._storage,
            manifest=manifest,
        )
        run = _build_training_run_row(payload=payload, manifest=manifest)
        return self._storage.create_research_training_run(run)

    def list_training_runs(
        self,
        *,
        dataset_id: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, object]]:
        return self._storage.list_research_training_runs(dataset_id=dataset_id, limit=limit)

    def get_training_run_detail(self, run_id: str) -> dict[str, object] | None:
        run = self._storage.get_research_training_run(run_id)
        if run is None:
            return None
        hydrated_run, artifacts = self._hydrate_training_artifacts(run)
        return {**hydrated_run, 'artifacts': artifacts}

    def _hydrate_training_artifacts(
        self,
        run: dict[str, object],
    ) -> tuple[dict[str, object], dict[str, object]]:
        stored_artifacts = load_training_artifacts(
            storage=self._storage,
            run_id=str(run['run_id']),
        )
        if stored_artifacts is not None:
            return run, stored_artifacts
        manifest = self._dataset_service.get_dataset_manifest(str(run['dataset_id']))
        if manifest is None:
            raise ValueError(f"unknown dataset manifest: {run['dataset_id']}")
        artifacts, parameter_refs = build_training_artifacts(
            storage=self._storage,
            manifest=manifest,
            run=run,
        )
        hydrated_run = {**run, **parameter_refs}
        save_training_artifacts(
            storage=self._storage,
            run=hydrated_run,
            artifacts=artifacts,
        )
        updated_run = self._storage.update_research_training_run(
            str(run['run_id']),
            **parameter_refs,
        )
        return updated_run or hydrated_run, artifacts


def _build_training_run_row(*, payload: dict[str, object], manifest: dict[str, object]) -> dict[str, object]:
    run_id = f"run-{int(time.time())}-{time.time_ns() % 100000}"
    return {
        'run_id': run_id,
        'dataset_id': manifest['dataset_id'],
        'model_family': payload['model_family'],
        'model_spec_ref': payload['model_spec_ref'],
        'candidate_set_ref': payload['candidate_set_ref'],
        'training_seed': int(payload['training_seed']),
        'status': 'queued',
        'progress_stage': 'queued',
        'failure_reason': '',
        'split_definition_version': manifest['split_definition_version'],
        'evaluation_protocol_version': manifest['evaluation_protocol_version'],
        'refit_policy_version': manifest['refit_policy_version'],
        'outer_origin_selection_policy': manifest['outer_origin_selection_policy'],
        'weighting_version': manifest['weighting_version'],
        'weight_definition': manifest['weight_definition'],
        'weight_estimator_version': manifest['weight_estimator_version'],
        'weight_fit_ref': manifest['weight_fit_ref'],
        'domain_classifier_version': manifest['domain_classifier_version'],
        'domain_classifier_fit_ref': manifest['domain_classifier_fit_ref'],
        'score_definition_version': manifest['score_definition_version'],
        'prerank_definition_version': manifest['prerank_definition_version'],
        'regime_definition_version': manifest['regime_definition_version'],
        'bootstrap_definition_version': manifest['bootstrap_definition_version'],
        'policy_definition_version': manifest['policy_definition_version'],
        'policy_parameter_ref': manifest['policy_parameter_ref'],
        'decision_utility_version': manifest['decision_utility_version'],
        'utility_parameter_ref': manifest['utility_parameter_ref'],
        'execution_assumption_version': manifest['execution_assumption_version'],
        'multiple_comparison_version': manifest['multiple_comparison_version'],
        'split_artifact_ref': f'artifact://training-run/{run_id}/split-artifact.json',
        'forecast_metrics_ref': f'artifact://training-run/{run_id}/forecast-metrics.json',
        'decision_metrics_ref': f'artifact://training-run/{run_id}/decision-metrics.json',
        'diagnostics_ref': f'artifact://training-run/{run_id}/diagnostics.json',
        'bootstrap_result_ref': f'artifact://training-run/{run_id}/bootstrap.json',
        'baseline_result_ref': f'artifact://training-run/{run_id}/baseline.json',
        'comparison_result_ref': f'artifact://training-run/{run_id}/comparison.json',
        'created_at': float(time.time()),
        'started_at': None,
        'finished_at': None,
    }


def _validate_inner_validation_preconditions(
    *,
    storage,
    manifest: dict[str, object],
) -> None:
    qualified_rows, _ = load_qualified_rows(storage, manifest)
    split_artifact = build_split_artifact(
        manifest=manifest,
        qualified_rows=qualified_rows,
    )
    if not split_artifact['origins']:
        raise ValueError('protocol-invalid: rolling-origin split produced no outer origins')
    for split_row in split_artifact['origins']:
        if _count_complete_inner_validation_folds(qualified_rows, split_row=split_row) > 0:
            continue
        raise ValueError(
            'protocol-invalid: rolling-origin split requires at least one '
            'complete inner-validation fold per origin'
        )


def _count_complete_inner_validation_folds(
    rows: list[dict[str, object]],
    *,
    split_row: dict[str, object],
) -> int:
    complete_fold_count = 0
    for fold in split_row.get('inner_validation_folds', []):
        train_rows = _select_rows_in_range(
            rows,
            start_ts=int(fold['train_start_ts']),
            end_ts=int(fold['train_end_ts']),
        )
        validation_rows = _select_rows_in_range(
            rows,
            start_ts=int(fold['validation_start_ts']),
            end_ts=int(fold['validation_end_ts']),
        )
        if train_rows and validation_rows:
            complete_fold_count += 1
    return complete_fold_count


def _select_rows_in_range(
    rows: list[dict[str, object]],
    *,
    start_ts: int,
    end_ts: int,
) -> list[dict[str, object]]:
    return [
        row
        for row in rows
        if start_ts <= int(row['decision_ts']) <= end_ts
    ]
