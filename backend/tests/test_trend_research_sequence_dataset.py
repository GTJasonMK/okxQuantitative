from math import log

from app.core.trend_research.models import FeatureBar1s
from app.core.trend_research.sequence_dataset import build_online_sequence_window, build_sequence_samples


START_BUCKET = 1_712_365_200
INPUT_MINUTES = 120
HORIZON_MINUTES = 60


def _price_for_minute(minute_index: int) -> float:
    if minute_index == 147:
        return 130.0
    if minute_index == 172:
        return 80.0
    return 100.0


def _build_feature_bar(minute_index: int) -> FeatureBar1s:
    price = _price_for_minute(minute_index)
    second_bucket = START_BUCKET + minute_index * 60
    return FeatureBar1s(
        inst_id="BTC-USDT-SWAP",
        ts_exchange=float(second_bucket),
        ts_local=float(second_bucket),
        second_bucket=second_bucket,
        mid_price=price,
        mark_price=price,
        index_price=price,
        spread_bps=1.0,
        signed_trade_notional=float(minute_index + 1),
        trade_count=minute_index + 1,
        oi_delta=float(minute_index) / 10.0,
        basis_zscore=float(minute_index) / 100.0,
        data_quality="ok",
        bid_price=price - 0.5,
        ask_price=price + 0.5,
        bid_size=2.0 + float(minute_index % 3),
        ask_size=1.0 + float((minute_index + 1) % 3),
        buy_notional=50.0 + minute_index,
        sell_notional=40.0 + minute_index,
        buy_count=3,
        sell_count=2,
        max_trade_notional=20.0,
        open_price=price,
        high_price=price,
        low_price=price,
        close_price=price,
        microprice=price,
        basis_bps=float(minute_index) / 10.0,
        open_interest=1_000.0 + minute_index,
        funding_rate=0.0001,
        funding_delta=0.0,
        premium=0.0,
        book_level_count=1,
        multi_level_book_imbalance=0.0,
        book_slope=0.0,
    )


def test_build_sequence_samples_aggregates_120_input_minutes_and_60_target_minutes():
    bars = [_build_feature_bar(minute_index) for minute_index in range(190)]

    samples = build_sequence_samples(
        bars,
        feature_names=("queue_imbalance", "basis_bps"),
        input_minutes=INPUT_MINUTES,
        horizon_minutes=HORIZON_MINUTES,
    )

    sample = samples[-1]
    assert len(sample.feature_rows) == INPUT_MINUTES
    assert sample.target.top_time_bucket == 17
    assert sample.target.bottom_time_bucket == 42
    assert sample.target.top_return == log(130.0 / 100.0)
    assert sample.target.bottom_return == log(80.0 / 100.0)


def test_build_sequence_samples_drops_incomplete_future_windows():
    bars = [_build_feature_bar(minute_index) for minute_index in range(150)]

    samples = build_sequence_samples(
        bars,
        feature_names=("queue_imbalance", "basis_bps"),
        input_minutes=INPUT_MINUTES,
        horizon_minutes=HORIZON_MINUTES,
    )

    assert samples == []


def test_build_sequence_samples_returns_no_rows_when_selected_feature_is_unavailable():
    bars = [_build_feature_bar(minute_index) for minute_index in range(190)]

    samples = build_sequence_samples(
        bars,
        feature_names=("multi_level_book_imbalance",),
        input_minutes=INPUT_MINUTES,
        horizon_minutes=HORIZON_MINUTES,
    )

    assert samples == []


def test_build_online_sequence_window_uses_latest_input_minutes():
    bars = [_build_feature_bar(minute_index) for minute_index in range(190)]

    window = build_online_sequence_window(
        bars,
        feature_names=("queue_imbalance", "basis_bps"),
        input_minutes=INPUT_MINUTES,
    )

    assert len(window.feature_rows) == INPUT_MINUTES
    assert window.anchor_minute_bucket == (START_BUCKET // 60) + 189
    assert window.current_price == 100.0
