# 市场扫描 API
# 提供扫描方案管理和即时/定时扫描端点

import asyncio
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from ..core.app_context import get_app_context
from ..core.market_scanner import AVAILABLE_CONDITIONS, MarketScanner, ScanCondition

router = APIRouter(prefix="/api/scanner", tags=["scanner"])


def _get_storage():
    ctx = get_app_context()
    return ctx.storage


# ==================== 请求模型 ====================


class ScanConditionModel(BaseModel):
    """扫描条件"""
    indicator: str = Field(..., description="指标类型: rsi, sma_cross, bb_squeeze, macd_signal, volume_breakout")
    operator: str = Field(..., description="比较运算: gt, lt, gte, lte, cross_above, cross_below")
    value: float = Field(default=0.0, description="阈值")
    params: Dict[str, Any] = Field(default_factory=dict, description="指标参数")


class ScanRequest(BaseModel):
    """即时扫描请求"""
    symbols: List[str] = Field(default_factory=list, description="交易对列表，为空则扫描所有已有数据的币种")
    conditions: List[ScanConditionModel] = Field(..., description="筛选条件")
    logic: str = Field(default="and", description="条件逻辑: and / or")
    timeframe: str = Field(default="1H", description="K线周期")
    inst_type: str = Field(default="SPOT", description="交易类型")


class ProfileCreateRequest(BaseModel):
    """创建扫描方案"""
    name: str = Field(..., description="方案名称")
    conditions: List[ScanConditionModel] = Field(..., description="筛选条件")
    logic: str = Field(default="and")
    symbols: List[str] = Field(default_factory=list)
    timeframe: str = Field(default="1H")
    inst_type: str = Field(default="SPOT")
    enabled: bool = Field(default=True)
    interval_seconds: int = Field(default=300, ge=60, le=86400)


class ProfileUpdateRequest(BaseModel):
    """更新扫描方案（所有字段可选）"""
    name: Optional[str] = None
    conditions: Optional[List[ScanConditionModel]] = None
    logic: Optional[str] = None
    symbols: Optional[List[str]] = None
    timeframe: Optional[str] = None
    inst_type: Optional[str] = None
    enabled: Optional[bool] = None
    interval_seconds: Optional[int] = Field(default=None, ge=60, le=86400)


# ==================== 扫描方案 CRUD ====================


@router.post("/profiles")
async def create_profile(body: ProfileCreateRequest):
    """创建扫描方案"""
    storage = _get_storage()
    profile_data = body.model_dump()
    profile_data["conditions"] = [c.model_dump() for c in body.conditions]
    profile_id = await asyncio.to_thread(storage.save_scanner_profile, profile_data)
    profile = await asyncio.to_thread(storage.get_scanner_profile, profile_id)
    return {"success": True, "data": profile}


@router.get("/profiles")
async def list_profiles():
    """列出所有扫描方案"""
    storage = _get_storage()
    profiles = await asyncio.to_thread(storage.get_scanner_profiles)
    return {"success": True, "data": profiles}


@router.put("/profiles/{profile_id}")
async def update_profile(profile_id: str, body: ProfileUpdateRequest):
    """更新扫描方案"""
    storage = _get_storage()
    existing = await asyncio.to_thread(storage.get_scanner_profile, profile_id)
    if not existing:
        raise HTTPException(status_code=404, detail="扫描方案不存在")

    updates = body.model_dump(exclude_none=True)
    if "conditions" in updates:
        updates["conditions"] = [c.model_dump() for c in body.conditions]
    merged = {**existing, **updates}
    await asyncio.to_thread(storage.save_scanner_profile, merged)
    profile = await asyncio.to_thread(storage.get_scanner_profile, profile_id)
    return {"success": True, "data": profile}


@router.delete("/profiles/{profile_id}")
async def delete_profile(profile_id: str):
    """删除扫描方案"""
    storage = _get_storage()
    ok = await asyncio.to_thread(storage.delete_scanner_profile, profile_id)
    if not ok:
        raise HTTPException(status_code=404, detail="扫描方案不存在")
    return {"success": True, "message": "方案已删除"}


# ==================== 扫描执行 ====================


@router.post("/scan")
async def run_scan(body: ScanRequest):
    """执行即时扫描（内联条件）"""
    storage = _get_storage()

    symbols = body.symbols
    if not symbols:
        available = await asyncio.to_thread(storage.get_available_symbols)
        symbols = [
            s["inst_id"] for s in available
            if s.get("inst_type", "SPOT") == body.inst_type
        ]

    if not symbols:
        return {"success": True, "data": [], "scanned": 0, "matched": 0}

    conditions = [
        ScanCondition(
            indicator=c.indicator,
            operator=c.operator,
            value=c.value,
            params=c.params,
        )
        for c in body.conditions
    ]

    scanner = MarketScanner(storage)
    results = await asyncio.to_thread(
        scanner.scan,
        symbols=symbols,
        conditions=conditions,
        logic=body.logic,
        timeframe=body.timeframe,
        inst_type=body.inst_type,
    )

    result_dicts = [
        {
            "inst_id": r.inst_id,
            "matched_conditions": r.matched_conditions,
            "indicator_values": r.indicator_values,
            "price": r.price,
            "timeframe": body.timeframe,
            "inst_type": body.inst_type,
        }
        for r in results
    ]

    return {
        "success": True,
        "data": result_dicts,
        "scanned": len(symbols),
        "matched": len(results),
    }


@router.post("/scan/{profile_id}")
async def run_profile_scan(profile_id: str):
    """执行已保存方案的扫描"""
    storage = _get_storage()
    profile = await asyncio.to_thread(storage.get_scanner_profile, profile_id)
    if not profile:
        raise HTTPException(status_code=404, detail="扫描方案不存在")

    symbols = profile.get("symbols", [])
    if not symbols:
        available = await asyncio.to_thread(storage.get_available_symbols)
        symbols = [
            s["inst_id"] for s in available
            if s.get("inst_type", "SPOT") == profile.get("inst_type", "SPOT")
        ]

    conditions = [
        ScanCondition(
            indicator=c.get("indicator", ""),
            operator=c.get("operator", ""),
            value=c.get("value", 0),
            params=c.get("params", {}),
        )
        for c in profile.get("conditions", [])
    ]

    scanner = MarketScanner(storage)
    results = await asyncio.to_thread(
        scanner.scan,
        symbols=symbols,
        conditions=conditions,
        logic=profile.get("logic", "and"),
        timeframe=profile.get("timeframe", "1H"),
        inst_type=profile.get("inst_type", "SPOT"),
    )

    result_dicts = [
        {
            "inst_id": r.inst_id,
            "matched_conditions": r.matched_conditions,
            "indicator_values": r.indicator_values,
            "price": r.price,
            "timeframe": profile.get("timeframe", "1H"),
            "inst_type": profile.get("inst_type", "SPOT"),
        }
        for r in results
    ]

    # 保存扫描结果
    await asyncio.to_thread(storage.save_scanner_results, profile_id, result_dicts)

    return {
        "success": True,
        "data": result_dicts,
        "scanned": len(symbols),
        "matched": len(results),
    }


# ==================== 扫描结果与条件类型 ====================


@router.get("/results")
async def get_scan_results(
    profile_id: str = Query("", description="方案ID筛选"),
    limit: int = Query(50, ge=1, le=200),
):
    """获取扫描历史结果"""
    storage = _get_storage()
    results = await asyncio.to_thread(
        storage.get_scanner_results, profile_id=profile_id, limit=limit
    )
    return {"success": True, "data": results}


@router.get("/conditions")
async def get_available_conditions():
    """获取可用的筛选条件类型及参数说明"""
    return {"success": True, "data": AVAILABLE_CONDITIONS}
