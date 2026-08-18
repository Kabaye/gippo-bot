import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from telegram.error import BadRequest

from gippo_bot.bot import (
    BELMARKET_CARD_CALLBACK,
    GIPPO_CARD_CALLBACK,
    LEGACY_REFRESH_CALLBACK,
    LEGACY_REFRESH_MESSAGE,
    REFRESH_CALLBACK,
    _is_authorized,
    _menu_keyboard,
    _validate_card_images,
    refresh_status,
    retire_legacy_refresh,
    show_belmarket_card,
    show_gippo_card,
)
from gippo_bot.cabinet import DEFAULT_BASE_URL
from gippo_bot.config import BotSettings, CabinetSettings, SettingsError


def _settings(
    *,
    open_access: bool,
    allowed_user_ids: frozenset[int],
    gippo_card_image_path: Path = Path("gippo.png"),
    belmarket_card_image_path: Path = Path("belmarket.png"),
) -> BotSettings:
    return BotSettings(
        token="token",
        open_access=open_access,
        allowed_user_ids=allowed_user_ids,
        cabinet=CabinetSettings(
            login="login",
            password="password",
            base_url=DEFAULT_BASE_URL,
        ),
        gippo_card_image_path=gippo_card_image_path,
        belmarket_card_image_path=belmarket_card_image_path,
    )


def test_open_access_accepts_any_user() -> None:
    update = SimpleNamespace(effective_user=SimpleNamespace(id=999))

    assert _is_authorized(update, _settings(open_access=True, allowed_user_ids=frozenset()))


def test_restricted_access_uses_allow_list() -> None:
    allowed = _settings(open_access=False, allowed_user_ids=frozenset({123}))

    assert _is_authorized(SimpleNamespace(effective_user=SimpleNamespace(id=123)), allowed)
    assert not _is_authorized(SimpleNamespace(effective_user=SimpleNamespace(id=999)), allowed)


def test_menu_uses_new_refresh_api_and_both_card_callbacks() -> None:
    keyboard = _menu_keyboard().inline_keyboard

    assert REFRESH_CALLBACK != LEGACY_REFRESH_CALLBACK
    assert [button.callback_data for row in keyboard for button in row] == [
        REFRESH_CALLBACK,
        GIPPO_CARD_CALLBACK,
        BELMARKET_CARD_CALLBACK,
    ]


def test_card_images_are_required_before_application_start(tmp_path: Path) -> None:
    gippo_card = tmp_path / "gippo.png"
    belmarket_card = tmp_path / "belmarket.png"
    settings = _settings(
        open_access=True,
        allowed_user_ids=frozenset(),
        gippo_card_image_path=gippo_card,
        belmarket_card_image_path=belmarket_card,
    )

    with pytest.raises(SettingsError, match="GIPPO_CARD_IMAGE_PATH"):
        _validate_card_images(settings)

    png_signature = b"\x89PNG\r\n\x1a\n"
    gippo_card.write_bytes(png_signature + b"gippo")
    belmarket_card.write_bytes(png_signature + b"belmarket")

    _validate_card_images(settings)


def test_legacy_refresh_replaces_old_message_with_start_instruction() -> None:
    settings = _settings(open_access=True, allowed_user_ids=frozenset())
    query = SimpleNamespace(answer=AsyncMock(), edit_message_text=AsyncMock())
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=999),
        callback_query=query,
    )
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"settings": settings}))

    asyncio.run(retire_legacy_refresh(update, context))

    query.answer.assert_awaited_once_with(
        "Вызовите /start, чтобы открыть новое меню.", show_alert=True
    )
    query.edit_message_text.assert_awaited_once_with(LEGACY_REFRESH_MESSAGE)


def test_new_refresh_accepts_unchanged_status_without_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    settings = _settings(open_access=True, allowed_user_ids=frozenset())
    query = SimpleNamespace(
        answer=AsyncMock(),
        edit_message_text=AsyncMock(side_effect=BadRequest("Message is not modified")),
    )
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=999),
        callback_query=query,
    )
    context = SimpleNamespace(
        application=SimpleNamespace(bot_data={"settings": settings, "gippo_client": object()})
    )
    monkeypatch.setattr("gippo_bot.bot._load_message", AsyncMock(return_value="same status"))

    asyncio.run(refresh_status(update, context))

    query.answer.assert_awaited_once_with("Обновляю…")
    query.edit_message_text.assert_awaited_once()


@pytest.mark.parametrize(
    ("handler", "selected_card", "expected_caption", "uses_callback"),
    (
        (show_gippo_card, "gippo", "Карта ГИППО «АсобаЯ»", True),
        (show_belmarket_card, "belmarket", "Карта Белмаркет «Хамелеон»", False),
    ),
)
def test_card_handlers_send_configured_original_image(
    tmp_path: Path,
    handler: object,
    selected_card: str,
    expected_caption: str,
    uses_callback: bool,
) -> None:
    gippo_card = tmp_path / "gippo.png"
    belmarket_card = tmp_path / "belmarket.png"
    gippo_card.write_bytes(b"original-gippo-image")
    belmarket_card.write_bytes(b"original-belmarket-image")
    settings = _settings(
        open_access=True,
        allowed_user_ids=frozenset(),
        gippo_card_image_path=gippo_card,
        belmarket_card_image_path=belmarket_card,
    )
    captured: dict[str, object] = {}

    async def capture_photo(*, photo: object, caption: str) -> None:
        captured["image"] = photo.read()
        captured["caption"] = caption

    message = SimpleNamespace(reply_photo=AsyncMock(side_effect=capture_photo))
    query = SimpleNamespace(answer=AsyncMock()) if uses_callback else None
    update = SimpleNamespace(
        effective_user=SimpleNamespace(id=999),
        effective_message=message,
        callback_query=query,
    )
    context = SimpleNamespace(application=SimpleNamespace(bot_data={"settings": settings}))

    asyncio.run(handler(update, context))

    assert captured == {
        "image": f"original-{selected_card}-image".encode(),
        "caption": expected_caption,
    }
    if query is not None:
        query.answer.assert_awaited_once_with("Отправляю карту…")
