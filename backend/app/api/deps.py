# API 依赖注入工具（可复用）
#
# 目标：
# - 收敛各 API 模块重复的 get_ctx() 实现，统一从 AppContext 获取核心依赖入口
# - 便于后续扩展（例如添加统一的 mode 解析、鉴权开关、灰度策略等）

from __future__ import annotations

from fastapi import HTTPException

from ..core.app_context import AppContext, get_app_context


def get_ctx() -> AppContext:
    """获取应用上下文（单例）"""
    return get_app_context()


def require_current_mode(requested_mode: str, *, action: str = "交易操作") -> None:
    """
    要求 requested_mode 与系统当前默认模式一致。

    说明：
    - 允许“查看两套盘的数据”（查询接口可传 simulated/live）
    - 但所有会影响交易所状态的动作（下单/撤单/改杠杆/切仓位模式/启动实时策略等）必须严格跟随默认模式
    """
    current = get_ctx().default_mode()
    if requested_mode == current:
        return

    current_text = "模拟盘" if current == "simulated" else "实盘"
    requested_text = "模拟盘" if requested_mode == "simulated" else "实盘"
    raise HTTPException(
        status_code=403,
        detail=f"当前系统默认模式为{current_text}，已禁止在{requested_text}执行{action}。请在“系统设置”切换默认模式后重试。",
    )
