from __future__ import annotations

from .diagnostic_mmd import run_mmd_check
from .diagnostic_propensity import run_propensity_check
from .shift_state import parse_shift_state_blob
from .strata_fit import fit_census_strata_cutpoints
from .strata import build_strata_key, build_strata_v1


def run_shift_diagnostics(
    *,
    labeled_shift_rows: list[dict[str, object]],
    census_shift_rows: list[dict[str, object]],
    version: str,
) -> dict[str, object]:
    fit_cutpoints = fit_census_strata_cutpoints(census_shift_rows)
    support_overlap = _evaluate_support_overlap(
        labeled_shift_rows=labeled_shift_rows,
        census_shift_rows=census_shift_rows,
        fit_cutpoints=fit_cutpoints,
    )
    mmd_test = run_mmd_check(
        labeled_shift_rows=labeled_shift_rows,
        census_shift_rows=census_shift_rows,
    )
    propensity_check = run_propensity_check(
        labeled_shift_rows=labeled_shift_rows,
        census_shift_rows=census_shift_rows,
    )
    overall_status = _resolve_overall_status(
        support_overlap=support_overlap,
        mmd_test=mmd_test,
        propensity_check=propensity_check,
    )
    return {
        'version': version,
        'overall_status': overall_status,
        'dataset_status': 'ready' if overall_status == 'acceptable' else 'research_only',
        'checks': {
            'support_overlap': support_overlap,
            'mmd_test': mmd_test,
            'propensity_check': propensity_check,
        },
    }
def _evaluate_support_overlap(
    *,
    labeled_shift_rows: list[dict[str, object]],
    census_shift_rows: list[dict[str, object]],
    fit_cutpoints: dict[str, list[float]],
) -> dict[str, object]:
    labeled_keys = _build_strata_keys_from_labeled(labeled_shift_rows, fit_cutpoints)
    census_keys = _build_strata_keys_from_census(census_shift_rows, fit_cutpoints)
    missing_keys = sorted(census_keys - labeled_keys)
    return {
        'status': 'ok' if census_keys and not missing_keys else 'gap_detected',
        'missing_strata_keys': missing_keys,
        'labeled_strata_count': len(labeled_keys),
        'census_strata_count': len(census_keys),
    }


def _build_strata_keys_from_labeled(
    labeled_shift_rows: list[dict[str, object]],
    fit_cutpoints: dict[str, list[float]],
) -> set[str]:
    return {
        build_strata_key(
            build_strata_v1(
                shift_state=row['shift_state'],
                fit_cutpoints=fit_cutpoints,
            )
        )
        for row in labeled_shift_rows
    }


def _build_strata_keys_from_census(
    census_shift_rows: list[dict[str, object]],
    fit_cutpoints: dict[str, list[float]],
) -> set[str]:
    return {
        build_strata_key(
            build_strata_v1(
                shift_state=parse_shift_state_blob(row),
                fit_cutpoints=fit_cutpoints,
            )
        )
        for row in census_shift_rows
    }


def _resolve_overall_status(
    *,
    support_overlap: dict[str, object],
    mmd_test: dict[str, object],
    propensity_check: dict[str, object],
) -> str:
    if (
        support_overlap['status'] == 'ok'
        and mmd_test['status'] == 'acceptable'
        and propensity_check['status'] == 'acceptable'
    ):
        return 'acceptable'
    return 'failed'
