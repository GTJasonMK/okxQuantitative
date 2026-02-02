import types

import pytest


def test_mode_utils_normalize_and_coerce():
    from app.utils.mode import normalize_mode, coerce_mode, mode_from_bool

    assert normalize_mode(" simulated ") == "simulated"
    assert normalize_mode("LIVE") == "live"
    assert normalize_mode("unknown") is None

    assert coerce_mode("unknown", "simulated") == "simulated"
    assert coerce_mode("live", "simulated") == "live"

    assert mode_from_bool(True) == "simulated"
    assert mode_from_bool(False) == "live"


def test_numbers_require_positive_decimal_str():
    from app.utils.numbers import require_positive_decimal_str

    assert require_positive_decimal_str(" 1.23 ") == "1.23"

    with pytest.raises(ValueError):
        require_positive_decimal_str("0")

    with pytest.raises(ValueError):
        require_positive_decimal_str("-1")

    with pytest.raises(ValueError):
        require_positive_decimal_str("not-a-number")

    with pytest.raises(ValueError):
        require_positive_decimal_str("Infinity")


def test_numbers_require_positive_int_str():
    from app.utils.numbers import require_positive_int_str

    assert require_positive_int_str(" 2 ") == "2"

    with pytest.raises(ValueError):
        require_positive_int_str("1.1")

    with pytest.raises(ValueError):
        require_positive_int_str("0")


def test_timeframes_helpers():
    from app.utils.timeframes import timeframe_to_ms, candles_per_day, calculate_candle_count, periods_per_year

    assert timeframe_to_ms("1H") == 60 * 60 * 1000
    assert timeframe_to_ms("unknown") == 60 * 60 * 1000

    assert candles_per_day("1H") == 24
    assert candles_per_day("1D") == 1

    assert calculate_candle_count(timeframe="1H", days=1) == 100  # 默认最少 100 根
    assert calculate_candle_count(timeframe="1H", days=10) == 240

    assert periods_per_year("1H") == 365 * 24
    assert periods_per_year("1W") == 52
    assert periods_per_year("unknown") == 365


def test_holdings_builders_are_pure_and_compatible():
    from app.core.holdings import build_holdings_base, build_spot_holdings

    balance_details = [
        {"ccy": "USDT", "availBal": "100", "frozenBal": "0"},
        {"ccy": "BTC", "availBal": "0.1", "frozenBal": "0"},
        {"ccy": "ETH", "availBal": "0", "frozenBal": "0"},
    ]
    cost_data = {"BTC": {"avg_cost": 20000, "total_cost": 2000, "total_fee": 1}}

    base = build_holdings_base(balance_details=balance_details, cost_data=cost_data)
    assert base[0]["ccy"] == "USDT"
    assert base[0]["is_stablecoin"] is True
    assert base[1]["ccy"] == "BTC"
    assert base[1]["avg_cost"] == "20000.0"
    assert base[1]["total_cost"] == "2000.0"

    tickers = {"BTC-USDT": types.SimpleNamespace(last=30000)}
    holdings, totals = build_spot_holdings(balance_details=balance_details, tickers=tickers, cost_data=cost_data)

    assert holdings[0]["ccy"] == "USDT"
    assert holdings[0]["value_usdt"] == "100.0"
    assert holdings[1]["ccy"] == "BTC"
    assert holdings[1]["value_usdt"] == "3000.0"
    assert holdings[1]["pnl_usdt"] == "1000.0"

    assert totals["total_value_usdt"] == "3100.0"
    assert totals["total_cost_usdt"] == "2000.0"
    assert totals["total_pnl_percent"] == "50.0"


def test_datetimes_parse_iso_datetime_accepts_z():
    from app.utils.datetimes import parse_iso_datetime

    dt = parse_iso_datetime("2024-01-01T00:00:00Z")
    assert dt.isoformat() == "2024-01-01T00:00:00+00:00"


def test_files_atomic_write_and_read_json(tmp_path):
    from app.utils.files import atomic_write_json, read_json_file

    p = tmp_path / "prefs.json"
    assert read_json_file(p, default={}) == {}

    atomic_write_json(p, {"a": 1, "b": "x"}, ensure_ascii=False, indent=2)
    assert read_json_file(p, default={}) == {"a": 1, "b": "x"}
