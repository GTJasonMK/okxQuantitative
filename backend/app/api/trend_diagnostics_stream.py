from __future__ import annotations

import asyncio
from typing import Callable


TREND_DIAGNOSTICS_SNAPSHOT_INTERVAL_SECONDS = 1.0


class TrendDiagnosticsSnapshotPump:
    def __init__(
        self,
        *,
        list_subscribers: Callable[[], list[tuple[object, str, int]]],
        send_snapshot,
        disconnect,
    ):
        self._list_subscribers = list_subscribers
        self._send_snapshot = send_snapshot
        self._disconnect = disconnect
        self._task = None
        self._loop = None

    def _ensure_loop_state(self) -> None:
        loop = asyncio.get_running_loop()
        if self._loop is loop:
            return
        self._loop = loop
        self._task = None

    def ensure_running(self) -> None:
        self._ensure_loop_state()
        if not self._list_subscribers():
            return
        if self._task is not None and not self._task.done():
            return
        self._task = asyncio.create_task(
            self._run(),
            name="trend_diagnostics_snapshot_pump",
        )

    async def broadcast_once(self) -> None:
        subscribers = list(self._list_subscribers())
        disconnected = []
        for websocket, inst_id, timeline_limit in subscribers:
            try:
                await self._send_snapshot(websocket, inst_id, timeline_limit)
            except Exception:
                disconnected.append(websocket)
        for websocket in disconnected:
            self._disconnect(websocket)

    async def _run(self) -> None:
        try:
            while True:
                await asyncio.sleep(TREND_DIAGNOSTICS_SNAPSHOT_INTERVAL_SECONDS)
                if not self._list_subscribers():
                    return
                await self.broadcast_once()
        finally:
            if self._task is asyncio.current_task():
                self._task = None
