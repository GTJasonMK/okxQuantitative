# 用户偏好设置 API
# 保存用户的界面设置到文件系统

import asyncio
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..utils.preferences_store import (
    delete_preference_key,
    load_preferences,
    merge_preferences,
    save_preferences,
)


router = APIRouter(prefix="/api/preferences", tags=["preferences"])


class PreferencesData(BaseModel):
    """偏好设置数据模型"""
    # 行情监控设置
    market_selected_symbols: Optional[list] = None
    market_available_symbols: Optional[list] = None
    market_auto_refresh: Optional[bool] = None
    market_refresh_interval: Optional[int] = None
    market_indicators: Optional[dict] = None
    # 交易设置
    trading_default_symbol: Optional[str] = None
    # 可扩展其他设置...

@router.get("")
async def get_preferences():
    """
    获取所有用户偏好设置
    """
    preferences = await asyncio.to_thread(load_preferences)
    return {
        "success": True,
        "data": preferences
    }


@router.get("/{key}")
async def get_preference(key: str):
    """
    获取指定键的偏好设置
    """
    preferences = await asyncio.to_thread(load_preferences)
    if key in preferences:
        return {
            "success": True,
            "data": preferences[key]
        }
    return {
        "success": True,
        "data": None
    }


@router.post("")
async def save_all_preferences(data: Dict[str, Any]):
    """
    保存所有偏好设置（完全覆盖）
    """
    if await asyncio.to_thread(save_preferences, data):
        return {"success": True, "message": "偏好设置已保存"}
    raise HTTPException(status_code=500, detail="保存偏好设置失败")


@router.patch("")
async def update_preferences(data: Dict[str, Any]):
    """
    更新部分偏好设置（合并更新）
    """
    if await asyncio.to_thread(merge_preferences, data):
        return {"success": True, "message": "偏好设置已更新"}
    raise HTTPException(status_code=500, detail="更新偏好设置失败")


@router.delete("/{key}")
async def delete_preference(key: str):
    """
    删除指定的偏好设置
    """
    ok = await asyncio.to_thread(delete_preference_key, key)
    if ok:
        return {"success": True, "message": f"已删除设置: {key}"}
    raise HTTPException(status_code=500, detail="删除偏好设置失败")
