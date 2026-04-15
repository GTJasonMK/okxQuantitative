from __future__ import annotations

import time

from app.core.trend_research.models import BookTopEvent
from app.core.trend_research.models import TradeTickEvent


class MarketFeedAdapter:
    def __init__(self, *, ws_manager, inst_id, book_channel):
        self._ws_manager = ws_manager
        self._inst_id = inst_id
        self._book_channel = book_channel
        self._trade_callback = None
        self._book_callback = None

    async def start(self, *, on_trade, on_book) -> None:
        self._trade_callback = self._build_trade_callback(on_trade)
        self._book_callback = self._build_book_callback(on_book)
        self._ws_manager.add_trade_callback(self._trade_callback)
        self._ws_manager.add_book_callback(self._book_callback)
        await self._ws_manager.subscribe_trades([self._inst_id])
        await self._ws_manager.subscribe_books([self._inst_id], channel=self._book_channel)

    async def stop(self) -> None:
        if self._trade_callback is not None:
            self._ws_manager.remove_trade_callback(self._trade_callback)
            self._trade_callback = None
        if self._book_callback is not None:
            self._ws_manager.remove_book_callback(self._book_callback)
            self._book_callback = None
        await self._ws_manager.unsubscribe_trades([self._inst_id])
        await self._ws_manager.unsubscribe_books([self._inst_id], channel=self._book_channel)

    def _build_trade_callback(self, on_trade):
        def _callback(inst_id: str, event: TradeTickEvent) -> None:
            if inst_id != self._inst_id:
                return
            on_trade(event)

        return _callback

    def _build_book_callback(self, on_book):
        def _callback(inst_id: str, event: BookTopEvent) -> None:
            if inst_id != self._inst_id:
                return
            on_book(event)

        return _callback

    def normalize(self, payload: dict[str, object]) -> list[TradeTickEvent | BookTopEvent]:
        channel = str(payload.get('arg', {}).get('channel', ''))
        inst_id = str(payload.get('arg', {}).get('instId', self._inst_id))
        if inst_id != self._inst_id:
            return []
        if channel == 'trades':
            return self._normalize_trades(payload.get('data') or [], inst_id)
        if channel == self._book_channel:
            return self._normalize_books(payload.get('data') or [], inst_id)
        return []

    def _normalize_trades(self, items, inst_id: str) -> list[TradeTickEvent]:
        events: list[TradeTickEvent] = []
        for item in items:
            events.append(
                TradeTickEvent(
                    inst_id=inst_id,
                    ts_exchange=int(item.get('ts', 0)) / 1000.0,
                    ts_local=time.time(),
                    price=float(item.get('px', 0.0)),
                    size=float(item.get('sz', 0.0)),
                    side=str(item.get('side', '')),
                )
            )
        return events

    def _normalize_books(self, items, inst_id: str) -> list[BookTopEvent]:
        events: list[BookTopEvent] = []
        for item in items:
            asks = item.get('asks') or []
            bids = item.get('bids') or []
            if not asks or not bids:
                continue
            events.append(
                BookTopEvent(
                    inst_id=inst_id,
                    ts_exchange=int(item.get('ts', 0)) / 1000.0,
                    ts_local=time.time(),
                    bid_price=float(bids[0][0]),
                    ask_price=float(asks[0][0]),
                    bid_size=float(bids[0][1]),
                    ask_size=float(asks[0][1]),
                    bid_levels=tuple((float(level[0]), float(level[1])) for level in bids),
                    ask_levels=tuple((float(level[0]), float(level[1])) for level in asks),
                )
            )
        return events
