from app.core.trend_research.models import FeatureBar1s
from app.core.trend_research.research_runtime import build_factor_series_payload


class FakeStorage:
    def __init__(self, bars):
        self._bars = list(bars)
        self.saved_labels = []
        self.saved_scores = []

    def list_feature_bars_1s(self, inst_id, limit=100):
        rows = [bar for bar in self._bars if bar.inst_id == inst_id]
        rows.sort(key=lambda bar: bar.second_bucket, reverse=True)
        return rows[:limit]

    def replace_swing_labels(self, inst_id, labels):
        self.saved_labels = [inst_id, list(labels)]

    def replace_factor_scores(self, inst_id, scores):
        self.saved_scores = [inst_id, list(scores)]


def _bar(second_bucket, **overrides):
    payload = {
        "inst_id": "BTC-USDT-SWAP",
        "ts_exchange": float(second_bucket),
        "ts_local": float(second_bucket),
        "second_bucket": second_bucket,
        "mid_price": 100.0,
        "mark_price": 100.2,
        "index_price": 99.9,
        "spread_bps": 10.0,
        "signed_trade_notional": 2000.0,
        "trade_count": 4,
        "oi_delta": 2.0,
        "basis_zscore": 0.5,
        "data_quality": "ok",
        "bid_price": 99.9,
        "ask_price": 100.1,
        "bid_size": 12.0,
        "ask_size": 10.0,
        "buy_notional": 1100.0,
        "sell_notional": 900.0,
        "buy_count": 3,
        "sell_count": 2,
        "max_trade_notional": 700.0,
        "buy_burst_count": 2,
        "sell_burst_count": 1,
        "buy_burst_notional": 800.0,
        "sell_burst_notional": 300.0,
        "open_price": 99.8,
        "high_price": 100.4,
        "low_price": 99.7,
        "close_price": 100.0,
        "microprice": 100.03,
        "basis_bps": 15.0,
        "open_interest": 5000.0,
        "funding_rate": 0.0001,
        "funding_delta": 0.00001,
        "premium": 3.0,
    }
    payload.update(overrides)
    return FeatureBar1s(**payload)


def test_build_factor_series_payload_returns_aligned_series_and_placeholders():
    storage = FakeStorage([
        _bar(101, close_price=100.0, oi_delta=1.0),
        _bar(102, close_price=101.0, oi_delta=-1.0),
        _bar(103, close_price=99.5, oi_delta=2.0),
    ])

    payload = build_factor_series_payload(
        storage,
        "BTC-USDT-SWAP",
        lookback=1800,
        limit=3,
    )

    assert payload["second_buckets"] == [101, 102, 103]
    assert payload["inst_id"] == "BTC-USDT-SWAP"

    series_by_name = {row["factor_name"]: row for row in payload["series"]}
    assert series_by_name["price_oi_quadrant"]["values"] == [0.0, 0.5, -1.0]
    assert series_by_name["multi_level_book_imbalance"]["available"] is False
    assert series_by_name["multi_level_book_imbalance"]["values"] == []

    score_meta_by_name = {row["factor_name"]: row for row in payload["score_meta"]}
    assert "momentum_60s" in score_meta_by_name
    assert score_meta_by_name["multi_level_book_imbalance"]["available"] is False
