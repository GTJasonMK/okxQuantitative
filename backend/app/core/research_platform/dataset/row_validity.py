from __future__ import annotations

from app.core.data_center_collection.integrity_policy import get_integrity_policy

LABEL_PRICE_FIELDS = ('open_price', 'high_price', 'low_price', 'close_price')


def row_is_strictly_valid(row: dict[str, object]) -> bool:
    policy = get_integrity_policy(str(row.get('integrity_policy_version', 'strict_v1')))
    if int(row.get('is_valid_second', 0) or 0) != 1:
        return False
    if not _required_fields_present(row=row, field_names=LABEL_PRICE_FIELDS):
        return False
    required_fields = tuple(policy['required_book_fields']) + tuple(policy['required_state_fields'])
    if not _required_fields_present(row=row, field_names=required_fields):
        return False
    if not _value_within_limit(row=row, key='book_age_seconds', limit=float(policy['book_stale_threshold_sec'])):
        return False
    if not _value_within_limit(row=row, key='state_age_seconds', limit=float(policy['state_stale_threshold_sec'])):
        return False
    return _value_within_limit(row=row, key='clock_skew_ms', limit=float(policy['clock_skew_threshold_ms']))


def _required_fields_present(
    *,
    row: dict[str, object],
    field_names: tuple[str, ...],
) -> bool:
    return all(field_name in row and row[field_name] is not None for field_name in field_names)


def _value_within_limit(
    *,
    row: dict[str, object],
    key: str,
    limit: float,
) -> bool:
    value = row.get(key)
    if value is None:
        return False
    return float(value) <= limit
