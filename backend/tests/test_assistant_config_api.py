import pytest


@pytest.mark.asyncio
async def test_get_assistant_config_masks_api_key():
    import app.main as main_mod

    old_values = (
        main_mod.config.ai_assistant.enabled,
        main_mod.config.ai_assistant.base_url,
        main_mod.config.ai_assistant.api_key,
        main_mod.config.ai_assistant.model,
        main_mod.config.ai_assistant.provider_name,
    )
    try:
        main_mod.config.ai_assistant.enabled = True
        main_mod.config.ai_assistant.base_url = "https://api.openai.com/v1"
        main_mod.config.ai_assistant.api_key = "sk-test-1234567890"
        main_mod.config.ai_assistant.model = "gpt-4.1-mini"
        main_mod.config.ai_assistant.provider_name = "OpenAI-Compatible"

        result = await main_mod.get_assistant_config()

        assert result["enabled"] is True
        assert result["configured"] is True
        assert result["model"] == "gpt-4.1-mini"
        assert result["provider_name"] == "OpenAI-Compatible"
        assert result["api_key"].startswith("sk-t")
        assert result["api_key"].endswith("7890")
        assert "*" in result["api_key"]
    finally:
        (
            main_mod.config.ai_assistant.enabled,
            main_mod.config.ai_assistant.base_url,
            main_mod.config.ai_assistant.api_key,
            main_mod.config.ai_assistant.model,
            main_mod.config.ai_assistant.provider_name,
        ) = old_values


@pytest.mark.asyncio
async def test_save_assistant_config_allows_masked_key_and_updates_runtime(tmp_path, monkeypatch):
    import app.main as main_mod

    monkeypatch.setattr(main_mod, "CONFIG_DIR", tmp_path, raising=True)

    old_values = (
        main_mod.config.ai_assistant.enabled,
        main_mod.config.ai_assistant.base_url,
        main_mod.config.ai_assistant.api_key,
        main_mod.config.ai_assistant.model,
        main_mod.config.ai_assistant.provider_name,
    )
    try:
        main_mod.config.ai_assistant.enabled = True
        main_mod.config.ai_assistant.base_url = "https://api.openai.com/v1"
        main_mod.config.ai_assistant.api_key = "sk-real-1234567890"
        main_mod.config.ai_assistant.model = "gpt-4.1-mini"
        main_mod.config.ai_assistant.provider_name = "OpenAI-Compatible"

        req = main_mod.AIAssistantConfigRequest(
            enabled=False,
            base_url="https://llm.example.com/v1",
            api_key="sk-r********7890",
            model="gpt-custom",
            provider_name="MyProvider",
        )

        resp = await main_mod.save_assistant_config(req)

        assert resp["success"] is True
        assert main_mod.config.ai_assistant.enabled is False
        assert main_mod.config.ai_assistant.base_url == "https://llm.example.com/v1"
        assert main_mod.config.ai_assistant.api_key == "sk-real-1234567890"
        assert main_mod.config.ai_assistant.model == "gpt-custom"
        assert main_mod.config.ai_assistant.provider_name == "MyProvider"

        env_text = (tmp_path / ".env").read_text(encoding="utf-8")
        assert "AI_ASSISTANT_ENABLED=false" in env_text
        assert "AI_ASSISTANT_BASE_URL=https://llm.example.com/v1" in env_text
        assert "AI_ASSISTANT_API_KEY=sk-real-1234567890" in env_text
        assert "AI_ASSISTANT_MODEL=gpt-custom" in env_text
        assert "AI_ASSISTANT_PROVIDER=MyProvider" in env_text
    finally:
        (
            main_mod.config.ai_assistant.enabled,
            main_mod.config.ai_assistant.base_url,
            main_mod.config.ai_assistant.api_key,
            main_mod.config.ai_assistant.model,
            main_mod.config.ai_assistant.provider_name,
        ) = old_values
