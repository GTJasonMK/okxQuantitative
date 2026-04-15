from __future__ import annotations


class StorageBackedCensusObservationReader:
    def __init__(self, *, storage):
        self._storage = storage

    def list_for_inst(
        self,
        inst_id: str,
        end_ts: int,
        lookback_sec: int,
    ) -> list[dict[str, object]]:
        return self._storage.list_research_census_second_states_for_inst(
            inst_id,
            end_ts=end_ts,
            lookback_sec=lookback_sec,
        )
