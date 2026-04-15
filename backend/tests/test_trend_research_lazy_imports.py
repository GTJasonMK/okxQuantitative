import importlib
import sys


TREND_RESEARCH_MODULES = (
    "app.core",
    "app.core.app_context",
    "app.core.trend_research",
    "app.core.trend_research.factory",
    "app.core.trend_research.service",
    "app.core.trend_research.inference",
    "app.core.trend_research.training_runtime",
    "app.core.trend_research.direct_training",
    "app.core.trend_research.tcn_model",
)


def _clear_modules():
    for name in TREND_RESEARCH_MODULES:
        sys.modules.pop(name, None)


def test_importing_app_context_does_not_load_trend_research_runtime_modules():
    _clear_modules()

    importlib.import_module("app.core.app_context")

    assert "app.core.trend_research.factory" not in sys.modules
    assert "app.core.trend_research.service" not in sys.modules
    assert "app.core.trend_research.direct_training" not in sys.modules
    assert "app.core.trend_research.tcn_model" not in sys.modules


def test_importing_inference_does_not_load_direct_training_until_runtime():
    _clear_modules()

    importlib.import_module("app.core.trend_research.inference")

    assert "app.core.trend_research.direct_training" not in sys.modules
