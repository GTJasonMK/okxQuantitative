from __future__ import annotations

from typing import Callable


class ResearchCollectionService:
    def __init__(self, *, storage, controller):
        self._storage = storage
        self._controller = controller
        self._listeners: list[Callable[[dict[str, object]], None]] = []

    def add_listener(self, listener: Callable[[dict[str, object]], None]) -> None:
        if listener not in self._listeners:
            self._listeners.append(listener)

    def remove_listener(self, listener: Callable[[dict[str, object]], None]) -> None:
        if listener in self._listeners:
            self._listeners.remove(listener)

    def emit_event(self, payload: dict[str, object]) -> None:
        for listener in list(self._listeners):
            listener(payload)

    async def start_collection_session(self, payload: dict[str, object]) -> dict[str, object]:
        if 'source_config_hash' not in payload:
            payload = {**payload, 'source_config_hash': 'manual'}
        return await self._controller.start_session(payload, emit_event=self.emit_event)

    async def stop_collection_session(self, session_id: str, *, stop_reason: str = 'manual_stop') -> dict[str, object] | None:
        session = self._storage.get_research_collection_session(session_id)
        if session is None:
            return None
        return await self._controller.stop_session(
            session_id,
            stop_reason=stop_reason,
            emit_event=self.emit_event,
        )

    async def delete_collection_session(self, session_id: str) -> dict[str, object] | None:
        session = self._storage.get_research_collection_session(session_id)
        if session is None:
            return None
        return await self._controller.delete_session(
            session_id,
            emit_event=self.emit_event,
        )
