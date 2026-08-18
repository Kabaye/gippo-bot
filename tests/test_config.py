import pytest

from gippo_bot.config import BotSettings, CabinetSettings, SettingsError


def test_cabinet_settings_require_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("GIPPO_LOGIN", raising=False)
    monkeypatch.delenv("GIPPO_PASSWORD", raising=False)

    with pytest.raises(SettingsError, match="GIPPO_LOGIN"):
        CabinetSettings.from_environment()


def test_bot_settings_parse_allow_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_OPEN_ACCESS", "false")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "123, 456")
    monkeypatch.setenv("GIPPO_LOGIN", "login")
    monkeypatch.setenv("GIPPO_PASSWORD", "password")

    settings = BotSettings.from_environment()

    assert settings.open_access is False
    assert settings.allowed_user_ids == frozenset({123, 456})


def test_bot_settings_reject_empty_allow_list(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_OPEN_ACCESS", "false")
    monkeypatch.setenv("TELEGRAM_ALLOWED_USER_IDS", "  ")
    monkeypatch.setenv("GIPPO_LOGIN", "login")
    monkeypatch.setenv("GIPPO_PASSWORD", "password")

    with pytest.raises(SettingsError, match="TELEGRAM_OPEN_ACCESS"):
        BotSettings.from_environment()


def test_bot_settings_allow_explicit_open_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_OPEN_ACCESS", "true")
    monkeypatch.delenv("TELEGRAM_ALLOWED_USER_IDS", raising=False)
    monkeypatch.setenv("GIPPO_LOGIN", "login")
    monkeypatch.setenv("GIPPO_PASSWORD", "password")

    settings = BotSettings.from_environment()

    assert settings.open_access is True
    assert settings.allowed_user_ids == frozenset()


def test_bot_settings_reject_invalid_open_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_OPEN_ACCESS", "sometimes")
    monkeypatch.setenv("GIPPO_LOGIN", "login")
    monkeypatch.setenv("GIPPO_PASSWORD", "password")

    with pytest.raises(SettingsError, match="true or false"):
        BotSettings.from_environment()


def test_bot_settings_accept_card_image_path_overrides(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    gippo_card = tmp_path / "gippo.png"
    belmarket_card = tmp_path / "belmarket.png"
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "token")
    monkeypatch.setenv("TELEGRAM_OPEN_ACCESS", "true")
    monkeypatch.setenv("GIPPO_LOGIN", "login")
    monkeypatch.setenv("GIPPO_PASSWORD", "password")
    monkeypatch.setenv("GIPPO_CARD_IMAGE_PATH", str(gippo_card))
    monkeypatch.setenv("BELMARKET_CARD_IMAGE_PATH", str(belmarket_card))

    settings = BotSettings.from_environment()

    assert settings.gippo_card_image_path == gippo_card
    assert settings.belmarket_card_image_path == belmarket_card
