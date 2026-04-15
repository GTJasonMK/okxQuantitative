from __future__ import annotations


def build_unavailable_fit_artifacts(
    *,
    fit_scope: str,
    manifest: dict[str, object],
    reason: str,
) -> dict[str, object]:
    return {
        'strata_fit_bundle': build_failed_bundle(
            fit_scope=fit_scope,
            ref_key='strata_fit_ref',
            manifest=manifest,
            reason=reason,
        ),
        'weight_fit_bundle': build_failed_bundle(
            fit_scope=fit_scope,
            ref_key='weight_fit_ref',
            manifest=manifest,
            reason=reason,
        ),
        'domain_classifier_fit_bundle': None if not manifest.get('domain_classifier_fit_ref') else build_failed_bundle(
            fit_scope=fit_scope,
            ref_key='domain_classifier_fit_ref',
            manifest=manifest,
            reason=reason,
        ),
    }


def build_failed_bundle(
    *,
    fit_scope: str,
    ref_key: str,
    manifest: dict[str, object],
    reason: str,
) -> dict[str, object]:
    return {
        ref_key: str(manifest.get(ref_key, '')),
        'materialized': False,
        'fit_scope': fit_scope,
        'failure_reason': reason,
    }


def build_failed_origin_entry(
    *,
    fit_scope: str,
    split_row: dict[str, object],
    fit_rows: list[dict[str, object]],
    census_rows: list[dict[str, object]],
    reason: str,
) -> dict[str, object]:
    return {
        'origin_ts': int(split_row['origin_ts']),
        'materialized': False,
        'fit_scope': fit_scope,
        'source_sample_count': len(fit_rows),
        'target_census_count': len(census_rows),
        'failure_reason': reason,
    }


def all_entries_materialized(entries: list[dict[str, object]]) -> bool:
    return all(bool(entry.get('materialized', True)) for entry in entries)
