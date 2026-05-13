from types import SimpleNamespace

from app.engine.config_bridge import backend_settings_to_agent_config


def _make_settings(**overrides):
    base = {
        "openai_api_key": "test-deepseek-key",
        "default_key": None,
        "default_base_url": "https://api.deepseek.com",
        "openai_base_url": "https://api.deepseek.com",
        "model": "deepseek-v4-pro",
        "max_tokens": 1_000_000,
        "temperature": 0.1,
        "openai_timeout_seconds": 30.0,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def test_backend_config_bridge_initializes_model_pointers() -> None:
    settings = _make_settings()

    cfg = backend_settings_to_agent_config(settings)

    assert cfg.model_pointers.main == cfg.default_model
    assert cfg.model_pointers.sub == cfg.default_model
    assert cfg.model_pointers.compact == cfg.default_model


def test_backend_config_bridge_keeps_model_pointers_without_models() -> None:
    settings = _make_settings(openai_api_key=None, default_key=None)

    cfg = backend_settings_to_agent_config(settings)

    assert hasattr(cfg, "model_pointers")
    assert cfg.model_pointers.resolve("compact", "fallback-model") == "fallback-model"
