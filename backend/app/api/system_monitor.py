from __future__ import annotations

import time

from fastapi import APIRouter, Depends, Query

from app.core.app_context import AppContext, get_app_context


router = APIRouter(prefix="/api/system", tags=["system-monitor"])


@router.get("/okx-outbound-timeline")
async def get_okx_outbound_timeline(
    window_seconds: int = Query(default=600, ge=10, le=3600),
    limit: int = Query(default=2000, ge=10, le=10000),
    ctx: AppContext = Depends(get_app_context),
):
    return ctx.okx_outbound_timeline().snapshot(
        window_seconds=window_seconds,
        now_ts=time.time(),
        limit=limit,
    )
