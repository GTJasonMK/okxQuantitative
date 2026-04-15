from __future__ import annotations

from app.core.research_platform.training.splits import (
    OUTER_ORIGIN_SELECTION_POLICY,
    build_blocked_temporal_hv_v1,
    count_outer_origin_candidates,
)
from app.core.research_platform.training.weighting import compute_strata_ratio_weights
from app.core.research_platform.training.weighting import fit_logistic_density_ratio_oof

from .fit_artifact_failures import all_entries_materialized
from .fit_artifact_failures import build_failed_origin_entry
from .fit_artifact_failures import build_unavailable_fit_artifacts
from .fit_artifact_rows import build_classifier_rows
from .fit_artifact_rows import build_strata_key_from_census
from .fit_artifact_rows import build_strata_key_from_row
from .fit_artifact_rows import select_fit_rows
from .fit_artifact_rows import select_origin_census_rows
from .strata_fit import fit_census_strata_cutpoints


FIT_SCOPE = 'dataset_outer_origins'
ORIGIN_FIT_SCOPE = 'outer_origin_pre_origin_fit'
STRATA_KEY_FIELDS = (
    'tod_bucket_6h',
    'weekend_flag',
    'rv_2h_bin_3',
    'liquidity_bin_3',
)


def build_dataset_fit_artifact_preview(
    *,
    manifest: dict[str, object],
    qualified_rows: list[dict[str, object]],
    census_rows: list[dict[str, object]],
) -> dict[str, object]:
    origin_splits = _build_origin_splits(manifest=manifest, qualified_rows=qualified_rows)
    if not origin_splits:
        return build_unavailable_fit_artifacts(
            fit_scope=FIT_SCOPE,
            manifest=manifest,
            reason='dataset_outer_origin_split_empty',
        )
    strata_entries = _build_strata_entries(
        manifest=manifest,
        qualified_rows=qualified_rows,
        census_rows=census_rows,
        origin_splits=origin_splits,
    )
    if str(manifest['weighting_version']) == 'classifier_density_ratio_weighting':
        return _build_classifier_artifacts(
            manifest=manifest,
            qualified_rows=qualified_rows,
            census_rows=census_rows,
            strata_entries=strata_entries,
            origin_splits=origin_splits,
        )
    return {
        'strata_fit_bundle': _build_strata_fit_bundle(manifest=manifest, strata_entries=strata_entries),
        'weight_fit_bundle': _build_weight_fit_bundle(
            manifest=manifest,
            origin_entries=_build_strata_weight_entries(
                manifest=manifest,
                qualified_rows=qualified_rows,
                census_rows=census_rows,
                origin_splits=origin_splits,
            ),
        ),
        'domain_classifier_fit_bundle': None,
    }


def _build_origin_splits(
    *,
    manifest: dict[str, object],
    qualified_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    decision_ts = [int(row['decision_ts']) for row in qualified_rows]
    outer_origin_count = count_outer_origin_candidates(
        decision_ts=decision_ts,
        embargo_sec=int(manifest['embargo_sec']),
    )
    return build_blocked_temporal_hv_v1(
        decision_ts=decision_ts,
        embargo_sec=int(manifest['embargo_sec']),
        outer_origin_count=outer_origin_count,
    )


def _build_strata_entries(
    *,
    manifest: dict[str, object],
    qualified_rows: list[dict[str, object]],
    census_rows: list[dict[str, object]],
    origin_splits: list[dict[str, object]],
) -> list[dict[str, object]]:
    entries = []
    for split_row in origin_splits:
        fit_rows = select_fit_rows(qualified_rows, split_row=split_row)
        origin_census_rows = select_origin_census_rows(census_rows, split_row=split_row)
        fit_cutpoints = fit_census_strata_cutpoints(origin_census_rows)
        entries.append(
            {
                'origin_ts': int(split_row['origin_ts']),
                'fit_scope': ORIGIN_FIT_SCOPE,
                'pre_origin_fit_end_ts': int(split_row['pre_origin_fit_end_ts']),
                'census_window_end_ts': int(split_row['census_window_end_ts']),
                'source_sample_count': len(fit_rows),
                'target_census_count': len(origin_census_rows),
                'fit_cutpoints': fit_cutpoints,
                'strata_definition_version': str(manifest['strata_definition_version']),
                'shift_state_definition_version': str(manifest['shift_state_definition_version']),
            }
        )
    return entries


def _build_classifier_artifacts(
    *,
    manifest: dict[str, object],
    qualified_rows: list[dict[str, object]],
    census_rows: list[dict[str, object]],
    strata_entries: list[dict[str, object]],
    origin_splits: list[dict[str, object]],
) -> dict[str, object]:
    weight_entries = []
    classifier_entries = []
    for split_row in origin_splits:
        fit_rows = select_fit_rows(qualified_rows, split_row=split_row)
        origin_census_rows = select_origin_census_rows(census_rows, split_row=split_row)
        try:
            result = fit_logistic_density_ratio_oof(
                rows=build_classifier_rows(
                    origin_ts=int(split_row['origin_ts']),
                    fit_rows=fit_rows,
                    census_rows=origin_census_rows,
                )
            )
        except ValueError as exc:
            weight_entries.append(
                build_failed_origin_entry(
                    fit_scope=ORIGIN_FIT_SCOPE,
                    split_row=split_row,
                    fit_rows=fit_rows,
                    census_rows=origin_census_rows,
                    reason=str(exc),
                )
            )
            classifier_entries.append(
                build_failed_origin_entry(
                    fit_scope=ORIGIN_FIT_SCOPE,
                    split_row=split_row,
                    fit_rows=fit_rows,
                    census_rows=origin_census_rows,
                    reason=str(exc),
                )
            )
            continue
        origin_key = str(split_row['origin_ts'])
        weight_entries.append(
            {
                'origin_ts': int(split_row['origin_ts']),
                'materialized': True,
                'fit_scope': ORIGIN_FIT_SCOPE,
                'source_sample_count': len(fit_rows),
                'target_census_count': len(origin_census_rows),
                'weight_fit': dict(result['weight_fit'][origin_key]),
            }
        )
        classifier_entries.append(
            {
                'origin_ts': int(split_row['origin_ts']),
                'materialized': True,
                'fit_scope': ORIGIN_FIT_SCOPE,
                'source_sample_count': len(fit_rows),
                'target_census_count': len(origin_census_rows),
                'fold_protocol': str(result['fold_protocol']),
                'domain_classifier_fit': dict(result['domain_classifier_fit'][origin_key]),
            }
        )
    return {
        'strata_fit_bundle': _build_strata_fit_bundle(manifest=manifest, strata_entries=strata_entries),
        'weight_fit_bundle': _build_weight_fit_bundle(manifest=manifest, origin_entries=weight_entries),
        'domain_classifier_fit_bundle': _build_domain_classifier_fit_bundle(
            manifest=manifest,
            origin_entries=classifier_entries,
        ),
    }


def _build_strata_weight_entries(
    *,
    manifest: dict[str, object],
    qualified_rows: list[dict[str, object]],
    census_rows: list[dict[str, object]],
    origin_splits: list[dict[str, object]],
) -> list[dict[str, object]]:
    entries = []
    for split_row in origin_splits:
        fit_rows = select_fit_rows(qualified_rows, split_row=split_row)
        origin_census_rows = select_origin_census_rows(census_rows, split_row=split_row)
        fit_cutpoints = fit_census_strata_cutpoints(origin_census_rows)
        result = compute_strata_ratio_weights(
            dataset_strata=[
                build_strata_key_from_row(row, fit_cutpoints=fit_cutpoints)
                for row in fit_rows
            ],
            census_strata=[
                build_strata_key_from_census(row, fit_cutpoints=fit_cutpoints)
                for row in origin_census_rows
            ],
            estimator_version=str(manifest['weight_estimator_version']),
            definition_version=str(manifest['weight_definition']),
        )
        entries.append(
            {
                'origin_ts': int(split_row['origin_ts']),
                'materialized': True,
                'fit_scope': ORIGIN_FIT_SCOPE,
                'source_sample_count': len(fit_rows),
                'target_census_count': len(origin_census_rows),
                'support_overlap_result': str(result['support_overlap_result']),
                'dataset_status': str(result['dataset_status']),
                'weight_fit': dict(result['weight_fit']),
            }
        )
    return entries


def _build_strata_fit_bundle(
    *,
    manifest: dict[str, object],
    strata_entries: list[dict[str, object]],
) -> dict[str, object]:
    return {
        'strata_fit_ref': str(manifest['strata_fit_ref']),
        'materialized': True,
        'fit_scope': FIT_SCOPE,
        'origin_selection_policy': OUTER_ORIGIN_SELECTION_POLICY,
        'origin_count': len(strata_entries),
        'strata_definition_version': str(manifest['strata_definition_version']),
        'shift_state_definition_version': str(manifest['shift_state_definition_version']),
        'strata_key_fields': list(STRATA_KEY_FIELDS),
        'by_origin': strata_entries,
    }


def _build_weight_fit_bundle(
    *,
    manifest: dict[str, object],
    origin_entries: list[dict[str, object]],
) -> dict[str, object]:
    return {
        'weight_fit_ref': str(manifest['weight_fit_ref']),
        'materialized': all_entries_materialized(origin_entries),
        'fit_scope': FIT_SCOPE,
        'origin_selection_policy': OUTER_ORIGIN_SELECTION_POLICY,
        'origin_count': len(origin_entries),
        'weighting_version': str(manifest['weighting_version']),
        'weight_estimator_version': str(manifest['weight_estimator_version']),
        'weight_definition': str(manifest['weight_definition']),
        'by_origin': origin_entries,
    }


def _build_domain_classifier_fit_bundle(
    *,
    manifest: dict[str, object],
    origin_entries: list[dict[str, object]],
) -> dict[str, object]:
    return {
        'domain_classifier_fit_ref': str(manifest['domain_classifier_fit_ref']),
        'materialized': all_entries_materialized(origin_entries),
        'fit_scope': FIT_SCOPE,
        'origin_selection_policy': OUTER_ORIGIN_SELECTION_POLICY,
        'origin_count': len(origin_entries),
        'domain_classifier_version': str(manifest['domain_classifier_version']),
        'by_origin': origin_entries,
    }
