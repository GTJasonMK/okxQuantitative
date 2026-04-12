from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.core.okx_outbound.governor import OKXOutboundGovernor
from app.core.okx_outbound.models import OKXOutboundEvent
from app.core.okx_outbound.rules import OKXRateRuleRegistry
from app.core.okx_outbound.timeline import OKXOutboundTimelineStore


class FakeClock:
    def __init__(self, now: float):
        self.now = now
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float):
        self.sleeps.append(seconds)
        self.now += seconds


class OKXOutboundGovernorTests(unittest.TestCase):
    def test_timeline_store_only_returns_events_inside_requested_window(self):
        store = OKXOutboundTimelineStore(max_events=8)
        base_ts = datetime(2026, 4, 5, 12, 0, tzinfo=timezone.utc).timestamp()

        store.record(
            OKXOutboundEvent(
                ts=base_ts - 700,
                op_key="market.ticker",
                channel="rest",
                target_group="public",
                rule_key="public_ip",
                scope_key="public_ip",
                inst_id="BTC-USDT",
                mode="",
                result="ok",
                latency_ms=12,
            )
        )
        store.record(
            OKXOutboundEvent(
                ts=base_ts - 30,
                op_key="market.books",
                channel="rest",
                target_group="public",
                rule_key="public_ip",
                scope_key="public_ip",
                inst_id="BTC-USDT",
                mode="",
                result="error",
                latency_ms=55,
            )
        )

        snapshot = store.snapshot(window_seconds=600, now_ts=base_ts, limit=100)

        self.assertEqual(len(snapshot["events"]), 1)
        self.assertEqual(snapshot["events"][0]["op_key"], "market.books")
        self.assertEqual(snapshot["summary"]["event_count"], 1)
        self.assertEqual(snapshot["summary"]["error_count"], 1)

    def test_rule_registry_distinguishes_books_and_books_full(self):
        registry = OKXRateRuleRegistry()
        books = registry.get("market.books")
        books_full = registry.get("market.books_full")

        self.assertEqual(books.rule_key, "public_ip")
        self.assertEqual(books.capacity, 40)
        self.assertEqual(books.window_seconds, 2)
        self.assertEqual(books_full.capacity, 10)
        self.assertEqual(books_full.window_seconds, 2)

    def test_rule_registry_registers_trend_research_contract_state_rules(self):
        registry = OKXRateRuleRegistry()

        mark_price = registry.get("market.mark_price")
        index_ticker = registry.get("market.index_ticker")
        open_interest = registry.get("market.open_interest")
        funding_rate = registry.get("market.funding_rate")

        self.assertEqual((mark_price.rule_key, mark_price.window_seconds, mark_price.capacity), ("public_ip_inst", 2, 10))
        self.assertEqual((index_ticker.rule_key, index_ticker.window_seconds, index_ticker.capacity), ("public_ip", 2, 20))
        self.assertEqual((open_interest.rule_key, open_interest.window_seconds, open_interest.capacity), ("public_ip_inst", 2, 20))
        self.assertEqual((funding_rate.rule_key, funding_rate.window_seconds, funding_rate.capacity), ("public_ip_inst", 2, 10))

    def test_governor_uses_scope_key_independently(self):
        clock = FakeClock(100.0)
        governor = OKXOutboundGovernor(time_fn=clock.time, sleep_fn=clock.sleep)

        governor.acquire("market.ticker", scope_key="public_ip")
        governor.acquire("trade.place_order", scope_key="trade_user_inst:live:BTC-USDT")

        snapshot = governor.debug_snapshot()
        self.assertEqual(snapshot["market.ticker|public_ip"]["count"], 1)
        self.assertEqual(
            snapshot["trade.place_order|trade_user_inst:live:BTC-USDT"]["count"],
            1,
        )

    def test_governor_splits_public_ip_inst_rules_by_instrument(self):
        clock = FakeClock(120.0)
        governor = OKXOutboundGovernor(time_fn=clock.time, sleep_fn=clock.sleep)

        governor.acquire("market.mark_price", scope_key="public_ip", inst_id="BTC-USDT-SWAP")
        governor.acquire("market.mark_price", scope_key="public_ip", inst_id="ETH-USDT-SWAP")

        snapshot = governor.debug_snapshot()
        self.assertEqual(snapshot["market.mark_price|public_ip:BTC-USDT-SWAP"]["count"], 1)
        self.assertEqual(snapshot["market.mark_price|public_ip:ETH-USDT-SWAP"]["count"], 1)

    def test_execute_rest_records_event_for_actual_outbound_call(self):
        clock = FakeClock(200.0)
        store = OKXOutboundTimelineStore(max_events=16)
        governor = OKXOutboundGovernor(
            timeline=store,
            time_fn=clock.time,
            sleep_fn=clock.sleep,
        )

        result = governor.execute_rest(
            op_key="market.ticker",
            scope_key="public_ip",
            inst_id="BTC-USDT",
            mode="",
            operation=lambda: {"code": "0"},
        )

        self.assertEqual(result["code"], "0")
        snapshot = store.snapshot(window_seconds=600, now_ts=clock.time(), limit=10)
        self.assertEqual(snapshot["summary"]["event_count"], 1)
        self.assertEqual(snapshot["events"][0]["op_key"], "market.ticker")


if __name__ == "__main__":
    unittest.main()
