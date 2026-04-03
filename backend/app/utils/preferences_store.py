from __future__ import annotations

from threading import Lock
from typing import Any, Dict

from ..config import CONFIG_DIR
from .files import atomic_write_json, read_json_file


PREFERENCES_FILE = CONFIG_DIR / "user_preferences.json"
_PREFERENCES_LOCK = Lock()


def load_preferences() -> Dict[str, Any]:
    """从本地文件读取用户偏好。"""
    return read_json_file(PREFERENCES_FILE, default={})


def save_preferences(data: Dict[str, Any]) -> bool:
    """完整覆盖保存偏好设置。"""
    try:
        with _PREFERENCES_LOCK:
            atomic_write_json(PREFERENCES_FILE, data, ensure_ascii=False, indent=2)
        return True
    except Exception as exc:
        print(f"[PreferencesStore] 保存偏好设置失败: {exc}")
        return False


def merge_preferences(partial: Dict[str, Any]) -> bool:
    """原子合并更新偏好设置。"""
    try:
        with _PREFERENCES_LOCK:
            current = load_preferences()
            current.update(partial)
            atomic_write_json(PREFERENCES_FILE, current, ensure_ascii=False, indent=2)
        return True
    except Exception as exc:
        print(f"[PreferencesStore] 合并更新偏好设置失败: {exc}")
        return False


def delete_preference_key(key: str) -> bool:
    """原子删除指定偏好键。"""
    try:
        with _PREFERENCES_LOCK:
            current = load_preferences()
            if key not in current:
                return True
            del current[key]
            atomic_write_json(PREFERENCES_FILE, current, ensure_ascii=False, indent=2)
        return True
    except Exception as exc:
        print(f"[PreferencesStore] 删除偏好设置失败: {exc}")
        return False
