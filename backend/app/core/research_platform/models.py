from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ResearchCollectionSession:
    session_id: str
    inst_id: str
    started_at: float
    ended_at: float | None
    planned_duration_sec: int
    status: str
    stop_reason: str
    collector_version: str
    source_config_hash: str
    trigger_mode: str
    trigger_note: str
    sampling_policy_id: str
    integrity_policy_version: str
    feature_recipe_version: str
    book_channel: str
    valid_second_count: int
    missing_second_count: int
    book_stale_second_count: int
    state_stale_second_count: int
    coverage_ratio: float
    quality_score: float


@dataclass(frozen=True)
class ResearchSecondState:
    session_id: str
    inst_id: str
    second_bucket: int
    ts_exchange: float
    ts_local: float
    bid_price: float
    ask_price: float
    bid_size: float
    ask_size: float
    bid_depth_10bps: float
    ask_depth_10bps: float
    mid_price: float
    microprice: float
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    mark_price: float
    index_price: float
    trade_count: int
    signed_trade_notional: float
    buy_notional: float
    sell_notional: float
    buy_count: int
    sell_count: int
    max_trade_notional: float
    buy_burst_count: int
    sell_burst_count: int
    buy_burst_notional: float
    sell_burst_notional: float
    open_interest: float
    oi_delta: float
    funding_rate: float
    funding_delta: float
    premium: float
    basis_bps: float
    spread_bps: float
    book_level_count: int
    multi_level_book_imbalance: float
    book_slope: float
    has_trade_input: int
    has_book_input: int
    has_state_input: int
    book_age_seconds: float
    state_age_seconds: float
    clock_skew_ms: float
    is_valid_second: int
    quality_grade: str
    invalid_reason: str
    integrity_policy_version: str


@dataclass(frozen=True)
class ResearchTargetCensus15m:
    census_id: str
    inst_id: str
    decision_ts: int
    deployment_eligible: int
    census_policy_version: str
    shift_state_definition_version: str
    shift_state_blob_json: str
    hour_of_day: int
    day_of_week: int
    realized_vol_proxy_2h: float
    spread_snapshot_bps: float
    liquidity_snapshot_bin: int
    funding_regime: str
    session_active_flag: int
    source_health_flag: int
    invalid_reason: str
