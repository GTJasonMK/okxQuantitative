from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from .models import FactorScore


SeriesComputer = Callable[[Sequence], list[float] | None]


@dataclass(frozen=True)
class FactorDefinition:
    name: str
    category: str
    tier: int
    required_fields: tuple[str, ...]
    compute_series: SeriesComputer
    availability: Callable[[Sequence], bool] | None = None
    unavailable_reason: str = ""

    def is_available(self, bars: Sequence) -> bool:
        if self.availability is not None:
            return self.availability(bars)
        if not bars:
            return False
        sample = bars[0]
        return all(hasattr(sample, field_name) for field_name in self.required_fields)

    def build_values(self, bars: Sequence) -> list[float] | None:
        if not self.is_available(bars):
            return None
        values = self.compute_series(bars)
        if values is None or len(values) != len(bars):
            return None
        return [float(value) for value in values]

    def build_placeholder_score(self, inst_id: str) -> FactorScore:
        return FactorScore(
            inst_id=inst_id,
            factor_name=self.name,
            spearman_ic=None,
            stability_score=None,
            redundancy_cluster=self.category or self.name,
            category=self.category,
            tier=self.tier,
            available=False,
            unavailable_reason=self.unavailable_reason,
        )
