from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from app.core.app_context import AppContext, get_app_context
from app.core.research_platform_delete_errors import DatasetDeleteBlockedError


router = APIRouter(prefix='/api/research-platform', tags=['Research Platform'])


class ResearchSessionCreateRequest(BaseModel):
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


class DatasetCreateRequest(BaseModel):
    included_session_ids: list[str]
    sample_filter_rule: str
    feature_recipe_version: str
    label_definition_version: str
    integrity_policy_version: str
    deployment_target_version: str
    target_census_policy_version: str
    target_window_policy_version: str
    shift_state_definition_version: str
    shift_assumption_version: str
    shift_diagnostic_version: str
    strata_definition_version: str
    sampling_stride_sec: int = Field(ge=1)
    split_definition_version: str
    embargo_sec: int = Field(ge=0)
    weighting_version: str
    weight_definition: str
    weight_estimator_version: str
    refit_policy_version: str
    domain_classifier_version: str = ''
    regime_definition_version: str
    bootstrap_definition_version: str
    evaluation_protocol_version: str
    score_definition_version: str
    prerank_definition_version: str
    policy_definition_version: str
    policy_parameter_ref: str
    decision_utility_version: str
    utility_parameter_ref: str
    execution_assumption_version: str
    multiple_comparison_version: str


class TrainingRunCreateRequest(BaseModel):
    dataset_id: str
    candidate_set_ref: str
    model_family: str
    model_spec_ref: str
    training_seed: int = Field(ge=0)


@router.post('/sessions')
async def start_session(request: ResearchSessionCreateRequest, ctx: AppContext = Depends(get_app_context)):
    session = await ctx.research_platform().start_collection_session(request.model_dump())
    return {'session': session}


@router.get('/sessions')
async def list_sessions(limit: int = 50, ctx: AppContext = Depends(get_app_context)):
    return {'sessions': ctx.research_platform().list_collection_sessions(limit=limit)}


@router.get('/sessions/{session_id}')
async def get_session(session_id: str, ctx: AppContext = Depends(get_app_context)):
    session = ctx.research_platform().get_collection_session_detail(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail='research session not found')
    return {'session': session}


@router.post('/sessions/{session_id}/stop')
async def stop_session(session_id: str, ctx: AppContext = Depends(get_app_context)):
    session = await ctx.research_platform().stop_collection_session(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail='research session not found')
    return {'session': session}


@router.get('/census/status')
async def get_census_status(ctx: AppContext = Depends(get_app_context)):
    return {'status': ctx.research_platform().get_census_status()}


@router.post('/datasets')
async def create_dataset(request: DatasetCreateRequest, ctx: AppContext = Depends(get_app_context)):
    try:
        dataset = ctx.research_platform().create_dataset_manifest(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {'dataset': dataset}


@router.get('/datasets')
async def list_datasets(limit: int = 50, ctx: AppContext = Depends(get_app_context)):
    return {'datasets': ctx.research_platform().list_dataset_manifests(limit=limit)}


@router.get('/datasets/{dataset_id}')
async def get_dataset(dataset_id: str, ctx: AppContext = Depends(get_app_context)):
    dataset = ctx.research_platform().get_dataset_manifest(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail='dataset manifest not found')
    return {'dataset': dataset}


@router.delete('/datasets/{dataset_id}')
async def delete_dataset(dataset_id: str, ctx: AppContext = Depends(get_app_context)):
    try:
        deleted = ctx.research_platform().delete_dataset_manifest(dataset_id)
    except DatasetDeleteBlockedError as exc:
        raise HTTPException(status_code=409, detail=exc.to_detail()) from exc
    if deleted is None:
        raise HTTPException(status_code=404, detail='dataset manifest not found')
    return {'deleted_dataset': deleted}


@router.get('/datasets/{dataset_id}/preview')
async def get_dataset_preview(dataset_id: str, ctx: AppContext = Depends(get_app_context)):
    dataset = ctx.research_platform().get_dataset_manifest(dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail='dataset manifest not found')
    fit_preview = ctx.research_platform().get_dataset_fit_artifact_preview(dataset_id)
    return {
        'preview': {
            'manifest': dataset,
            'protocol_validation_status': ctx.research_platform().get_dataset_protocol_validation_status(dataset_id),
            'split_summary': ctx.research_platform().get_dataset_split_summary(dataset_id),
            'weight_summary': ctx.research_platform().get_dataset_weight_summary(dataset_id),
            'regime_schema': ctx.research_platform().get_dataset_regime_schema(dataset_id),
            'n_eff_summary': ctx.research_platform().get_dataset_effective_size_summary(dataset_id),
            'shift_diagnostic_preview': ctx.research_platform().get_dataset_shift_diagnostic_preview(dataset_id),
            'shift_diagnostics_bundle': (
                ctx.research_platform().get_dataset_shift_diagnostics_bundle(dataset_id)
            ),
            'strata_fit_bundle': fit_preview['strata_fit_bundle'],
            'weight_fit_bundle': fit_preview['weight_fit_bundle'],
            'domain_classifier_fit_bundle': fit_preview['domain_classifier_fit_bundle'],
        }
    }


@router.post('/training-runs')
async def start_training_run(request: TrainingRunCreateRequest, ctx: AppContext = Depends(get_app_context)):
    try:
        run = ctx.research_platform().start_training_run(request.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {'training_run': run}


@router.get('/training-runs')
async def list_training_runs(
    dataset_id: str | None = None,
    limit: int = 50,
    ctx: AppContext = Depends(get_app_context),
):
    return {
        'training_runs': ctx.research_platform().list_training_runs(
            dataset_id=dataset_id,
            limit=limit,
        )
    }


@router.get('/training-runs/{run_id}')
async def get_training_run(run_id: str, ctx: AppContext = Depends(get_app_context)):
    try:
        training_run = ctx.research_platform().get_training_run_detail(run_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if training_run is None:
        raise HTTPException(status_code=404, detail='training run not found')
    return {'training_run': training_run}
