from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class OKXOutboundRule:
    op_key: str
    rule_key: str
    channel: str
    target_group: str
    window_seconds: int
    capacity: int


@dataclass(frozen=True)
class OKXOutboundEvent:
    ts: float
    op_key: str
    channel: str
    target_group: str
    rule_key: str
    scope_key: str
    inst_id: str = ""
    mode: str = ""
    result: str = "ok"
    latency_ms: int = 0

    def to_dict(self) -> dict:
        return asdict(self)
