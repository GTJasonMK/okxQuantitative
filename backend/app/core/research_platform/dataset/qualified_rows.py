from __future__ import annotations

from app.core.research_platform.census.constants import INDEPENDENT_CENSUS_SOURCE_KIND

from .shift_state import build_labeled_shift_row


def load_qualified_rows(
    storage,
    protocol_bundle: dict[str, object],
) -> tuple[list[dict[str, object]], list[dict[str, object]]]:
    session_ids = [str(session_id) for session_id in protocol_bundle['included_session_ids']]
    samples = storage.list_research_sample_index_15m_for_sessions(session_ids)
    targets = storage.list_research_boundary_targets_15m_for_sessions(session_ids)
    if not samples or not targets:
        return [], []
    inst_id = resolve_inst_id(samples)
    census_rows = _load_eligible_census_rows(storage, inst_id=inst_id, protocol_bundle=protocol_bundle)
    return _join_qualified_rows(samples, targets, census_rows, protocol_bundle), census_rows


def _load_eligible_census_rows(
    storage,
    *,
    inst_id: str,
    protocol_bundle: dict[str, object],
) -> list[dict[str, object]]:
    census_rows = storage.list_research_target_census_for_inst(inst_id)
    return [
        row
        for row in census_rows
        if _census_row_matches_protocol(row, protocol_bundle=protocol_bundle)
    ]


def _join_qualified_rows(
    samples: list[dict[str, object]],
    targets: list[dict[str, object]],
    census_rows: list[dict[str, object]],
    protocol_bundle: dict[str, object],
) -> list[dict[str, object]]:
    target_map = {(row['session_id'], row['decision_ts']): row for row in targets}
    census_map = {int(row['decision_ts']): row for row in census_rows}
    qualified_rows = []
    for sample_row in samples:
        joined_row = _build_joined_row(
            sample_row=sample_row,
            target_row=target_map.get((sample_row['session_id'], sample_row['decision_ts'])),
            census_row=census_map.get(int(sample_row['decision_ts'])),
            protocol_bundle=protocol_bundle,
        )
        if joined_row is not None:
            qualified_rows.append(joined_row)
    qualified_rows.sort(key=lambda row: int(row['decision_ts']))
    return qualified_rows


def _build_joined_row(
    *,
    sample_row: dict[str, object],
    target_row: dict[str, object] | None,
    census_row: dict[str, object] | None,
    protocol_bundle: dict[str, object],
) -> dict[str, object] | None:
    if not _sample_row_is_training_ready(sample_row):
        return None
    if target_row is None or census_row is None:
        return None
    if not _target_row_matches_protocol(target_row, protocol_bundle=protocol_bundle):
        return None
    labeled_row = build_labeled_shift_row(
        sample_row=sample_row,
        target_row=target_row,
        census_row=census_row,
    )
    return {
        **labeled_row,
        'r_open': float(target_row['r_open']),
        'u': float(target_row['u']),
        'd': float(target_row['d']),
        'target_row': dict(target_row),
        'census_row': dict(census_row),
    }


def _sample_row_is_training_ready(sample_row: dict[str, object]) -> bool:
    return (
        int(sample_row['sample_valid']) == 1
        and int(sample_row['ready_for_training']) == 1
    )


def _target_row_matches_protocol(
    target_row: dict[str, object],
    *,
    protocol_bundle: dict[str, object],
) -> bool:
    return (
        int(target_row['label_complete']) == 1
        and str(target_row['label_definition_version'])
        == str(protocol_bundle['label_definition_version'])
    )


def _census_row_matches_protocol(
    census_row: dict[str, object],
    *,
    protocol_bundle: dict[str, object],
) -> bool:
    return (
        int(census_row['deployment_eligible']) == 1
        and str(census_row.get('observation_source_kind', '')) == INDEPENDENT_CENSUS_SOURCE_KIND
        and str(census_row['census_policy_version'])
        == str(protocol_bundle['target_census_policy_version'])
        and str(census_row['shift_state_definition_version'])
        == str(protocol_bundle['shift_state_definition_version'])
    )


def resolve_inst_id(samples: list[dict[str, object]]) -> str:
    inst_ids = {str(sample['inst_id']) for sample in samples}
    if len(inst_ids) != 1:
        raise ValueError('dataset manifest requires exactly one inst_id across included sessions')
    return next(iter(inst_ids))
