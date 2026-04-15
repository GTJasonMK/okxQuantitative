BASIS_BPS_MULTIPLIER = 1e4

from .integrity_policy import get_integrity_policy


def assemble_second_state(snapshot: dict[str, object]) -> dict[str, object]:
    policy = get_integrity_policy(str(snapshot.get('integrity_policy_version', 'strict_v1')))
    row = _build_second_state_row(snapshot, policy=policy)
    invalid_codes = _collect_invalid_codes(row, policy=policy)
    row['is_valid_second'] = 0 if invalid_codes else 1
    row['quality_grade'] = _resolve_quality_grade(row, invalid_codes, policy=policy)
    row['invalid_reason'] = '|'.join(invalid_codes)
    return row


def _build_second_state_row(
    snapshot: dict[str, object],
    *,
    policy: dict[str, object],
) -> dict[str, object]:
    row = {key: snapshot.get(key, 0) for key in _row_fields()}
    row['trade_count'] = int(row['trade_count'] or 0)
    _normalize_price_path(row)
    row['basis_bps'] = _resolve_basis_bps(row)
    row['integrity_policy_version'] = str(policy['integrity_policy_version'])
    return row


def _row_fields() -> tuple[str, ...]:
    return (
        'second_bucket', 'ts_exchange', 'ts_local', 'bid_price', 'ask_price', 'bid_size', 'ask_size',
        'bid_depth_10bps', 'ask_depth_10bps',
        'mid_price', 'microprice', 'open_price', 'high_price', 'low_price', 'close_price',
        'mark_price', 'index_price', 'trade_count', 'signed_trade_notional', 'buy_notional',
        'sell_notional', 'buy_count', 'sell_count', 'max_trade_notional', 'buy_burst_count',
        'sell_burst_count', 'buy_burst_notional', 'sell_burst_notional', 'open_interest',
        'oi_delta', 'funding_rate', 'funding_delta', 'premium', 'basis_bps', 'spread_bps',
        'book_level_count', 'multi_level_book_imbalance', 'book_slope', 'has_trade_input',
        'has_book_input', 'has_state_input', 'book_age_seconds', 'state_age_seconds', 'clock_skew_ms',
    )


def _normalize_price_path(row: dict[str, object]) -> None:
    if int(row['trade_count']) > 0 and float(row['close_price'] or 0.0) > 0.0:
        return
    if float(row['mid_price'] or 0.0) > 0.0:
        for key in ('open_price', 'high_price', 'low_price', 'close_price'):
            row[key] = float(row['mid_price'])
        return
    for key in ('open_price', 'high_price', 'low_price', 'close_price'):
        row[key] = 0.0


def _resolve_basis_bps(row: dict[str, object]) -> float:
    index_price = float(row['index_price'] or 0.0)
    mark_price = float(row['mark_price'] or 0.0)
    if index_price <= 0.0:
        return 0.0
    return BASIS_BPS_MULTIPLIER * (mark_price - index_price) / index_price


def _collect_invalid_codes(
    row: dict[str, object],
    *,
    policy: dict[str, object],
) -> list[str]:
    invalid_codes: list[str] = []
    if _is_missing_required_fields(row, fields=policy['required_book_fields']):
        invalid_codes.append('missing_book_snapshot')
    if _is_missing_required_fields(row, fields=policy['required_state_fields']):
        invalid_codes.append('missing_state_snapshot')
    if float(row['book_age_seconds'] or 0.0) > float(policy['book_stale_threshold_sec']):
        invalid_codes.append('book_stale')
    if float(row['state_age_seconds'] or 0.0) > float(policy['state_stale_threshold_sec']):
        invalid_codes.append('state_stale')
    if not _has_valid_top_of_book(row):
        invalid_codes.append('invalid_top_of_book')
    if not _has_valid_price_path(row):
        invalid_codes.append('invalid_price_path')
    if float(row['clock_skew_ms'] or 0.0) > float(policy['clock_skew_threshold_ms']):
        invalid_codes.append('clock_skew_exceeded')
    return invalid_codes


def _is_missing_required_fields(
    row: dict[str, object],
    *,
    fields: tuple[str, ...],
) -> bool:
    return any(float(row.get(field_name, 0.0) or 0.0) <= 0.0 for field_name in fields)


def _has_valid_top_of_book(row: dict[str, object]) -> bool:
    bid_price = float(row['bid_price'] or 0.0)
    ask_price = float(row['ask_price'] or 0.0)
    mid_price = float(row['mid_price'] or 0.0)
    microprice = float(row['microprice'] or 0.0)
    open_interest = float(row['open_interest'] or 0.0)
    return bid_price > 0.0 and ask_price >= bid_price and mid_price > 0.0 and microprice > 0.0 and open_interest >= 0.0


def _has_valid_price_path(row: dict[str, object]) -> bool:
    open_price = float(row['open_price'] or 0.0)
    high_price = float(row['high_price'] or 0.0)
    low_price = float(row['low_price'] or 0.0)
    close_price = float(row['close_price'] or 0.0)
    if min(open_price, high_price, low_price, close_price) <= 0.0:
        return False
    return low_price <= min(open_price, close_price) <= max(open_price, close_price) <= high_price


def _resolve_quality_grade(
    row: dict[str, object],
    invalid_codes: list[str],
    *,
    policy: dict[str, object],
) -> str:
    if invalid_codes:
        return 'F'
    if int(row['has_book_input'] or 0) == 0 or int(row['has_state_input'] or 0) == 0:
        return 'C'
    if (
        float(row['book_age_seconds'] or 0.0) > float(policy['book_warn_stale_threshold_sec'])
        or float(row['state_age_seconds'] or 0.0) > float(policy['state_warn_stale_threshold_sec'])
        or float(row['clock_skew_ms'] or 0.0) > float(policy['clock_skew_warn_threshold_ms'])
    ):
        return 'B'
    return 'A'
