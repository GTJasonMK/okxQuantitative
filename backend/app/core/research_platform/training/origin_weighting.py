from __future__ import annotations

from app.core.research_platform.dataset.strata_fit import fit_census_strata_cutpoints
from app.core.research_platform.dataset.shift_state import parse_shift_state_blob
from app.core.research_platform.dataset.strata import (
    build_strata_key,
    build_strata_v1,
)

from .weighting import (
    build_density_ratio_feature_row,
    compute_strata_ratio_weights,
    fit_logistic_density_ratio_oof,
    score_density_ratio_row,
)


def build_weighting_bundle(
    *,
    manifest: dict[str, object],
    origin_ts: int,
    fit_rows: list[dict[str, object]],
    test_rows: list[dict[str, object]],
    census_rows: list[dict[str, object]],
) -> tuple[dict[str, object], list[float]]:
    weighting_version = str(manifest['weighting_version'])
    if weighting_version == 'classifier_density_ratio_weighting':
        return _build_density_ratio_bundle(
            origin_ts=origin_ts,
            fit_rows=fit_rows,
            test_rows=test_rows,
            census_rows=census_rows,
        )
    return _build_strata_ratio_bundle(
        manifest=manifest,
        fit_rows=fit_rows,
        test_rows=test_rows,
        census_rows=census_rows,
    )


def build_weight_fit_bundles(
    *,
    origins: list[dict[str, object]],
    weight_fit_ref: str,
    domain_classifier_fit_ref: str,
) -> dict[str, object]:
    bundles = {
        'weight_fit_bundle': {
            'weight_fit_ref': weight_fit_ref,
            'by_origin': [
                {
                    'origin_ts': int(origin['origin_ts']),
                    'weight_fit': origin['weighting'].get('weight_fit', {}),
                }
                for origin in origins
            ],
        }
    }
    if domain_classifier_fit_ref:
        bundles['domain_classifier_fit_bundle'] = {
            'domain_classifier_fit_ref': domain_classifier_fit_ref,
            'by_origin': [
                {
                    'origin_ts': int(origin['origin_ts']),
                    'domain_classifier_fit': origin['weighting'].get('domain_classifier_fit', {}),
                }
                for origin in origins
            ],
        }
    return bundles


def _build_strata_ratio_bundle(
    *,
    manifest: dict[str, object],
    fit_rows: list[dict[str, object]],
    test_rows: list[dict[str, object]],
    census_rows: list[dict[str, object]],
) -> tuple[dict[str, object], list[float]]:
    fit_cutpoints = fit_census_strata_cutpoints(census_rows)
    dataset_strata = [_build_strata_key_from_row(row, fit_cutpoints=fit_cutpoints) for row in fit_rows]
    census_strata = [_build_strata_key_from_census(row, fit_cutpoints=fit_cutpoints) for row in census_rows]
    result = compute_strata_ratio_weights(
        dataset_strata=dataset_strata,
        census_strata=census_strata,
        estimator_version=str(manifest['weight_estimator_version']),
        definition_version=str(manifest['weight_definition']),
    )
    weights = _resolve_strata_weights(
        test_rows,
        fit_cutpoints=fit_cutpoints,
        weight_map=result['weights'],
    )
    return {'weighting_version': str(manifest['weighting_version']), **result}, weights
def _resolve_strata_weights(
    test_rows: list[dict[str, object]],
    *,
    fit_cutpoints: dict[str, list[float]],
    weight_map: dict[str, float],
) -> list[float]:
    weights = []
    missing_keys = []
    for row in test_rows:
        strata_key = _build_strata_key_from_row(row, fit_cutpoints=fit_cutpoints)
        weight = weight_map.get(strata_key)
        if weight is None:
            missing_keys.append(strata_key)
            continue
        weights.append(float(weight))
    if missing_keys:
        raise ValueError(f'missing origin weighting strata: {sorted(set(missing_keys))}')
    return weights


def _build_density_ratio_bundle(
    *,
    origin_ts: int,
    fit_rows: list[dict[str, object]],
    test_rows: list[dict[str, object]],
    census_rows: list[dict[str, object]],
) -> tuple[dict[str, object], list[float]]:
    classifier_rows = _build_classifier_rows(
        origin_ts=origin_ts,
        fit_rows=fit_rows,
        census_rows=census_rows,
    )
    result = fit_logistic_density_ratio_oof(rows=classifier_rows)
    fit = result['domain_classifier_fit'][str(origin_ts)]
    return result, [_score_density_ratio(row, fit=fit) for row in test_rows]


def _build_classifier_rows(
    *,
    origin_ts: int,
    fit_rows: list[dict[str, object]],
    census_rows: list[dict[str, object]],
) -> list[dict[str, object]]:
    rows = [_build_classifier_row(origin_ts=origin_ts, row=row, domain_label=0) for row in fit_rows]
    rows.extend(_build_classifier_row(origin_ts=origin_ts, row=row, domain_label=1) for row in census_rows)
    return rows


def _build_classifier_row(
    *,
    origin_ts: int,
    row: dict[str, object],
    domain_label: int,
) -> dict[str, object]:
    shift_state = row['shift_state'] if 'shift_state' in row else parse_shift_state_blob(row)
    decision_ts = int(row['decision_ts'])
    return {
        'origin_ts': origin_ts,
        'decision_ts': decision_ts,
        'session_id': str(row.get('session_id', f'census-{decision_ts}')),
        'domain_label': domain_label,
        **build_density_ratio_feature_row(shift_state=shift_state),
    }


def _score_density_ratio(
    row: dict[str, object],
    *,
    fit: dict[str, object],
) -> float:
    feature_row = build_density_ratio_feature_row(shift_state=row['shift_state'])
    return score_density_ratio_row(row=feature_row, fit=fit)


def _build_strata_key_from_row(
    row: dict[str, object],
    *,
    fit_cutpoints: dict[str, list[float]],
) -> str:
    return build_strata_key(
        build_strata_v1(
            shift_state=row['shift_state'],
            fit_cutpoints=fit_cutpoints,
        )
    )


def _build_strata_key_from_census(
    row: dict[str, object],
    *,
    fit_cutpoints: dict[str, list[float]],
) -> str:
    return build_strata_key(
        build_strata_v1(
            shift_state=parse_shift_state_blob(row),
            fit_cutpoints=fit_cutpoints,
        )
    )
