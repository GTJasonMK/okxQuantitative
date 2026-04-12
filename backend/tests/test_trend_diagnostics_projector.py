from app.core.trend_research.diagnostics_projector import TrendDiagnosticsProjector


def test_projector_tracks_health_and_timeline_for_selected_instrument():
    projector = TrendDiagnosticsProjector(timeline_window=5)

    projector.reset_instruments(["BTC-USDT-SWAP", "ETH-USDT-SWAP"])
    projector.record_trade_input("BTC-USDT-SWAP", emitted_at=1712365200.0)
    projector.record_book_input("BTC-USDT-SWAP", emitted_at=1712365201.0)
    projector.record_state_sync("BTC-USDT-SWAP", emitted_at=1712365202.0)
    feature_event = projector.record_feature_emitted(
        "BTC-USDT-SWAP",
        bucket=1712365202,
        emitted_at=1712365202.4,
    )
    inference_event = projector.record_inference_emitted(
        "BTC-USDT-SWAP",
        bucket=1712365202,
        emitted_at=1712365202.8,
    )

    snapshot = projector.build_snapshot(
        inst_id="BTC-USDT-SWAP",
        timeline_limit=5,
        now_ts=1712365203.0,
    )

    assert snapshot["selected_inst_id"] == "BTC-USDT-SWAP"
    assert snapshot["global_health"]["whitelist_count"] == 2
    assert snapshot["instrument_health"]["pipeline_stage"] == "inference_ready"
    assert snapshot["instrument_health"]["trade_age_seconds"] == 3.0
    assert snapshot["details"]["last_feature_bucket"] == 1712365202
    assert feature_event["event_type"] == "feature_emitted"
    assert inference_event["event_type"] == "inference_emitted"
    assert snapshot["timeline"][-1]["kind"] == "inference"


def test_projector_emits_recovery_when_runtime_error_clears():
    projector = TrendDiagnosticsProjector(timeline_window=5)

    projector.reset_instruments(["BTC-USDT-SWAP"])
    error_event = projector.record_runtime_error(
        "BTC-USDT-SWAP",
        message="trade stream stalled",
        emitted_at=1712365200.0,
    )
    recovery_event = projector.record_runtime_error(
        "BTC-USDT-SWAP",
        message="",
        emitted_at=1712365205.0,
    )

    snapshot = projector.build_snapshot(
        inst_id="BTC-USDT-SWAP",
        timeline_limit=5,
        now_ts=1712365205.0,
    )

    assert error_event["event_type"] == "runtime_error_changed"
    assert error_event["payload"]["current_error"] == "trade stream stalled"
    assert recovery_event["payload"]["current_error"] == ""
    assert snapshot["timeline"][-1]["kind"] == "recovery"
    assert snapshot["instrument_health"]["is_error"] is False


def test_projector_incremental_events_include_live_health_payload():
    projector = TrendDiagnosticsProjector(timeline_window=5)

    projector.reset_instruments(["BTC-USDT-SWAP", "ETH-USDT-SWAP"])
    trade_event = projector.record_trade_input(
        "BTC-USDT-SWAP",
        emitted_at=1712365200.0,
    )

    assert trade_event["payload"]["instrument_health"]["inst_id"] == "BTC-USDT-SWAP"
    assert trade_event["payload"]["instrument_health"]["trade_age_seconds"] == 0.0
    assert "subscription_state" in trade_event["payload"]["details"]
    assert trade_event["payload"]["global_health"]["whitelist_count"] == 2
    assert trade_event["payload"]["global_health"]["active_count"] == 1
    assert trade_event["payload"]["global_health"]["stale_count"] == 1
