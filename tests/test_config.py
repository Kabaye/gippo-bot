import pytest

from gippo_bot.config import BotSettings, CabinetSettings, SettingsError


def test_cabinet_settings_require_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIPPO_LOGIN", raising=False)
    monkeypatch.delenv("GIPPO_PASSWORD", raising=False)

    with pytest.raises(SettingsError, match="GIPPO_LOGIN"):
        CabinetSettings.from_environment()


def test_bot_settings_parse_allow_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "123, 456")
    monkeypatch.setenv("GIPPO_LOGIN", "login")
    monkeypatch.setenv("GIPPO_PASSWORD", "password")

    settings = BotSettings.from_environment()

    assert settings.allowed_user_ids == frozenset({123, 456})


def test_bot_settings_reject_empty_allow_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "  ")
    monkeypatch.setenv("GIPPO_LOGIN", "login")
    monkeypatch.setenv("GIPPO_PASSWORD", "password")

    with pytest.raises(SettingsError, match="TELEGRAM_ALLOWED_USER_IDS"):
        BotSettings.from_environment()
