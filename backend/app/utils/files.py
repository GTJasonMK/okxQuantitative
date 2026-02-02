# 文件读写工具（可复用）
#
# 目标：
# - 提供可复用的“原子写入”能力，避免并发/进程中断导致 JSON 配置文件损坏
# - 不依赖 FastAPI，便于在 API/服务层/脚本/单测中复用

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Mapping, MutableMapping, TypeVar

T = TypeVar("T")


def read_json_file(path: str | Path, *, default: T) -> T:
    """
    读取 JSON 文件；文件不存在或解析失败时返回 default。

    说明：
    - 该函数“偏容错”，更适合读取用户偏好/本地缓存等非关键配置。
    """
    p = Path(path)
    if not p.exists():
        return default
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def atomic_write_json(path: str | Path, data: Any, *, ensure_ascii: bool = False, indent: int = 2) -> None:
    """
    原子写入 JSON 文件。

    实现：
    - 写到同目录临时文件
    - fsync 确保落盘
    - os.replace 原子替换到目标路径
    """
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    tmp_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=str(p.parent),
            delete=False,
        ) as f:
            json.dump(data, f, ensure_ascii=ensure_ascii, indent=indent)
            f.flush()
            os.fsync(f.fileno())
            tmp_path = f.name
        os.replace(tmp_path, p)
    finally:
        # 异常时尽力清理临时文件；成功替换后 tmp_path 通常已不存在
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

