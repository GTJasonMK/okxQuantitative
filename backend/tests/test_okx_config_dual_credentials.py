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
async def test_save_okx_config_allows_masked_demo_while_setting_live(tmp_path, monkeypatch):
    """
    回归测试：前端可能把已配置密钥以遮蔽形式回填（包含 *）。
    此时用户再填写另一套密钥（例如实盘）并保存，后端不应拒绝或覆盖已配置的一套。
    """
    import app.main as main_mod

    # 避免写入真实 config/.env
    monkeypatch.setattr(main_mod, "CONFIG_DIR", tmp_path, raising=True)

    # 避免触发真实 WS 重连/交易模块 reinit 的副作用（测试只关心保存逻辑）
    import app.core.app_context as ctx_mod

    class DummyTradingManager:
        def reinit(self):
            return None

    class DummyCtx:
        def trading_manager(self):
            return DummyTradingManager()

        async def restart_ws(self):
            return None

    monkeypatch.setattr(ctx_mod, "get_app_context", lambda: DummyCtx(), raising=True)

    # 预置：demo 已配置，live 未配置
    old_demo = (
        main_mod.config.okx.demo.api_key,
        main_mod.config.okx.demo.secret_key,
        main_mod.config.okx.demo.passphrase,
    )
    old_live = (
        main_mod.config.okx.live.api_key,
        main_mod.config.okx.live.secret_key,
        main_mod.config.okx.live.passphrase,
    )
    old_use_simulated = main_mod.config.okx.use_simulated
    try:
        main_mod.config.okx.demo.api_key = "demo_key_1234567890"
        main_mod.config.okx.demo.secret_key = "demo_secret_1234567890"
        main_mod.config.okx.demo.passphrase = "demo_pass_1234567890"

        main_mod.config.okx.live.api_key = ""
        main_mod.config.okx.live.secret_key = ""
        main_mod.config.okx.live.passphrase = ""
        main_mod.config.okx.use_simulated = True

        # 请求：demo 传遮蔽值（模拟 UI 回填），live 传真实新值
        req = main_mod.OKXConfigRequest(
            demo=main_mod.OKXCredentialsRequest(
                api_key="demo********7890",
                secret_key="demo********7890",
                passphrase="demo********7890",
            ),
            live=main_mod.OKXCredentialsRequest(
                api_key="live_key_abcdef",
                secret_key="live_secret_abcdef",
                passphrase="live_pass_abcdef",
            ),
            use_simulated=False,  # 同时切换到实盘
        )

        resp = await main_mod.save_okx_config(req)
        assert resp["success"] is True

        # demo 保持不变
        assert main_mod.config.okx.demo.api_key == "demo_key_1234567890"
        assert main_mod.config.okx.demo.secret_key == "demo_secret_1234567890"
        assert main_mod.config.okx.demo.passphrase == "demo_pass_1234567890"

        # live 被写入
        assert main_mod.config.okx.live.api_key == "live_key_abcdef"
        assert main_mod.config.okx.live.secret_key == "live_secret_abcdef"
        assert main_mod.config.okx.live.passphrase == "live_pass_abcdef"

        # 文件应包含两套配置（demo 为既有值，live 为新值）
        env_text = (tmp_path / ".env").read_text(encoding="utf-8")
        assert "OKX_DEMO_API_KEY=demo_key_1234567890" in env_text
        assert "OKX_LIVE_API_KEY=live_key_abcdef" in env_text
        assert "OKX_USE_SIMULATED=false" in env_text
    finally:
        main_mod.config.okx.demo.api_key, main_mod.config.okx.demo.secret_key, main_mod.config.okx.demo.passphrase = old_demo
        main_mod.config.okx.live.api_key, main_mod.config.okx.live.secret_key, main_mod.config.okx.live.passphrase = old_live
        main_mod.config.okx.use_simulated = old_use_simulated

