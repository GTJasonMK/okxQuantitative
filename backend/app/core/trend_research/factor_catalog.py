from __future__ import annotations

from collections.abc import Sequence

from .factor_definition import FactorDefinition
from .factors_microstructure import (
    compute_microprice_premium_bps_series,
    compute_ofi_top_book_series,
    compute_queue_imbalance_series,
    compute_spread_level_bps_series,
)
from .factors_liquidity import (
    compute_amihud_illiquidity_series,
    compute_depth_to_vol_ratio_series,
    compute_impact_per_notional_series,
)
from .factors_perpetual import (
    compute_basis_momentum_series,
    compute_funding_basis_divergence_series,
    compute_premium_shock_series,
    compute_price_oi_quadrant_series,
)
from .factors_price_structure import (
    MOMENTUM_PERIOD_30S,
    MOMENTUM_PERIOD_60S,
    MOMENTUM_PERIOD_300S,
    compute_breakout_pressure_series,
    compute_distance_to_window_extrema_series,
    compute_momentum_series,
    compute_realized_range_factor_series,
    compute_realized_volatility_factor_series,
    compute_trend_efficiency_series,
)
from .factors_trade_flow import (
    compute_buy_burst_strength_series,
    compute_large_trade_share_series,
    compute_sell_burst_strength_series,
    compute_signed_volume_imbalance_series,
    compute_trade_intensity_series,
)


def get_factor_definitions() -> tuple[FactorDefinition, ...]:
    return (
        *_baseline_factor_definitions(),
        *_microstructure_factor_definitions(),
        *_trade_flow_factor_definitions(),
        *_price_structure_factor_definitions(),
        *_perpetual_factor_definitions(),
        *_liquidity_factor_definitions(),
    )


def _baseline_factor_definitions() -> tuple[FactorDefinition, ...]:
    return (
        _field_factor("signed_trade_notional_z", "trade_flow", "signed_trade_notional"),
        _field_factor("spread_bps_z", "microstructure", "spread_bps"),
        _field_factor("oi_delta_z", "perpetual", "oi_delta"),
        _field_factor("basis_zscore_z", "perpetual", "basis_zscore"),
        _field_factor("trade_count_z", "trade_flow", "trade_count"),
    )


def _microstructure_factor_definitions() -> tuple[FactorDefinition, ...]:
    return (
        FactorDefinition(
            name="queue_imbalance",
            category="microstructure",
            tier=0,
            required_fields=("bid_size", "ask_size"),
            compute_series=compute_queue_imbalance_series,
        ),
        FactorDefinition(
            name="microprice_premium_bps",
            category="microstructure",
            tier=0,
            required_fields=("microprice", "mid_price"),
            compute_series=compute_microprice_premium_bps_series,
        ),
        FactorDefinition(
            name="spread_level_bps",
            category="microstructure",
            tier=0,
            required_fields=("bid_price", "ask_price", "mid_price"),
            compute_series=compute_spread_level_bps_series,
        ),
        FactorDefinition(
            name="ofi_top_book",
            category="microstructure",
            tier=0,
            required_fields=("bid_price", "ask_price", "bid_size", "ask_size"),
            compute_series=compute_ofi_top_book_series,
        ),
        FactorDefinition(
            name="multi_level_book_imbalance",
            category="microstructure",
            tier=1,
            required_fields=("book_level_count", "multi_level_book_imbalance"),
            compute_series=lambda bars: [float(bar.multi_level_book_imbalance) for bar in bars],
            availability=_has_multi_level_books,
            unavailable_reason="依赖多档盘口",
        ),
        FactorDefinition(
            name="book_slope",
            category="microstructure",
            tier=1,
            required_fields=("book_level_count", "book_slope"),
            compute_series=lambda bars: [float(bar.book_slope) for bar in bars],
            availability=_has_multi_level_books,
            unavailable_reason="依赖多档盘口",
        ),
    )


def _trade_flow_factor_definitions() -> tuple[FactorDefinition, ...]:
    return (
        FactorDefinition(
            name="signed_volume_imbalance",
            category="trade_flow",
            tier=0,
            required_fields=("buy_notional", "sell_notional"),
            compute_series=compute_signed_volume_imbalance_series,
        ),
        FactorDefinition(
            name="trade_intensity",
            category="trade_flow",
            tier=0,
            required_fields=("buy_notional", "sell_notional", "buy_count", "sell_count"),
            compute_series=compute_trade_intensity_series,
        ),
        FactorDefinition(
            name="large_trade_share",
            category="trade_flow",
            tier=0,
            required_fields=("buy_notional", "sell_notional", "max_trade_notional"),
            compute_series=compute_large_trade_share_series,
        ),
        FactorDefinition(
            name="buy_burst_strength",
            category="trade_flow",
            tier=0,
            required_fields=(
                "buy_notional",
                "sell_notional",
                "buy_count",
                "sell_count",
                "buy_burst_notional",
                "buy_burst_count",
            ),
            compute_series=compute_buy_burst_strength_series,
        ),
        FactorDefinition(
            name="sell_burst_strength",
            category="trade_flow",
            tier=0,
            required_fields=(
                "buy_notional",
                "sell_notional",
                "buy_count",
                "sell_count",
                "sell_burst_notional",
                "sell_burst_count",
            ),
            compute_series=compute_sell_burst_strength_series,
        ),
    )


def _price_structure_factor_definitions() -> tuple[FactorDefinition, ...]:
    return (
        FactorDefinition(
            name="momentum_30s",
            category="price_structure",
            tier=0,
            required_fields=("close_price", "mid_price"),
            compute_series=lambda bars: compute_momentum_series(bars, window=MOMENTUM_PERIOD_30S),
        ),
        FactorDefinition(
            name="momentum_60s",
            category="price_structure",
            tier=0,
            required_fields=("close_price", "mid_price"),
            compute_series=lambda bars: compute_momentum_series(bars, window=MOMENTUM_PERIOD_60S),
        ),
        FactorDefinition(
            name="momentum_300s",
            category="price_structure",
            tier=0,
            required_fields=("close_price", "mid_price"),
            compute_series=lambda bars: compute_momentum_series(bars, window=MOMENTUM_PERIOD_300S),
        ),
        FactorDefinition(
            name="distance_to_window_extrema",
            category="price_structure",
            tier=0,
            required_fields=("close_price", "mid_price"),
            compute_series=compute_distance_to_window_extrema_series,
        ),
        FactorDefinition(
            name="breakout_pressure",
            category="price_structure",
            tier=0,
            required_fields=("close_price", "mid_price", "bid_size", "ask_size", "buy_notional", "sell_notional"),
            compute_series=compute_breakout_pressure_series,
        ),
        FactorDefinition(
            name="realized_volatility",
            category="price_structure",
            tier=0,
            required_fields=("close_price", "mid_price"),
            compute_series=compute_realized_volatility_factor_series,
        ),
        FactorDefinition(
            name="realized_range",
            category="price_structure",
            tier=0,
            required_fields=("close_price", "mid_price", "high_price", "low_price"),
            compute_series=compute_realized_range_factor_series,
        ),
        FactorDefinition(
            name="trend_efficiency",
            category="price_structure",
            tier=0,
            required_fields=("close_price", "mid_price"),
            compute_series=compute_trend_efficiency_series,
        ),
    )


def _perpetual_factor_definitions() -> tuple[FactorDefinition, ...]:
    return (
        _field_factor("basis_bps", "perpetual", "basis_bps"),
        FactorDefinition(
            name="basis_momentum",
            category="perpetual",
            tier=0,
            required_fields=("basis_bps",),
            compute_series=compute_basis_momentum_series,
        ),
        _field_factor("funding_rate_level", "perpetual", "funding_rate"),
        _field_factor("funding_rate_delta", "perpetual", "funding_delta"),
        _field_factor("open_interest_level", "perpetual", "open_interest"),
        _field_factor("open_interest_delta", "perpetual", "oi_delta"),
        FactorDefinition(
            name="price_oi_quadrant",
            category="perpetual",
            tier=0,
            required_fields=("close_price", "mid_price", "oi_delta"),
            compute_series=compute_price_oi_quadrant_series,
        ),
        FactorDefinition(
            name="funding_basis_divergence",
            category="perpetual",
            tier=0,
            required_fields=("basis_bps", "funding_rate"),
            compute_series=compute_funding_basis_divergence_series,
        ),
        FactorDefinition(
            name="premium_shock",
            category="perpetual",
            tier=0,
            required_fields=("basis_bps", "funding_delta", "premium"),
            compute_series=compute_premium_shock_series,
        ),
    )


def _liquidity_factor_definitions() -> tuple[FactorDefinition, ...]:
    return (
        FactorDefinition(
            name="amihud_illiquidity",
            category="liquidity",
            tier=0,
            required_fields=("close_price", "mid_price", "buy_notional", "sell_notional"),
            compute_series=compute_amihud_illiquidity_series,
        ),
        FactorDefinition(
            name="impact_per_notional",
            category="liquidity",
            tier=0,
            required_fields=("close_price", "mid_price", "signed_trade_notional"),
            compute_series=compute_impact_per_notional_series,
        ),
        FactorDefinition(
            name="depth_to_vol_ratio",
            category="liquidity",
            tier=0,
            required_fields=("bid_price", "ask_price", "bid_size", "ask_size", "close_price", "mid_price"),
            compute_series=compute_depth_to_vol_ratio_series,
        ),
    )


def _field_factor(name: str, category: str, field_name: str) -> FactorDefinition:
    return FactorDefinition(
        name=name,
        category=category,
        tier=0,
        required_fields=(field_name,),
        compute_series=lambda bars, attr=field_name: [float(getattr(bar, attr, 0.0) or 0.0) for bar in bars],
    )
def _has_multi_level_books(bars: Sequence) -> bool:
    return any(int(getattr(bar, "book_level_count", 0) or 0) >= 2 for bar in bars)
