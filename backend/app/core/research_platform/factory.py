from __future__ import annotations

from threading import Lock

from app.core.data_center_collection import CollectionRuntimeRegistry
from app.core.data_center_collection import CollectionSessionController
from app.core.data_center_collection import build_collection_runtime

from .census.orchestrator import CensusOrchestrator
from .census.observation_reader import StorageBackedCensusObservationReader
from .census.runtime import CensusObservationRuntime
from .census.scheduler import TargetCensusScheduler
from .census.session_activity import StorageBackedSessionActivityProvider
from .census.service import ResearchCensusService
from .census.universe import PreferenceBackedCensusUniverseProvider
from .census.universe import load_census_universe_settings
from .collection.service import ResearchCollectionService
from .dataset.materializer import BoundaryMaterializer
from .dataset.service import ResearchDatasetService
from .service import ResearchPlatformService
from .training.service import ResearchTrainingService


_service = None
_service_lock = Lock()
_SERVICE_METHOD_NAMES = tuple(
    name
    for name, value in vars(ResearchPlatformService).items()
    if callable(value) and not name.startswith('_')
)


def get_research_platform_service(ctx) -> ResearchPlatformService:
    global _service
    if _service_matches_contract(_service):
        return _service
    with _service_lock:
        if not _service_matches_contract(_service):
            _service = _build_research_platform_service(ctx)
    return _service


def _service_matches_contract(service) -> bool:
    if service is None:
        return False
    return all(callable(getattr(service, name, None)) for name in _SERVICE_METHOD_NAMES)


def _build_research_platform_service(ctx) -> ResearchPlatformService:
    storage = ctx.storage()
    dataset_service = ResearchDatasetService(storage=storage)
    boundary_materializer = BoundaryMaterializer(storage=storage)
    universe_provider = _build_census_universe_provider(ctx)
    scheduler = TargetCensusScheduler(
        census_service=ResearchCensusService(
            storage=storage,
            observation_reader=StorageBackedCensusObservationReader(storage=storage),
            session_activity_provider=StorageBackedSessionActivityProvider(storage=storage),
        ),
        inst_id_provider=universe_provider.list_inst_ids,
    )
    census_service = CensusOrchestrator(
        scheduler=scheduler,
        universe_provider=universe_provider,
        runtime_factory=lambda inst_id: CensusObservationRuntime(
            storage=storage,
            inst_id=inst_id,
            fetcher=ctx.fetcher(),
            ws_manager=ctx.ws_manager(),
        ),
    )
    registry = CollectionRuntimeRegistry()
    controller = CollectionSessionController(
        storage=storage,
        runtime_registry=registry,
        runtime_factory=lambda session, emit_event: build_collection_runtime(
            storage=storage,
            session=session,
            fetcher=ctx.fetcher(),
            ws_manager=ctx.ws_manager(),
            publish_event=emit_event,
            after_flush=boundary_materializer.handle_flushed_second,
        ),
    )
    return ResearchPlatformService(
        collection_service=ResearchCollectionService(
            storage=storage,
            controller=controller,
        ),
        census_service=census_service,
        dataset_service=dataset_service,
        training_service=ResearchTrainingService(
            storage=storage,
            dataset_service=dataset_service,
        ),
        storage=storage,
    )


def _build_census_universe_provider(ctx):
    return PreferenceBackedCensusUniverseProvider(
        cfg=ctx.cfg,
        settings_loader=load_census_universe_settings,
    )
