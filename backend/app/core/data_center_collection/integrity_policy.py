from __future__ import annotations


STRICT_V1_INTEGRITY_POLICY = {
    'integrity_policy_version': 'strict_v1',
    'book_stale_threshold_sec': 2.0,
    'state_stale_threshold_sec': 15.0,
    'clock_skew_threshold_ms': 3000.0,
    'required_book_fields': ('bid_price', 'ask_price', 'mid_price', 'microprice'),
    'required_state_fields': ('mark_price', 'index_price', 'open_interest'),
    'trade_missing_policy': 'mid_price_carry_forward_v1',
    'strict_input_complete': True,
    'strict_label_complete': True,
    'book_warn_stale_threshold_sec': 1.0,
    'state_warn_stale_threshold_sec': 5.0,
    'clock_skew_warn_threshold_ms': 1000.0,
}

_POLICY_REGISTRY = {
    STRICT_V1_INTEGRITY_POLICY['integrity_policy_version']: STRICT_V1_INTEGRITY_POLICY,
}


def get_integrity_policy(version: str) -> dict[str, object]:
    policy = _POLICY_REGISTRY.get(str(version))
    if policy is None:
        raise ValueError(f'unsupported integrity policy version: {version}')
    return dict(policy)
