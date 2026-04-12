from __future__ import annotations

from pathlib import Path
from threading import Lock

from .model_store import DEFAULT_DIRECT_MODEL_PATH, load_direct_model_bundle
from .service import TrendResearchService
from .settings import build_default_trend_research_settings, load_trend_research_settings


_service = None
_service_lock = Lock()


def _load_saved_model_bundle():
    if not Path(DEFAULT_DIRECT_MODEL_PATH).exists():
        return None
    return load_direct_model_bundle()


def get_trend_research_service(ctx) -> TrendResearchService:
    global _service
    if _service is None:
        with _service_lock:
            if _service is None:
                cfg = ctx.cfg.trend_research
                defaults = build_default_trend_research_settings(cfg)
                settings = load_trend_research_settings(cfg)
                _service = TrendResearchService(
                    whitelist=settings["whitelist"],
                    storage=ctx.storage(),
                    fetcher=ctx.fetcher(),
                    ws_manager=ctx.ws_manager(),
                    ws_manager_supplier=ctx.ws_manager,
                    feature_bar_seconds=settings["feature_bar_seconds"],
                    state_sync_seconds=settings["state_sync_seconds"],
                    book_channel=settings["book_channel"],
                    enabled=settings["enabled"],
                    defaults=defaults,
                    cfg=cfg,
                    model_bundle=_load_saved_model_bundle(),
                )
                ctx.add_ws_restart_listener(_service.on_ws_manager_restart)
    return _service
