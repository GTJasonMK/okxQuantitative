from __future__ import annotations

from pathlib import Path

import pytest

from app.core.data_storage import DataStorage
from app.core.research_platform import factory
from tests.research_platform_dataset_helpers import close_storage


@pytest.fixture
def storage(tmp_path: Path):
    instance = DataStorage(tmp_path / 'research_factory.db')
    yield instance
    close_storage(instance)


def test_factory_builds_independent_census_universe_provider(storage, monkeypatch):
    storage.save_research_second_state(
        session_id='sess-warehouse',
        inst_id='BTC-USDT-SWAP',
        second_bucket=1713000899,
        ts_exchange=1713000899.0,
        ts_local=1713000899.2,
        bid_price=65000.0,
        ask_price=65000.5,
        bid_size=12.0,
        ask_size=10.0,
        bid_depth_10bps=40.0,
        ask_depth_10bps=20.0,
        mid_price=65000.25,
        microprice=65000.23,
        open_price=64999.0,
        high_price=65001.0,
        low_price=64998.5,
        close_price=65000.2,
        mark_price=65000.1,
        index_price=65000.0,
        trade_count=18,
        signed_trade_notional=230000.0,
        buy_notional=150000.0,
        sell_notional=80000.0,
        buy_count=10,
        sell_count=8,
        max_trade_notional=45000.0,
        buy_burst_count=2,
        sell_burst_count=1,
        buy_burst_notional=56000.0,
        sell_burst_notional=18000.0,
        open_interest=3200000.0,
        oi_delta=1200.0,
        funding_rate=0.0001,
        funding_delta=0.0,
        premium=1.5,
        basis_bps=2.1,
        spread_bps=0.08,
        book_level_count=5,
        multi_level_book_imbalance=0.11,
        book_slope=0.03,
        has_trade_input=1,
        has_book_input=1,
        has_state_input=1,
        book_age_seconds=0.0,
        state_age_seconds=0.0,
        clock_skew_ms=12.0,
        is_valid_second=1,
        quality_grade='A',
        invalid_reason='',
        integrity_policy_version='strict_v1',
    )

    class FakeContext:
        cfg = object()

    monkeypatch.setattr(
        factory,
        'load_census_universe_settings',
        lambda cfg: {'enabled': True, 'universe': []},
    )

    provider = factory._build_census_universe_provider(FakeContext())

    assert provider.list_inst_ids() == []
