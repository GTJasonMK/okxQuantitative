from app.core.data_center_collection.integrity_policy import get_integrity_policy
from app.core.data_center_collection.second_state_assembler import assemble_second_state


def _runtime_snapshot(**overrides):
    snapshot = {
        'second_bucket': 1713000000,
        'ts_exchange': 1713000000.0,
        'ts_local': 1713000000.2,
        'bid_price': 65000.0,
        'ask_price': 65000.5,
        'bid_size': 12.0,
        'ask_size': 10.0,
        'mid_price': 65000.25,
        'microprice': 65000.23,
        'open_price': 65000.25,
        'high_price': 65000.25,
        'low_price': 65000.25,
        'close_price': 65000.25,
        'mark_price': 65000.1,
        'index_price': 65000.0,
        'trade_count': 1,
        'signed_trade_notional': 0.0,
        'buy_notional': 0.0,
        'sell_notional': 0.0,
        'buy_count': 0,
        'sell_count': 0,
        'max_trade_notional': 0.0,
        'buy_burst_count': 0,
        'sell_burst_count': 0,
        'buy_burst_notional': 0.0,
        'sell_burst_notional': 0.0,
        'open_interest': 3200000.0,
        'oi_delta': 0.0,
        'funding_rate': 0.0001,
        'funding_delta': 0.0,
        'premium': 1.5,
        'spread_bps': 0.08,
        'book_level_count': 5,
        'multi_level_book_imbalance': 0.11,
        'book_slope': 0.03,
        'has_trade_input': 1,
        'has_book_input': 1,
        'has_state_input': 1,
        'book_age_seconds': 0.0,
        'state_age_seconds': 0.0,
        'clock_skew_ms': 12.0,
        'integrity_policy_version': 'strict_v1',
    }
    snapshot.update(overrides)
    return snapshot


def test_assembler_marks_valid_second_when_book_and_state_are_fresh():
    payload = assemble_second_state(_runtime_snapshot(second_bucket=1713000000))

    assert payload['is_valid_second'] == 1
    assert payload['quality_grade'] == 'A'
    assert payload['invalid_reason'] == ''


def test_assembler_uses_mid_price_when_no_trade_input():
    payload = assemble_second_state(_runtime_snapshot(trade_count=0, close_price=0.0))

    assert payload['close_price'] == payload['mid_price']
    assert payload['open_price'] == payload['mid_price']


def test_assembler_marks_invalid_when_book_is_stale():
    payload = assemble_second_state(_runtime_snapshot(book_age_seconds=3.0))

    assert payload['is_valid_second'] == 0
    assert payload['quality_grade'] == 'F'
    assert payload['invalid_reason'] == 'book_stale'


def test_assembler_uses_explicit_integrity_policy_thresholds():
    policy = get_integrity_policy('strict_v1')

    valid_payload = assemble_second_state(
        _runtime_snapshot(
            book_age_seconds=policy['book_stale_threshold_sec'],
            state_age_seconds=policy['state_stale_threshold_sec'],
            clock_skew_ms=policy['clock_skew_threshold_ms'],
        )
    )
    invalid_payload = assemble_second_state(
        _runtime_snapshot(
            book_age_seconds=policy['book_stale_threshold_sec'] + 0.01,
        )
    )

    assert valid_payload['is_valid_second'] == 1
    assert valid_payload['integrity_policy_version'] == 'strict_v1'
    assert invalid_payload['is_valid_second'] == 0
    assert invalid_payload['invalid_reason'] == 'book_stale'
