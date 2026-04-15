from __future__ import annotations

from typing import Any


DATASET_ARTIFACT_SPECS = (
    ('strata_fit_ref', 'strata_fit_bundle', 'dataset_strata_fit'),
    ('weight_fit_ref', 'weight_fit_bundle', 'dataset_weight_fit'),
    ('domain_classifier_fit_ref', 'domain_classifier_fit_bundle', 'dataset_domain_classifier_fit'),
)
TRAINING_ARTIFACT_SPECS = (
    ('split_artifact_ref', 'split_artifact', 'training_split_artifact'),
    ('forecast_metrics_ref', 'forecast_metrics', 'training_forecast_metrics'),
    ('decision_metrics_ref', 'decision_metrics', 'training_decision_metrics'),
    ('diagnostics_ref', 'diagnostics_bundle', 'training_diagnostics_bundle'),
    ('bootstrap_result_ref', 'bootstrap_result', 'training_bootstrap_result'),
    ('baseline_result_ref', 'baseline_result', 'training_baseline_result'),
    ('comparison_result_ref', 'comparison_result', 'training_comparison_result'),
    ('policy_parameter_ref', 'policy_parameter_bundle', 'training_policy_parameters'),
    ('utility_parameter_ref', 'utility_parameter_bundle', 'training_utility_parameters'),
    ('weight_fit_ref', 'weight_fit_bundle', 'training_weight_fit'),
    ('domain_classifier_fit_ref', 'domain_classifier_fit_bundle', 'training_domain_classifier_fit'),
)


def save_dataset_fit_artifacts(
    *,
    storage,
    manifest: dict[str, object],
    fit_artifacts: dict[str, object],
) -> None:
    for ref_key, bundle_key, artifact_kind in DATASET_ARTIFACT_SPECS:
        ref = str(manifest.get(ref_key, ''))
        bundle = fit_artifacts.get(bundle_key)
        if not ref or bundle is None:
            continue
        storage.save_research_artifact(
            artifact_ref=ref,
            artifact_kind=artifact_kind,
            payload=bundle,
        )


def load_dataset_fit_artifacts(
    *,
    storage,
    manifest: dict[str, object],
) -> dict[str, object]:
    artifacts: dict[str, object] = {}
    for ref_key, bundle_key, _ in DATASET_ARTIFACT_SPECS:
        ref = str(manifest.get(ref_key, ''))
        if not ref:
            artifacts[bundle_key] = None
            continue
        artifacts[bundle_key] = _require_payload(
            storage=storage,
            artifact_ref=ref,
        )
    return artifacts


def save_training_artifacts(
    *,
    storage,
    run: dict[str, object],
    artifacts: dict[str, object],
) -> None:
    diagnostics_bundle = {
        'weighted_diagnostics': artifacts['weighted_diagnostics'],
        'unweighted_diagnostics': artifacts['unweighted_diagnostics'],
        'regime_metrics': artifacts['regime_metrics'],
        'n_eff_summary': artifacts['n_eff_summary'],
        'rolling_origin_evaluation': artifacts['rolling_origin_evaluation'],
        'execution_assumption_bundle': artifacts['execution_assumption_bundle'],
        'candidate_set_bundle': artifacts['candidate_set_bundle'],
    }
    payloads: dict[str, Any] = {
        **artifacts,
        'diagnostics_bundle': diagnostics_bundle,
    }
    for ref_key, payload_key, artifact_kind in TRAINING_ARTIFACT_SPECS:
        ref = str(run.get(ref_key, ''))
        payload = payloads.get(payload_key)
        if not ref or payload is None:
            continue
        storage.save_research_artifact(
            artifact_ref=ref,
            artifact_kind=artifact_kind,
            payload=payload,
        )
    storage.save_research_artifact(
        artifact_ref=_training_full_artifact_ref(str(run['run_id'])),
        artifact_kind='training_full_artifacts',
        payload=artifacts,
    )


def load_training_artifacts(*, storage, run_id: str) -> dict[str, object] | None:
    row = storage.get_research_artifact(_training_full_artifact_ref(run_id))
    if row is None:
        return None
    return storage.deserialize_research_artifact(row)


def _training_full_artifact_ref(run_id: str) -> str:
    return f'artifact://training-run/{run_id}/full-artifacts.json'


def _require_payload(*, storage, artifact_ref: str) -> dict[str, object]:
    row = storage.get_research_artifact(artifact_ref)
    if row is None:
        raise ValueError(f'missing research artifact payload: {artifact_ref}')
    return storage.deserialize_research_artifact(row)
