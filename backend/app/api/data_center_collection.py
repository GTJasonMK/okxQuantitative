from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import require_sensitive_write_access
from app.core.app_context import AppContext, get_app_context
from app.core.data_center_collection.errors import CollectionSessionBootstrapError
from app.core.research_platform_delete_errors import CollectionSessionDeleteBlockedError


router = APIRouter(prefix='/api/data-center/collections', tags=['Data Center Collection'])


class DataCenterCollectionSessionCreateRequest(BaseModel):
    inst_id: str
    planned_duration_sec: int = Field(ge=1)
    trigger_mode: str
    trigger_note: str = ''
    sampling_policy_id: str
    integrity_policy_version: str
    collector_version: str
    feature_recipe_version: str
    book_channel: str
    source_config_hash: str = 'manual'


@router.get('/sessions')
async def list_collection_sessions(
    limit: int = 50,
    ctx: AppContext = Depends(get_app_context),
):
    return {'sessions': ctx.research_platform().list_collection_sessions(limit=limit)}


@router.get('/sessions/{session_id}')
async def get_collection_session(
    session_id: str,
    ctx: AppContext = Depends(get_app_context),
):
    session = ctx.research_platform().get_collection_session_detail(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail='collection session not found')
    return {'session': session}


@router.post('/sessions')
async def start_collection_session(
    request: DataCenterCollectionSessionCreateRequest,
    ctx: AppContext = Depends(get_app_context),
    _guard: None = Depends(require_sensitive_write_access),
):
    try:
        session = await ctx.research_platform().start_collection_session(request.model_dump())
    except CollectionSessionBootstrapError as exc:
        raise HTTPException(status_code=503, detail=exc.detail) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    return {'session': session}


@router.post('/sessions/{session_id}/stop')
async def stop_collection_session(
    session_id: str,
    ctx: AppContext = Depends(get_app_context),
    _guard: None = Depends(require_sensitive_write_access),
):
    session = await ctx.research_platform().stop_collection_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail='collection session not found')
    return {'session': session}


@router.delete('/sessions/{session_id}')
async def delete_collection_session(
    session_id: str,
    ctx: AppContext = Depends(get_app_context),
    _guard: None = Depends(require_sensitive_write_access),
):
    try:
        deleted = await ctx.research_platform().delete_collection_session(session_id)
    except CollectionSessionDeleteBlockedError as exc:
        raise HTTPException(status_code=409, detail=exc.to_detail()) from exc
    if deleted is None:
        raise HTTPException(status_code=404, detail='collection session not found')
    return {'deleted_session': deleted}


@router.get('/census/status')
async def get_collection_census_status(
    ctx: AppContext = Depends(get_app_context),
):
    return {'status': ctx.research_platform().get_census_status()}
