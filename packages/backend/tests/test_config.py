import os
import subprocess
import sys

from app.config import refresh_settings


def test_custom_default_model_env_is_honored(monkeypatch) -> None:
    monkeypatch.setenv("MODEL", "custom-model")

    settings = refresh_settings()

    assert settings.model == "custom-model"


def test_custom_default_model_fallback_env_is_honored(monkeypatch) -> None:
    monkeypatch.delenv("MODEL", raising=False)
    monkeypatch.setenv("DEFAULT_MODEL", "custom-default-model")

    settings = refresh_settings()

    assert settings.model == "custom-default-model"


def test_dmxapi_key_env_is_supported(monkeypatch) -> None:
    monkeypatch.delenv("DEFAULT_KEY", raising=False)
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setenv("DMXAPI_API_KEY", "dmx-secret")

    settings = refresh_settings()

    assert settings.openai_api_key == "dmx-secret"
    assert settings.default_key == "dmx-secret"


def test_ic_package_imports_without_manual_pythonpath() -> None:
    env = dict(os.environ)
    env.pop("PYTHONPATH", None)

    result = subprocess.run(
        [sys.executable, "-c", "import ic, app.config; print(ic.__name__)"],
        cwd=os.getcwd(),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "ic"
