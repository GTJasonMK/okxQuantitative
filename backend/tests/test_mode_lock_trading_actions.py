import asyncio

import pytest


@pytest.fixture(autouse=True)
def _avoid_asyncio_default_executor_hang(monkeypatch):
    """
    与其他测试保持一致：避免 pytest/asyncio 在关闭事件循环时卡在 shutdown_default_executor。
    """

    async def _to_thread(func, /, *args, **kwargs):
        return func(*args, **kwargs)

    monkeypatch.setattr(asyncio, "to_thread", _to_thread, raising=True)


@pytest.mark.asyncio
async def test_spot_order_is_blocked_when_requested_mode_differs_from_default(monkeypatch):
    """
    当系统默认模式为 simulated 时，必须禁止任何 live 交易动作（即使 live 密钥已配置）。
    """
    from fastapi import HTTPException
    import app.api.trading as trading_mod

    old = trading_mod.config.okx.use_simulated
    try:
        trading_mod.config.okx.use_simulated = True  # 默认 simulated

        monkeypatch.setattr(trading_mod, "get_trader", lambda mode: (_ for _ in ()).throw(AssertionError("不应触发 trader")), raising=True)

        req = trading_mod.PlaceOrderRequest(
            inst_id="BTC-USDT",
            side="buy",
            order_type="market",
            size="1",
            price="",
            td_mode="cash",
            mode="live",
        )

        with pytest.raises(HTTPException) as exc:
            await trading_mod.place_order(req)
        assert exc.value.status_code == 403
    finally:
        trading_mod.config.okx.use_simulated = old


@pytest.mark.asyncio
async def test_contract_order_is_blocked_when_requested_mode_differs_from_default(monkeypatch):
    from fastapi import HTTPException
    import app.api.trading as trading_mod

    old = trading_mod.config.okx.use_simulated
    try:
        trading_mod.config.okx.use_simulated = False  # 默认 live

        monkeypatch.setattr(trading_mod, "get_trader", lambda mode: (_ for _ in ()).throw(AssertionError("不应触发 trader")), raising=True)

        req = trading_mod.ContractOrderRequest(
            inst_id="BTC-USDT-SWAP",
            side="buy",
            pos_side="long",
            order_type="market",
            size="1",
            price="",
            td_mode="cross",
            reduce_only=False,
            mode="simulated",
        )

        with pytest.raises(HTTPException) as exc:
            await trading_mod.place_contract_order(req)
        assert exc.value.status_code == 403
    finally:
        trading_mod.config.okx.use_simulated = old

