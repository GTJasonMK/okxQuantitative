from __future__ import annotations


from app.core.research_platform.dataset.constants import LABEL_VECTOR_FIELDS


OBSERVATION_FIELDS = LABEL_VECTOR_FIELDS
FORECAST_FIELD_PREFIX = 'forecast_'
SPREAD_SCALE = 100.0


def build_observation_row(row: dict[str, object]) -> dict[str, float]:
    return {
        field_name: float(row[field_name])
        for field_name in OBSERVATION_FIELDS
    }


def build_forecast_row(row: dict[str, object]) -> dict[str, float]:
    missing = [
        f'{FORECAST_FIELD_PREFIX}{field_name}'
        for field_name in OBSERVATION_FIELDS
        if f'{FORECAST_FIELD_PREFIX}{field_name}' not in row
    ]
    if missing:
        raise ValueError(f"forecast row missing predicted fields: {', '.join(missing)}")
    return {
        field_name: float(row[f'{FORECAST_FIELD_PREFIX}{field_name}'])
        for field_name in OBSERVATION_FIELDS
    }


def build_spread_last_bps(row: dict[str, object]) -> float:
    return float(row['spread_snapshot_bps']) * SPREAD_SCALE
