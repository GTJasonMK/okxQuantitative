from __future__ import annotations

from threading import Lock

from .governor import OKXOutboundGovernor
from .rules import OKXRateRuleRegistry
from .timeline import OKXOutboundTimelineStore


_timeline_store: OKXOutboundTimelineStore | None = None
_timeline_lock = Lock()
_governor: OKXOutboundGovernor | None = None
_governor_lock = Lock()


def get_okx_outbound_timeline_store() -> OKXOutboundTimelineStore:
    global _timeline_store
    if _timeline_store is None:
        with _timeline_lock:
            if _timeline_store is None:
                _timeline_store = OKXOutboundTimelineStore()
    return _timeline_store


def get_okx_outbound_governor() -> OKXOutboundGovernor:
    global _governor
    if _governor is None:
        with _governor_lock:
            if _governor is None:
                _governor = OKXOutboundGovernor(
                    registry=OKXRateRuleRegistry(),
                    timeline=get_okx_outbound_timeline_store(),
                )
    return _governor


__all__ = [
    "OKXOutboundGovernor",
    "OKXOutboundTimelineStore",
    "OKXRateRuleRegistry",
    "get_okx_outbound_governor",
    "get_okx_outbound_timeline_store",
]
