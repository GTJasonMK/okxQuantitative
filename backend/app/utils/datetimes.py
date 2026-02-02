# 时间/日期解析工具（可复用）
#
# 目标：
# - 统一 ISO8601 时间解析口径，避免各 API 各自实现导致行为不一致
# - 保持纯函数，便于复用与测试

from __future__ import annotations

from datetime import datetime


def parse_iso_datetime(value: str) -> datetime:
    """
    解析 ISO8601 时间字符串为 datetime。

    说明：
    - datetime.fromisoformat 不支持以 "Z" 结尾的 UTC 表示（例如 2024-01-01T00:00:00Z）
    - 这里做最小兼容：把 Z 转换为 +00:00，再交给 fromisoformat 解析
    """
    s = (value or "").strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    return datetime.fromisoformat(s)

