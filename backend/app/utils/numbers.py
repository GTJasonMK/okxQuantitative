# 数值解析与校验工具
#
# 目标：
# - 把 API 层“字符串数值校验”的重复逻辑收敛到可复用的纯函数中
# - 不依赖 FastAPI，便于在服务层/脚本/测试中复用

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Tuple


def parse_decimal_str(value: str) -> Tuple[str, Decimal]:
    """
    解析字符串 Decimal，返回 (原始去空格字符串, Decimal)。

    说明：
    - 项目里很多 OKX SDK 参数要求字符串（例如 sz/px），但我们仍希望在进入交易前做严格校验。
    """
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

