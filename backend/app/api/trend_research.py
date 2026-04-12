from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.core.app_context import AppContext, get_app_context
from app.core.trend_research.process_view import build_trend_process_snapshot
from app.core.trend_research.realtime import resolve_trend_status
from app.core.trend_research.research_runtime import DEFAULT_FACTOR_LOOKBACK


router = APIRouter(prefix="/api/trend-research", tags=["trend-research"])

MAX_FEATURE_BAR_SECONDS = 60
MAX_STATE_SYNC_SECONDS = 3600
MIN_FACTOR_LOOKBACK_SECONDS = 1800
MAX_FACTOR_LOOKBACK_SECONDS = 7200


class TrendResearchConfigRequest(BaseModel):
    enabled: bool = Field(default=False)
    whitelist: list[str] | str = Field(default_factory=list)
    feature_bar_seconds: int = Field(default=1, ge=1, le=MAX_FEATURE_BAR_SECONDS)
    state_sync_seconds: int = Field(default=30, ge=5, le=MAX_STATE_SYNC_SECONDS)
    book_channel: str = Field(default="books5")


def _response_meta(service, rows):
    settings = service.get_settings()
    runtime_error = str(getattr(service, "get_runtime_error", lambda: "")() or "")
    return {
        "enabled": bool(settings["enabled"]),
        "status": resolve_trend_status(
            enabled=bool(settings["enabled"]),
            whitelist=settings["whitelist"],
            rows=rows,
            runtime_error=runtime_error,
        ),
        "whitelist": list(settings["whitelist"]),
        "runtime_error": runtime_error,
        "model_status": _model_payload(service),
    }


def _model_payload(service):
    return dict(getattr(service, "get_model_status", lambda: {})() or {})


@router.get("/inference")
async def get_inference(
    limit: int = Query(default=100, ge=1, le=500),
    ctx: AppContext = Depends(get_app_context),
):
    service = ctx.trend_research()
    rows = service.list_inference(limit=limit)
    return {
        **_response_meta(service, rows),
        "rows": rows,
    }


@router.get("/process")
async def get_process(
    bar_limit: int = Query(default=20, ge=1, le=120),
    ctx: AppContext = Depends(get_app_context),
):
    service = ctx.trend_research()
    rows = service.list_inference(limit=1)
    payload = (
        service.build_process_snapshot(bar_limit=bar_limit)
        if hasattr(service, "build_process_snapshot")
        else build_trend_process_snapshot(service, bar_limit=bar_limit)
    )
    return {
        **_response_meta(service, rows),
        **payload,
    }


@router.get("/diagnostics")
async def get_diagnostics(
    inst_id: str | None = Query(default=None),
    timeline_limit: int = Query(default=40, ge=5, le=200),
    ctx: AppContext = Depends(get_app_context),
):
    service = ctx.trend_research()
    return service.build_diagnostics_snapshot(
        inst_id=inst_id,
        timeline_limit=timeline_limit,
    )


@router.get("/feature-bars/{inst_id}")
async def get_feature_bars(
    inst_id: str,
    limit: int = Query(default=120, ge=1, le=2000),
    ctx: AppContext = Depends(get_app_context),
):
    service = ctx.trend_research()
    rows = service.list_inference(limit=1)
    return {
        **_response_meta(service, rows),
        "inst_id": inst_id,
        "rows": service.list_feature_bars(inst_id, limit=limit),
    }


@router.get("/factors/{inst_id}")
async def get_factors(
    inst_id: str,
    lookback: int = Query(
        default=DEFAULT_FACTOR_LOOKBACK,
        ge=MIN_FACTOR_LOOKBACK_SECONDS,
        le=MAX_FACTOR_LOOKBACK_SECONDS,
    ),
    limit: int = Query(default=20, ge=1, le=100),
    ctx: AppContext = Depends(get_app_context),
):
    service = ctx.trend_research()
    rows = service.list_inference(limit=1)
    factor_rows = service.rebuild_factor_scores(inst_id, lookback=lookback, limit=limit)
    return {
        **_response_meta(service, rows),
        "inst_id": inst_id,
        "lookback": lookback,
        "rows": factor_rows,
    }


@router.get("/factor-series/{inst_id}")
async def get_factor_series(
    inst_id: str,
    lookback: int = Query(
        default=DEFAULT_FACTOR_LOOKBACK,
        ge=MIN_FACTOR_LOOKBACK_SECONDS,
        le=MAX_FACTOR_LOOKBACK_SECONDS,
    ),
    limit: int | None = Query(default=None, ge=1, le=MAX_FACTOR_LOOKBACK_SECONDS),
    ctx: AppContext = Depends(get_app_context),
):
    service = ctx.trend_research()
    rows = service.list_inference(limit=1)
    payload = service.list_factor_series(inst_id, lookback=lookback, limit=limit)
    return {
        **_response_meta(service, rows),
        **payload,
    }


@router.get("/config")
async def get_config(ctx: AppContext = Depends(get_app_context)):
    service = ctx.trend_research()
    settings = service.get_settings()
    rows = service.list_inference(limit=1)
    return {
        "settings": settings,
        "defaults": service.get_default_settings(),
        **_response_meta(service, rows),
    }


@router.get("/model")
async def get_model(ctx: AppContext = Depends(get_app_context)):
    service = ctx.trend_research()
    rows = service.list_inference(limit=1)
    return {
        "model": _model_payload(service),
        **_response_meta(service, rows),
    }


@router.get("/training-run")
async def get_training_run(ctx: AppContext = Depends(get_app_context)):
    service = ctx.trend_research()
    rows = service.list_inference(limit=1)
    return {
        **_response_meta(service, rows),
        "training_run": dict(getattr(service, "get_training_run", lambda: {})() or {}),
    }


@router.post("/model/retrain")
async def retrain_model(
    lookback: int = Query(
        default=DEFAULT_FACTOR_LOOKBACK,
        ge=MIN_FACTOR_LOOKBACK_SECONDS,
        le=MAX_FACTOR_LOOKBACK_SECONDS,
    ),
    ctx: AppContext = Depends(get_app_context),
):
    service = ctx.trend_research()
    try:
        training_run = await service.start_retrain_model(lookback=lookback)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    rows = service.list_inference(limit=1)
    return {
        "model": _model_payload(service),
        **_response_meta(service, rows),
        "training_run": training_run,
    }


@router.put("/config")
async def update_config(
    request: TrendResearchConfigRequest,
    ctx: AppContext = Depends(get_app_context),
):
    service = ctx.trend_research()
    try:
        settings = await service.apply_settings(request.model_dump(), persist=True)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    rows = service.list_inference(limit=1)
    return {
        "settings": settings,
        **_response_meta(service, rows),
    }
