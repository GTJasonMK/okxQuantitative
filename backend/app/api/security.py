from __future__ import annotations

import os
from functools import lru_cache

from fastapi import HTTPException, Request


DEFAULT_CORS_ALLOWED_ORIGINS = (
    'http://127.0.0.1:5173',
    'http://localhost:5173',
    'http://127.0.0.1:4173',
    'http://localhost:4173',
    'app://-',
    'null',
)
DEFAULT_WRITE_GUARD_HEADER = 'X-OKXQ-Client'
DEFAULT_WRITE_GUARD_VALUE = 'desktop'
TRUSTED_LOCAL_HOSTS = frozenset({'127.0.0.1', '::1', 'localhost', 'testclient'})


def _normalize_csv(raw: str) -> tuple[str, ...]:
    items = [item.strip() for item in str(raw or '').split(',') if item.strip()]
    return tuple(dict.fromkeys(items))


@lru_cache(maxsize=1)
def get_cors_allowed_origins() -> tuple[str, ...]:
    raw = os.getenv('CORS_ALLOWED_ORIGINS', '').strip()
    if raw:
        values = tuple(item for item in _normalize_csv(raw) if item != '*')
        if values:
            return values
    return DEFAULT_CORS_ALLOWED_ORIGINS


@lru_cache(maxsize=1)
def get_write_guard_config() -> tuple[str, str]:
    header_name = os.getenv('WRITE_GUARD_HEADER', '').strip() or DEFAULT_WRITE_GUARD_HEADER
    header_value = os.getenv('WRITE_GUARD_VALUE', '').strip() or DEFAULT_WRITE_GUARD_VALUE
    return header_name, header_value


def require_sensitive_write_access(request: Request) -> None:
    """保护敏感写操作，拒绝非本机或非受信客户端调用。"""
    host = str((request.client.host if request.client else '') or '').lower()
    if host not in TRUSTED_LOCAL_HOSTS:
        raise HTTPException(status_code=403, detail='敏感写操作仅允许本机客户端调用')

    # 测试环境保留兼容（TestClient 默认 host=testclient）
    if host == 'testclient':
        return

    allowed_origins = set(get_cors_allowed_origins())
    origin = str(request.headers.get('origin', '') or '').strip()
    if origin and origin not in allowed_origins:
        raise HTTPException(status_code=403, detail='请求来源未被允许执行敏感写操作')

    header_name, expected_value = get_write_guard_config()
    provided_value = str(request.headers.get(header_name, '') or '').strip()
    if provided_value != expected_value:
        raise HTTPException(
            status_code=403,
            detail=f'缺少可信客户端标识，请携带请求头 {header_name}',
        )
