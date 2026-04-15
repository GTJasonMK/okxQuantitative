from __future__ import annotations

import time

from app.core.research_platform.artifact_store import (
    load_dataset_fit_artifacts,
    save_dataset_fit_artifacts,
)
from app.core.research_platform_delete_errors import DatasetDeleteBlockedError
from app.core.research_platform.protocol_registry import (
    PROTOCOL_FIELD_NAMES,
    validate_protocol_bundle,
)

from .diagnostics import run_shift_diagnostics
from .effective_size import build_effective_size_summary
from .fit_artifacts import build_dataset_fit_artifact_preview
from .manifest import (
    build_dataset_manifest,
    create_dataset_id,
    deserialize_manifest,
    serialize_manifest,
    validate_weighting_preconditions,
)
from .qualified_rows import load_qualified_rows, resolve_inst_id
from .shift_state import build_boundary_regime_schema
from .splitting import build_dataset_splits


class ResearchDatasetService:
    def __init__(self, *, storage):
        self._storage = storage

    def create_dataset_manifest(self, payload: dict[str, object]) -> dict[str, object]:
        validate_protocol_bundle(scope='dataset_manifest', payload=payload)
        dataset_id = create_dataset_id(payload)
        source_samples = self._list_sample_rows(payload)
        labeled_rows, census_rows = self._load_joined_rows(payload)
        split_rows = build_dataset_splits(
            labeled_rows=labeled_rows,
            embargo_sec=int(payload['embargo_sec']),
            sampling_stride_sec=int(payload['sampling_stride_sec']),
        )
        effective_size_summary = build_effective_size_summary(
            train_rows=split_rows['train'],
            val_rows=split_rows['val'],
            test_rows=split_rows['test'],
        )
        shift_diagnostic_result = run_shift_diagnostics(
            labeled_shift_rows=split_rows['train'],
            census_shift_rows=census_rows,
            version=str(payload['shift_diagnostic_version']),
        )
        validate_weighting_preconditions(
            payload=payload,
            shift_diagnostic_result=shift_diagnostic_result,
        )
        manifest = build_dataset_manifest(
            payload=payload,
            stats=_build_manifest_stats(
                dataset_id=dataset_id,
                inst_id=resolve_inst_id(source_samples),
                census_rows=census_rows,
                split_rows=split_rows,
                effective_size_summary=effective_size_summary,
                shift_diagnostic_result=shift_diagnostic_result,
                weighting_version=str(payload['weighting_version']),
                domain_classifier_version=str(payload['domain_classifier_version']),
            ),
        )
        fit_artifacts = build_dataset_fit_artifact_preview(
            manifest=manifest,
            qualified_rows=labeled_rows,
            census_rows=census_rows,
        )
        self._storage.save_research_dataset_manifest(**serialize_manifest(manifest))
        save_dataset_fit_artifacts(
            storage=self._storage,
            manifest=manifest,
            fit_artifacts=fit_artifacts,
        )
        return manifest

    def list_dataset_manifests(self, *, limit: int = 50) -> list[dict[str, object]]:
        rows = self._storage.list_research_dataset_manifests(limit=limit)
        return [deserialize_manifest(row) for row in rows]

    def get_dataset_manifest(self, dataset_id: str) -> dict[str, object] | None:
        return deserialize_manifest(self._storage.get_research_dataset_manifest(dataset_id))

    def get_dataset_protocol_validation_status(self, dataset_id: str) -> str:
        manifest = self.get_dataset_manifest(dataset_id)
        if manifest is None:
            return 'missing'
        try:
            validate_protocol_bundle(
                scope='dataset_manifest',
                payload={field: manifest[field] for field in PROTOCOL_FIELD_NAMES},
            )
        except ValueError:
            return 'invalid'
        return 'ok'

    def get_dataset_split_summary(self, dataset_id: str) -> dict[str, object]:
        manifest = self._require_manifest(dataset_id)
        return {
            'train_sample_count': manifest['train_sample_count'],
            'val_sample_count': manifest['val_sample_count'],
            'test_sample_count': manifest['test_sample_count'],
            'embargo_sec': manifest['embargo_sec'],
        }

    def get_dataset_weight_summary(self, dataset_id: str) -> dict[str, object]:
        manifest = self._require_manifest(dataset_id)
        return {
            'weighting_version': manifest['weighting_version'],
            'weight_definition': manifest['weight_definition'],
            'weight_estimator_version': manifest['weight_estimator_version'],
            'weight_fit_ref': manifest['weight_fit_ref'],
            'domain_classifier_fit_ref': manifest['domain_classifier_fit_ref'],
        }

    def get_dataset_regime_schema(self, dataset_id: str) -> dict[str, object]:
        self._require_manifest(dataset_id)
        return build_boundary_regime_schema()

    def get_dataset_effective_size_summary(self, dataset_id: str) -> dict[str, object]:
        manifest = self._require_manifest(dataset_id)
        return _build_effective_size_preview(manifest)

    def get_dataset_shift_diagnostic_preview(self, dataset_id: str) -> dict[str, object]:
        manifest = self._require_manifest(dataset_id)
        return manifest['shift_diagnostic_result']

    def get_dataset_fit_artifact_preview(self, dataset_id: str) -> dict[str, object]:
        manifest = self._require_manifest(dataset_id)
        return load_dataset_fit_artifacts(
            storage=self._storage,
            manifest=manifest,
        )

    def get_dataset_shift_diagnostics_bundle(self, dataset_id: str) -> dict[str, object]:
        manifest = self._require_manifest(dataset_id)
        return {
            'weighting_version': manifest['weighting_version'],
            'diagnostic_scope': 'shift_only_preview',
            'shift_diagnostic_result': manifest['shift_diagnostic_result'],
        }

    def delete_dataset_manifest(self, dataset_id: str) -> dict[str, object] | None:
        manifest = self.get_dataset_manifest(dataset_id)
        if manifest is None:
            return None
        blocking_run_ids = self._storage.list_research_training_run_ids_for_dataset(dataset_id)
        if blocking_run_ids:
            raise DatasetDeleteBlockedError.referenced_by_training_runs(
                dataset_id,
                blocking_run_ids,
            )
        return self._storage.delete_research_dataset_manifest(dataset_id)

    def _load_joined_rows(
        self,
        payload: dict[str, object],
    ) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
        sample_rows = self._list_sample_rows(payload)
        target_rows = self._storage.list_research_boundary_targets_15m_for_sessions(
            _included_session_ids(payload),
        )
        if not sample_rows or not target_rows:
            raise ValueError('dataset manifest requires sample index and boundary targets')
        labeled_rows, census_rows = load_qualified_rows(self._storage, payload)
        return labeled_rows, census_rows

    def _require_manifest(self, dataset_id: str) -> dict[str, object]:
        manifest = self.get_dataset_manifest(dataset_id)
        if manifest is None:
            raise ValueError(f'unknown dataset manifest: {dataset_id}')
        return manifest

    def _list_sample_rows(self, payload: dict[str, object]) -> list[dict[str, object]]:
        return self._storage.list_research_sample_index_15m_for_sessions(
            _included_session_ids(payload),
        )


def _build_manifest_stats(
    *,
    dataset_id: str,
    inst_id: str,
    census_rows: list[dict[str, object]],
    split_rows: dict[str, list[dict[str, object]]],
    effective_size_summary: dict[str, object],
    shift_diagnostic_result: dict[str, object],
    weighting_version: str,
    domain_classifier_version: str,
) -> dict[str, object]:
    estimates = effective_size_summary['sequence_definitions']['label_r_close_sequence']['estimates']
    return {
        'dataset_id': dataset_id,
        'inst_id': inst_id,
        'strata_fit_ref': f'artifact://dataset/{dataset_id}/strata-fit-by-origin.json',
        'weight_fit_ref': f'artifact://dataset/{dataset_id}/weight-fit-by-origin.json',
        'domain_classifier_fit_ref': _resolve_domain_classifier_fit_ref(
            dataset_id=dataset_id,
            weighting_version=weighting_version,
            domain_classifier_version=domain_classifier_version,
        ),
        'dataset_status': shift_diagnostic_result['dataset_status'],
        'shift_diagnostic_result': shift_diagnostic_result,
        'target_census_count': len(census_rows),
        'support_overlap_result': shift_diagnostic_result['checks']['support_overlap']['status'],
        'train_sample_count': len(split_rows['train']),
        'val_sample_count': len(split_rows['val']),
        'test_sample_count': len(split_rows['test']),
        'train_effective_sample_size': estimates['train'],
        'val_effective_sample_size': estimates['val'],
        'test_effective_sample_size': estimates['test'],
        'created_at': float(time.time()),
    }


def _resolve_domain_classifier_fit_ref(
    *,
    dataset_id: str,
    weighting_version: str,
    domain_classifier_version: str,
) -> str:
    if weighting_version != 'classifier_density_ratio_weighting' or not domain_classifier_version:
        return ''
    return f'artifact://dataset/{dataset_id}/domain-classifier-fit-by-origin.json'


def _build_effective_size_preview(manifest: dict[str, object]) -> dict[str, object]:
    return {
        'truncation_rule': 'initial_positive_sequence_v1',
        'sequence_definitions': {
            'primary_validation_score_sequence': {
                'materialized_in_stage': 'training_run',
                'sequence_role': 'model_selection_objective',
            },
            'label_r_close_sequence': {
                'field_name': 'r_close',
                'materialized_in_stage': 'dataset_manifest',
                'sequence_role': 'data_dependence_proxy',
                'estimates': {
                    'train': manifest['train_effective_sample_size'],
                    'val': manifest['val_effective_sample_size'],
                    'test': manifest['test_effective_sample_size'],
                },
            },
            'model_comparison_delta_sequence': {
                'materialized_in_stage': 'training_run',
                'sequence_role': 'pairwise_model_difference',
            },
        },
    }


def _included_session_ids(payload: dict[str, object]) -> list[str]:
    return [str(session_id) for session_id in payload['included_session_ids']]
