import pytest

from app.agent.code_runner import (
    MarketAnalysisSecurityError,
    MarketAnalysisTimeoutError,
    run_market_analysis,
)


def test_run_market_analysis_returns_structured_result():
    dataset = {
        "context": {
            "inst_id": "BTC-USDT",
            "inst_type": "SPOT",
        },
        "candles": {
            "1H": {
                "count": 3,
                "candles": [
                    {"timestamp": 1, "close": 100.0, "volume": 10.0},
                    {"timestamp": 2, "close": 105.0, "volume": 12.0},
                    {"timestamp": 3, "close": 110.0, "volume": 11.0},
                ],
            }
        },
        "orderbook": {
            "bids": [{"price": 109.0, "size": 5.0}],
            "asks": [{"price": 111.0, "size": 6.0}],
        },
    }
    code = """
def analyze(data, helpers):
    frame = helpers["candles_to_frame"]("1H")
    print("rows", len(frame))
    return {
        "summary": "上涨节奏延续",
        "metrics": {
            "close_change": float(frame["close"].iloc[-1] - frame["close"].iloc[0]),
            "close_mean": float(frame["close"].mean()),
        },
        "tables": {
            "candles": frame.tail(2),
        },
    }
"""

    result = run_market_analysis(code=code, dataset=dataset, timeout_seconds=8)

    assert result["summary"] == "上涨节奏延续"
    assert result["metrics"]["close_change"] == 10.0
    assert result["tables"]["candles"]["type"] == "dataframe"
    assert result["tables"]["candles"]["row_count"] == 2
    assert result["dataset_overview"]["timeframes"]["1H"] == 3
    assert result["logs"] == ["rows 3"]


def test_run_market_analysis_exposes_pd_and_np_namespaces():
    dataset = {"context": {}, "candles": {}}
    code = """
def analyze(data, helpers):
    frame = pd.DataFrame([{"x": 1}, {"x": 2}])
    arr = np.array([1, 2, 3])
    return {
        "metrics": {
            "rows": int(len(frame)),
            "sum": int(np.sum(arr)),
        }
    }
"""

    result = run_market_analysis(code=code, dataset=dataset, timeout_seconds=8)

    assert result["metrics"]["rows"] == 2
    assert result["metrics"]["sum"] == 6


def test_run_market_analysis_rejects_imports():
    dataset = {"context": {}, "candles": {}}
    code = """
import os

def analyze(data, helpers):
    return {"summary": "bad"}
"""

    with pytest.raises(MarketAnalysisSecurityError):
        run_market_analysis(code=code, dataset=dataset, timeout_seconds=8)


def test_run_market_analysis_times_out():
    dataset = {"context": {}, "candles": {}}
    code = """
def analyze(data, helpers):
    while True:
        pass
"""

    with pytest.raises(MarketAnalysisTimeoutError):
        run_market_analysis(code=code, dataset=dataset, timeout_seconds=3)
