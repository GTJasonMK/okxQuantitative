# 用户偏好设置 API
# 保存用户的界面设置到文件系统

import asyncio
from threading import Lock
from typing import Any, Dict, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from ..config import CONFIG_DIR
from ..utils.files import read_json_file, atomic_write_json


router = APIRouter(prefix="/api/preferences", tags=["preferences"])

# 偏好设置文件路径
PREFERENCES_FILE = CONFIG_DIR / "user_preferences.json"
_PREFERENCES_LOCK = Lock()


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


def load_preferences() -> Dict[str, Any]:
    """从文件加载偏好设置"""
    return read_json_file(PREFERENCES_FILE, default={})


def save_preferences(data: Dict[str, Any]) -> bool:
    """保存偏好设置到文件"""
    try:
        # 原子写入：避免进程中断/并发写导致文件损坏
        with _PREFERENCES_LOCK:
            atomic_write_json(PREFERENCES_FILE, data, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[Preferences] 保存偏好设置失败: {e}")
        return False


def merge_preferences(partial: Dict[str, Any]) -> bool:
    """合并更新偏好设置（原子操作，避免并发丢失更新）"""
    try:
        with _PREFERENCES_LOCK:
            current = load_preferences()
            current.update(partial)
            atomic_write_json(PREFERENCES_FILE, current, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[Preferences] 合并更新偏好设置失败: {e}")
        return False


def delete_preference_key(key: str) -> bool:
    """删除指定键（原子操作）"""
    try:
        with _PREFERENCES_LOCK:
            current = load_preferences()
            if key not in current:
                return True
            del current[key]
            atomic_write_json(PREFERENCES_FILE, current, ensure_ascii=False, indent=2)
        return True
    except Exception as e:
        print(f"[Preferences] 删除偏好设置失败: {e}")
        return False


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
