from app.config import AppConfig


def test_app_config_ignores_removed_legacy_okx_env_names(monkeypatch):
    monkeypatch.setenv('OKX_API_KEY', 'legacy_key')
    monkeypatch.setenv('OKX_SECRET_KEY', 'legacy_secret')
    monkeypatch.setenv('OKX_PASSPHRASE', 'legacy_pass')
    monkeypatch.setenv('OKX_SIMULATED', 'false')
    monkeypatch.delenv('OKX_DEMO_API_KEY', raising=False)
    monkeypatch.delenv('OKX_DEMO_SECRET_KEY', raising=False)
    monkeypatch.delenv('OKX_DEMO_PASSPHRASE', raising=False)
    monkeypatch.delenv('OKX_LIVE_API_KEY', raising=False)
    monkeypatch.delenv('OKX_LIVE_SECRET_KEY', raising=False)
    monkeypatch.delenv('OKX_LIVE_PASSPHRASE', raising=False)
    monkeypatch.delenv('OKX_USE_SIMULATED', raising=False)

    config = AppConfig.from_env()

    assert config.okx.demo.api_key == ''
    assert config.okx.demo.secret_key == ''
    assert config.okx.demo.passphrase == ''
    assert config.okx.live.api_key == ''
    assert config.okx.live.secret_key == ''
    assert config.okx.live.passphrase == ''
    assert config.okx.use_simulated is True
