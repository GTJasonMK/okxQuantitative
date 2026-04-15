from __future__ import annotations

from pathlib import Path

from app.core.data_storage import DataStorage


DEFAULT_INST_ID = 'BTC-USDT-SWAP'
DEFAULT_SESSION_ID = 'sess-1'
DEFAULT_DECISION_TS = 1713000900
DEFAULT_INPUT_SECONDS = 7200
DEFAULT_LABEL_SECONDS = 900
BASE_PRICE = 65000.0
PRICE_STEP = 0.05


def create_storage(tmp_path: Path, name: str) -> DataStorage:
    return DataStorage(tmp_path / name)


def close_storage(storage: DataStorage) -> None:
    connection = getattr(storage, '_local', None)
    if connection is None or getattr(connection, 'connection', None) is None:
        return
    connection.connection.close()
    connection.connection = None


def build_second_rows(
    *,
    start_ts: int,
    count: int,
    inst_id: str = DEFAULT_INST_ID,
    session_id: str = DEFAULT_SESSION_ID,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for offset in range(count):
        second_bucket = start_ts + offset
        close_price = BASE_PRICE + (offset * PRICE_STEP)
        open_price = close_price - 0.03
        high_price = close_price + 0.08
        low_price = open_price - 0.05
        rows.append(
            {
                'session_id': session_id,
                'inst_id': inst_id,
                'second_bucket': second_bucket,
                'ts_exchange': float(second_bucket),
                'ts_local': float(second_bucket) + 0.2,
                'bid_price': close_price - 0.01,
                'ask_price': close_price + 0.01,
                'bid_size': 12.0,
                'ask_size': 10.0,
                'bid_depth_10bps': 40.0,
                'ask_depth_10bps': 20.0,
                'mid_price': close_price,
                'microprice': close_price,
                'open_price': open_price,
                'high_price': high_price,
                'low_price': low_price,
                'close_price': close_price,
                'mark_price': close_price,
                'index_price': close_price - 0.02,
                'trade_count': 18,
                'signed_trade_notional': 230000.0,
                'buy_notional': 150000.0,
                'sell_notional': 80000.0,
                'buy_count': 10,
                'sell_count': 8,
                'max_trade_notional': 45000.0,
                'buy_burst_count': 2,
                'sell_burst_count': 1,
                'buy_burst_notional': 56000.0,
                'sell_burst_notional': 18000.0,
                'open_interest': 3200000.0,
                'oi_delta': 1200.0,
                'funding_rate': 0.0001,
                'funding_delta': 0.0,
                'premium': 1.5,
                'basis_bps': 2.1,
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
                'is_valid_second': 1,
                'quality_grade': 'A',
                'invalid_reason': '',
                'integrity_policy_version': 'strict_v1',
            }
        )
    return rows


def save_second_rows(storage: DataStorage, rows: list[dict[str, object]]) -> None:
    for row in rows:
        storage.save_research_second_state(**row)
