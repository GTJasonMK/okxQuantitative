import pytest


def test_parse_okx_realtime_candle_payload():
    """原生 candle 推送应被解析为统一的 K 线结构。"""
    from app.core.websocket_manager import _build_candle_channel, _parse_candle

    candle = _parse_candle(
        [
            "1710000000000",
            "63000.1",
            "63120.5",
            "62980.2",
            "63088.8",
            "12.34",
            "778000.1",
            "778500.2",
            "0",
        ],
        channel=_build_candle_channel("1m"),
        inst_id="BTC-USDT",
        inst_type="SPOT",
    )

    assert candle is not None
    assert candle.inst_id == "BTC-USDT"
    assert candle.inst_type == "SPOT"
    assert candle.timeframe == "1m"
    assert candle.timestamp == 1710000000000
    assert candle.open == 63000.1
    assert candle.close == 63088.8
    assert candle.volume == 12.34
    assert candle.confirm == 0
    assert candle.to_dict()["timeframe"] == "1m"


@pytest.mark.asyncio
async def test_okx_manager_subscribe_and_unsubscribe_business_candles():
    """business WS 应按 instId + timeframe 订阅和退订原生 candle。"""
    from app.core.websocket_manager import OKXWebSocketManager

    class DummyBusinessWS:
        def __init__(self):
            self.subscribe_calls = []
            self.unsubscribe_calls = []

        async def subscribe(self, params, callback):
            self.subscribe_calls.append(params)

        async def unsubscribe(self, params, callback):
            self.unsubscribe_calls.append(params)

    manager = OKXWebSocketManager(is_simulated=True)
    manager._business_running = True
    manager._business_ws = DummyBusinessWS()

    await manager.subscribe_candles([("BTC-USDT", "1m"), ("ETH-USDT", "1H")])

    assert manager._business_ws.subscribe_calls == [[
        {"channel": "candle1m", "instId": "BTC-USDT"},
        {"channel": "candle1H", "instId": "ETH-USDT"},
    ]]
    assert manager._subscribed_candle_keys == {"BTC-USDT|1m", "ETH-USDT|1H"}

    await manager.unsubscribe_candles([("BTC-USDT", "1m")])

    assert manager._business_ws.unsubscribe_calls == [[
        {"channel": "candle1m", "instId": "BTC-USDT"},
    ]]
    assert manager._subscribed_candle_keys == {"ETH-USDT|1H"}
