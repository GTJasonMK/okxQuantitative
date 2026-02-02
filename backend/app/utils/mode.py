# mode 工具函数
#
# 目标：
# - 统一 simulated/live 的规范化逻辑，避免在不同模块里重复实现
# - 不依赖 FastAPI/配置，保持纯函数，便于复用与测试

from __future__ import annotations

from typing import Any, Literal, Optional

Mode = Literal["simulated", "live"]


def normalize_mode(value: Any) -> Optional[Mode]:
    """把输入规范化为 'simulated'/'live'；非法值返回 None。"""
    if isinstance(value, str):
        v = value.strip().lower()
        if v in ("simulated", "live"):
            return v  # type: ignore[return-value]
    return None


def coerce_mode(value: Any, default: Mode) -> Mode:
    """把输入规范化为 'simulated'/'live'；非法值回退到 default。"""
    return normalize_mode(value) or default


def mode_from_bool(is_simulated: bool) -> Mode:
    """由 bool 转换为 mode 字符串。"""
    return "simulated" if is_simulated else "live"

