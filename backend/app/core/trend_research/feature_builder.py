from __future__ import annotations

BASIS_BPS_MULTIPLIER = 10000.0
MULTI_LEVEL_MIN_LEVELS = 2
DEPTH_WINDOW_BPS = 10.0

from .models import (
    BookTopEvent,
    ContractStateSnapshot,
    FeatureBuilderRuntimeSnapshot,
    FeatureBar1s,
    TradeTickEvent,
)


class FeatureBarBuilder:
    """把单币种实时事件压成统一 1 秒特征条。"""

    def __init__(self, inst_id: str):
        self._inst_id = inst_id
        self._book: BookTopEvent | None = None
        self._contract_state: ContractStateSnapshot | None = None
        self._last_trade: TradeTickEvent | None = None
        self._oi_delta = 0.0
        self._funding_delta = 0.0
        self._signed_trade_notional = 0.0
        self._trade_count = 0
        self._buy_notional = 0.0
        self._sell_notional = 0.0
        self._buy_count = 0
        self._sell_count = 0
        self._max_trade_notional = 0.0
        self._buy_burst_count = 0
        self._sell_burst_count = 0
        self._buy_burst_notional = 0.0
        self._sell_burst_notional = 0.0
        self._current_streak_side = ""
        self._current_streak_count = 0
        self._current_streak_notional = 0.0
        self._open_price = 0.0
        self._high_price = 0.0
        self._low_price = 0.0
        self._close_price = 0.0

    def apply_trade(self, event: TradeTickEvent) -> None:
        notional = event.price * event.size
        direction = 1.0 if str(event.side).lower() == "buy" else -1.0
        self._signed_trade_notional += direction * notional
        self._trade_count += 1
        self._max_trade_notional = max(self._max_trade_notional, notional)
        self._apply_trade_side(event.side, notional)
        self._apply_trade_streak(event.side, notional)
        self._apply_trade_price(event.price)
        self._last_trade = event

    def apply_book(self, event: BookTopEvent) -> None:
        self._book = event

    def apply_contract_state(self, snapshot: ContractStateSnapshot) -> None:
        previous_oi = self._contract_state.open_interest if self._contract_state else snapshot.open_interest
        previous_funding = self._contract_state.funding_rate if self._contract_state else snapshot.funding_rate
        self._oi_delta = snapshot.open_interest - previous_oi
        self._funding_delta = snapshot.funding_rate - previous_funding
        self._contract_state = snapshot

    def has_snapshot(self) -> bool:
        return self._book is not None or self._contract_state is not None or self._trade_count > 0

    def build_runtime_snapshot(self) -> FeatureBuilderRuntimeSnapshot:
        return FeatureBuilderRuntimeSnapshot(
            inst_id=self._inst_id,
            has_trade_input=self._last_trade is not None or self._trade_count > 0,
            has_book_input=self._book is not None,
            has_contract_state=self._contract_state is not None,
            pending_trade_count=self._trade_count,
            last_trade_ts_local=self._last_trade.ts_local if self._last_trade else None,
            last_book_ts_local=self._book.ts_local if self._book else None,
            last_state_ts_local=self._contract_state.ts_local if self._contract_state else None,
            last_trade_price=self._last_trade.price if self._last_trade else 0.0,
            last_trade_side=self._last_trade.side if self._last_trade else "",
        )

    def _apply_trade_side(self, side: str, notional: float) -> None:
        if str(side).lower() == "buy":
            self._buy_notional += notional
            self._buy_count += 1
            return
        self._sell_notional += notional
        self._sell_count += 1

    def _apply_trade_streak(self, side: str, notional: float) -> None:
        normalized_side = str(side).lower()
        if normalized_side == self._current_streak_side:
            self._current_streak_count += 1
            self._current_streak_notional += notional
        else:
            self._current_streak_side = normalized_side
            self._current_streak_count = 1
            self._current_streak_notional = notional
        if normalized_side == "buy":
            self._buy_burst_count = max(self._buy_burst_count, self._current_streak_count)
            self._buy_burst_notional = max(self._buy_burst_notional, self._current_streak_notional)
            return
        self._sell_burst_count = max(self._sell_burst_count, self._current_streak_count)
        self._sell_burst_notional = max(self._sell_burst_notional, self._current_streak_notional)

    def _apply_trade_price(self, price: float) -> None:
        if self._trade_count == 1:
            self._open_price = price
            self._high_price = price
            self._low_price = price
            self._close_price = price
            return
        self._high_price = max(self._high_price, price)
        self._low_price = min(self._low_price, price)
        self._close_price = price

    def _reset_flow_aggregates(self) -> None:
        self._signed_trade_notional = 0.0
        self._trade_count = 0
        self._buy_notional = 0.0
        self._sell_notional = 0.0
        self._buy_count = 0
        self._sell_count = 0
        self._max_trade_notional = 0.0
        self._buy_burst_count = 0
        self._sell_burst_count = 0
        self._buy_burst_notional = 0.0
        self._sell_burst_notional = 0.0
        self._current_streak_side = ""
        self._current_streak_count = 0
        self._current_streak_notional = 0.0
        self._open_price = 0.0
        self._high_price = 0.0
        self._low_price = 0.0
        self._close_price = 0.0

    def _resolve_mid_price(self) -> float:
        if self._book is None:
            return 0.0
        return (self._book.bid_price + self._book.ask_price) / 2.0

    def _resolve_microprice(self) -> float:
        if self._book is None:
            return 0.0
        book_depth = self._book.bid_size + self._book.ask_size
        if book_depth <= 0.0:
            return 0.0
        weighted_bid = self._book.bid_price * self._book.ask_size
        weighted_ask = self._book.ask_price * self._book.bid_size
        return (weighted_bid + weighted_ask) / book_depth

    def _resolve_price_path(self, fallback_price: float) -> tuple[float, float, float, float]:
        if self._trade_count > 0:
            return self._open_price, self._high_price, self._low_price, self._close_price
        return fallback_price, fallback_price, fallback_price, fallback_price

    def _resolve_multi_level_features(self) -> tuple[int, float, float]:
        if self._book is None:
            return 0, 0.0, 0.0
        bid_levels = tuple(self._book.bid_levels or ())
        ask_levels = tuple(self._book.ask_levels or ())
        if len(bid_levels) < MULTI_LEVEL_MIN_LEVELS or len(ask_levels) < MULTI_LEVEL_MIN_LEVELS:
            return 0, 0.0, 0.0
        bid_depth = sum(size for _, size in bid_levels)
        ask_depth = sum(size for _, size in ask_levels)
        total_depth = bid_depth + ask_depth
        imbalance = (bid_depth - ask_depth) / total_depth if total_depth > 0.0 else 0.0
        return min(len(bid_levels), len(ask_levels)), imbalance, self._compute_book_slope(bid_levels, ask_levels)

    def _resolve_depth_10bps(self, mid_price: float) -> tuple[float, float]:
        if self._book is None or mid_price <= 0.0:
            return 0.0, 0.0
        max_distance = mid_price * (DEPTH_WINDOW_BPS / BASIS_BPS_MULTIPLIER)
        bid_depth = sum(
            size
            for price, size in tuple(self._book.bid_levels or ())
            if (mid_price - price) <= max_distance
        )
        ask_depth = sum(
            size
            for price, size in tuple(self._book.ask_levels or ())
            if (price - mid_price) <= max_distance
        )
        return bid_depth, ask_depth

    def _compute_book_slope(self, bid_levels, ask_levels) -> float:
        near_depth = bid_levels[0][1] + ask_levels[0][1]
        if near_depth <= 0.0:
            return 0.0
        far_depth = 0.0
        level_count = min(len(bid_levels), len(ask_levels))
        for index in range(1, level_count):
            far_depth += bid_levels[index][1] + ask_levels[index][1]
        average_far_depth = far_depth / max(level_count - 1, 1)
        return (average_far_depth / near_depth) - 1.0

    def flush(self, second_bucket: int) -> FeatureBar1s:
        bid_price = self._book.bid_price if self._book else 0.0
        ask_price = self._book.ask_price if self._book else 0.0
        bid_size = self._book.bid_size if self._book else 0.0
        ask_size = self._book.ask_size if self._book else 0.0
        mid_price = self._resolve_mid_price()
        microprice = self._resolve_microprice()
        spread_bps = ((ask_price - bid_price) / mid_price) * BASIS_BPS_MULTIPLIER if mid_price > 0 else 0.0
        mark_price = self._contract_state.mark_price if self._contract_state else mid_price
        index_price = self._contract_state.index_price if self._contract_state else mid_price
        open_interest = self._contract_state.open_interest if self._contract_state else 0.0
        funding_rate = self._contract_state.funding_rate if self._contract_state else 0.0
        premium = self._contract_state.premium if self._contract_state else 0.0
        basis_zscore = mark_price - index_price
        basis_bps = ((mark_price - index_price) / index_price) * BASIS_BPS_MULTIPLIER if index_price > 0 else 0.0
        data_quality = "ok" if self._book and self._contract_state else "partial"
        open_price, high_price, low_price, close_price = self._resolve_price_path(mid_price)
        book_level_count, multi_level_book_imbalance, book_slope = self._resolve_multi_level_features()
        bid_depth_10bps, ask_depth_10bps = self._resolve_depth_10bps(mid_price)
        bar = FeatureBar1s(
            inst_id=self._inst_id,
            ts_exchange=float(second_bucket),
            ts_local=float(second_bucket),
            second_bucket=int(second_bucket),
            mid_price=mid_price,
            mark_price=mark_price,
            index_price=index_price,
            spread_bps=spread_bps,
            signed_trade_notional=self._signed_trade_notional,
            trade_count=self._trade_count,
            oi_delta=self._oi_delta,
            basis_zscore=basis_zscore,
            data_quality=data_quality,
            bid_price=bid_price,
            ask_price=ask_price,
            bid_size=bid_size,
            ask_size=ask_size,
            bid_depth_10bps=bid_depth_10bps,
            ask_depth_10bps=ask_depth_10bps,
            buy_notional=self._buy_notional,
            sell_notional=self._sell_notional,
            buy_count=self._buy_count,
            sell_count=self._sell_count,
            max_trade_notional=self._max_trade_notional,
            buy_burst_count=self._buy_burst_count,
            sell_burst_count=self._sell_burst_count,
            buy_burst_notional=self._buy_burst_notional,
            sell_burst_notional=self._sell_burst_notional,
            open_price=open_price,
            high_price=high_price,
            low_price=low_price,
            close_price=close_price,
            microprice=microprice,
            basis_bps=basis_bps,
            open_interest=open_interest,
            funding_rate=funding_rate,
            funding_delta=self._funding_delta,
            premium=premium,
            book_level_count=book_level_count,
            multi_level_book_imbalance=multi_level_book_imbalance,
            book_slope=book_slope,
        )
        self._reset_flow_aggregates()
        return bar
