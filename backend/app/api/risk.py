# 高级风险指标 API
# 提供 VaR、Sharpe/Sortino、回撤分析、滚动指标等端点

import asyncio
from typing import Any, Dict

from fastapi import APIRouter, Query

from ..core.app_context import get_app_context
from ..core.risk_metrics import (
    calculate_historical_var,
    calculate_max_drawdown_series,
    calculate_parametric_var,
    calculate_returns,
    calculate_rolling_metrics,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    safe_float,
)

router = APIRouter(prefix="/api/risk", tags=["risk"])


def _get_storage():
    ctx = get_app_context()
    return ctx.storage


def _get_equities_and_returns(storage, mode: str, days: int):
    """获取权益序列和收益率序列"""
    equities = storage.get_portfolio_equities(mode, days)
    returns = calculate_returns(equities)
    return equities, returns


@router.get("/metrics")
async def get_risk_metrics(
    mode: str = Query("simulated", description="交易模式"),
    days: int = Query(90, ge=7, le=365, description="回溯天数"),
):
    """综合风险仪表盘：VaR + Sharpe + Sortino + 回撤"""
    storage = _get_storage()
    equities, returns = await asyncio.to_thread(
        _get_equities_and_returns, storage, mode, days
    )

    if len(returns) < 2:
        return {
            "success": True,
            "data": {
                "has_data": False,
                "message": "权益快照不足，请先确保系统已运行数天并记录了每日快照",
                "data_points": len(equities),
            },
        }

    dd_info = calculate_max_drawdown_series(equities)

    return {
        "success": True,
        "data": {
            "has_data": True,
            "data_points": len(equities),
            "var_95": calculate_historical_var(returns, confidence=0.95),
            "var_99": calculate_historical_var(returns, confidence=0.99),
            "parametric_var_95": calculate_parametric_var(returns, confidence=0.95),
            "sharpe_ratio": round(calculate_sharpe_ratio(returns), 4),
            "sortino_ratio": round(calculate_sortino_ratio(returns), 4),
            "max_drawdown": dd_info["max_drawdown"],
            "max_drawdown_duration": dd_info["max_drawdown_duration"],
            "current_drawdown": dd_info["current_drawdown"],
            "peak_equity": dd_info["peak"],
            "latest_equity": equities[-1] if equities else 0,
        },
    }


@router.get("/var")
async def get_var(
    mode: str = Query("simulated"),
    confidence: float = Query(0.95, ge=0.8, le=0.999),
    days: int = Query(90, ge=7, le=365),
):
    """VaR（Value at Risk）计算"""
    storage = _get_storage()
    equities, returns = await asyncio.to_thread(
        _get_equities_and_returns, storage, mode, days
    )

    return {
        "success": True,
        "data": {
            "historical_var": calculate_historical_var(returns, confidence=confidence),
            "parametric_var": calculate_parametric_var(returns, confidence=confidence),
            "confidence": confidence,
            "data_points": len(returns),
        },
    }


@router.get("/drawdown")
async def get_drawdown(
    mode: str = Query("simulated"),
    days: int = Query(90, ge=7, le=365),
):
    """回撤分析，返回回撤时序数据"""
    storage = _get_storage()
    equities = await asyncio.to_thread(
        storage.get_portfolio_equities, mode, days
    )

    dd_info = calculate_max_drawdown_series(equities)
    snapshots = await asyncio.to_thread(
        storage.get_portfolio_snapshots, mode, days
    )
    dates = [s["date"] for s in snapshots if s["total_equity"] > 0]

    return {
        "success": True,
        "data": {
            "dates": dates,
            "equities": equities,
            **dd_info,
        },
    }


@router.get("/rolling")
async def get_rolling_metrics(
    mode: str = Query("simulated"),
    window: int = Query(30, ge=5, le=90),
    days: int = Query(90, ge=7, le=365),
):
    """滚动风险指标（Sharpe、波动率、VaR）"""
    storage = _get_storage()
    equities, returns = await asyncio.to_thread(
        _get_equities_and_returns, storage, mode, days
    )

    rolling = calculate_rolling_metrics(returns, window=window)
    snapshots = await asyncio.to_thread(
        storage.get_portfolio_snapshots, mode, days
    )
    # 收益率比权益少一期
    dates = [s["date"] for s in snapshots if s["total_equity"] > 0]
    if len(dates) > 1:
        dates = dates[1:]

    return {
        "success": True,
        "data": {
            "dates": dates[:len(returns)],
            **rolling,
        },
    }


@router.get("/snapshots")
async def get_snapshots(
    mode: str = Query("simulated"),
    days: int = Query(90, ge=1, le=365),
):
    """原始权益快照"""
    storage = _get_storage()
    snapshots = await asyncio.to_thread(
        storage.get_portfolio_snapshots, mode, days
    )
    return {"success": True, "data": snapshots}
