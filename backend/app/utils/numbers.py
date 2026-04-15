# 数值解析与校验工具
#
# 目标：
# - 把 API 层字符串数值校验的重复逻辑收敛到可复用的纯函数中
# - 不依赖 FastAPI，便于在服务层/脚本/测试中复用

from __future__ import annotations

import math
from decimal import Decimal, InvalidOperation
from typing import Any, Tuple


def safe_float_convert(value: Any, default: float = 0.0) -> float:
    """安全转换任意值为浮点数，异常时返回默认值。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_float_finite(value: float) -> float:
    """将 inf/nan 转换为安全的有限浮点数，防止 JSON 序列化崩溃。"""
    if math.isinf(value):
        return 9999.99 if value > 0 else -9999.99
    if math.isnan(value):
        return 0.0
    return value


def clamp_int(value: Any, *, default: int, minimum: int, maximum: int) -> int:
    """安全转换为 int 并限制在 [minimum, maximum] 范围内。"""
    try:
        numeric = int(value)
    except (TypeError, ValueError):
        return default
    return max(minimum, min(maximum, numeric))


def parse_decimal_str(value: str) -> Tuple[str, Decimal]:
    """解析字符串 Decimal，返回 (原始去空格字符串, Decimal)。"""
    s = (value or "").strip()
    try:
        d = Decimal(s)
    except (InvalidOperation, TypeError) as e:
        raise ValueError(f"无法解析为数值: {value!r}") from e
    return s, d


def require_positive_decimal_str(value: str) -> str:
    """要求为有限正数，返回去空格后的原始字符串。"""
    s, d = parse_decimal_str(value)
    if not d.is_finite() or d <= 0:
        raise ValueError(f"必须为正数: {value!r}")
    return s


def require_positive_int_str(value: str) -> str:
    """要求为有限正整数（用于合约张数等），返回去空格后的原始字符串。"""
    s, d = parse_decimal_str(value)
    if not d.is_finite() or d <= 0:
        raise ValueError(f"必须为正整数: {value!r}")
    if d != d.to_integral_value():
        raise ValueError(f"必须为正整数: {value!r}")
    return s
