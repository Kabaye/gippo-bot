"""Telegram application entry point."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.error import BadRequest, TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
)

from .cabinet import GippoClient, GippoError
from .config import BotSettings, SettingsError
from .formatting import format_status

LOGGER = logging.getLogger(__name__)
LEGACY_REFRESH_CALLBACK = "refresh_status"
REFRESH_CALLBACK = "refresh_status:v2"
GIPPO_CARD_CALLBACK = "show_card:gippo:v2"
BELMARKET_CARD_CALLBACK = "show_card:belmarket:v2"
LEGACY_REFRESH_MESSAGE = (
    "Это меню устарело. Пожалуйста, снова вызовите /start, "
    "чтобы открыть новое меню с картами ГИППО и Белмаркет."
)


def _menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("Обновить", callback_data=REFRESH_CALLBACK)],
            [
                InlineKeyboardButton("Карта ГИППО", callback_data=GIPPO_CARD_CALLBACK),
                InlineKeyboardButton("Карта Белмаркет", callback_data=BELMARKET_CARD_CALLBACK),
            ],
        ]
    )


def _is_authorized(update: Update, settings: BotSettings) -> bool:
    user = update.effective_user
    return user is not None and (settings.open_access or user.id in settings.allowed_user_ids)


async def _close_cabinet(application: Application) -> None:
    """Close the shared cabinet session after Telegram shuts down."""

    client: GippoClient | None = application.bot_data.get("gippo_client")
    if client is not None:
        client.close()


async def _deny(update: Update) -> None:
    if update.callback_query is not None:
        await update.callback_query.answer("Нет доступа", show_alert=True)
    elif update.effective_message is not None:
        await update.effective_message.reply_text("Нет доступа.")


async def _load_message(client: GippoClient) -> str:
    try:
        status = await asyncio.to_thread(client.fetch_status)
    except GippoError:
        LOGGER.exception("Could not load the GIPPO cabinet status")
        return "Не удалось получить данные GIPPO. Попробуйте ещё раз позже."
    except Exception:
        LOGGER.exception("Unexpected error while loading the GIPPO cabinet status")
        return "Временная ошибка. Попробуйте ещё раз позже."
    return format_status(status)


def _validate_card_images(settings: BotSettings) -> None:
    invalid: list[str] = []
    for name, path in (
        ("GIPPO_CARD_IMAGE_PATH", settings.gippo_card_image_path),
        ("BELMARKET_CARD_IMAGE_PATH", settings.belmarket_card_image_path),
    ):
        try:
            with path.open("rb") as image:
                is_png = image.read(8) == b"\x89PNG\r\n\x1a\n"
        except OSError:
            is_png = False
        if not is_png:
            invalid.append(name)
    if invalid:
        raise SettingsError(f"Card image must be a readable PNG file: {', '.join(invalid)}")


async def _send_card(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    *,
    image_path: Path,
    caption: str,
) -> None:
    settings: BotSettings = context.application.bot_data["settings"]
    if not _is_authorized(update, settings):
        await _deny(update)
        return

    query = update.callback_query
    if query is not None:
        try:
            await query.answer("Отправляю карту…")
        except TelegramError:
            LOGGER.warning("Could not acknowledge a loyalty-card callback", exc_info=True)

    message = update.effective_message
    if message is None:
        return

    try:
        with image_path.open("rb") as image:
            await message.reply_photo(photo=image, caption=caption)
    except (OSError, TelegramError):
        LOGGER.exception("Could not send loyalty card image")
        await message.reply_text("Не удалось отправить карту. Попробуйте ещё раз позже.")


async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle `/start` and `/status` for users permitted by the access mode."""

    settings: BotSettings = context.application.bot_data["settings"]
    if not _is_authorized(update, settings):
        await _deny(update)
        return

    client: GippoClient = context.application.bot_data["gippo_client"]
    message = await _load_message(client)
    if update.effective_message is not None:
        await update.effective_message.reply_text(message, reply_markup=_menu_keyboard())


async def show_gippo_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the configured GIPPO loyalty-card image."""

    settings: BotSettings = context.application.bot_data["settings"]
    await _send_card(
        update,
        context,
        image_path=settings.gippo_card_image_path,
        caption="Карта ГИППО «АсобаЯ»",
    )


async def show_belmarket_card(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send the configured Belmarket loyalty-card image."""

    settings: BotSettings = context.application.bot_data["settings"]
    await _send_card(
        update,
        context,
        image_path=settings.belmarket_card_image_path,
        caption="Карта Белмаркет «Хамелеон»",
    )


async def refresh_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Refresh an existing status message after its inline button is pressed."""

    settings: BotSettings = context.application.bot_data["settings"]
    if not _is_authorized(update, settings):
        await _deny(update)
        return

    query = update.callback_query
    if query is None:
        return
    await query.answer("Обновляю…")
    client: GippoClient = context.application.bot_data["gippo_client"]
    message = await _load_message(client)
    try:
        await query.edit_message_text(message, reply_markup=_menu_keyboard())
    except BadRequest as exc:
        if "message is not modified" not in str(exc).lower():
            raise


async def retire_legacy_refresh(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Retire refresh buttons from messages created before the card menu existed."""

    settings: BotSettings = context.application.bot_data["settings"]
    if not _is_authorized(update, settings):
        await _deny(update)
        return

    query = update.callback_query
    if query is None:
        return
    try:
        await query.answer("Вызовите /start, чтобы открыть новое меню.", show_alert=True)
    except TelegramError:
        LOGGER.warning("Could not acknowledge a legacy refresh callback", exc_info=True)
    try:
        await query.edit_message_text(LEGACY_REFRESH_MESSAGE)
    except TelegramError:
        LOGGER.warning("Could not replace a legacy refresh message", exc_info=True)


def build_application(settings: BotSettings) -> Application:
    """Build a configured Telegram application without starting polling."""

    _validate_card_images(settings)
    cabinet = settings.cabinet
    client = GippoClient(
        cabinet.login,
        cabinet.password,
        base_url=cabinet.base_url,
        timeout_seconds=cabinet.timeout_seconds,
    )
    application = ApplicationBuilder().token(settings.token).post_shutdown(_close_cabinet).build()
    application.bot_data["settings"] = settings
    application.bot_data["gippo_client"] = client
    application.add_handler(CommandHandler(["start", "status"], show_status))
    application.add_handler(CommandHandler("gippo", show_gippo_card))
    application.add_handler(CommandHandler("belmarket", show_belmarket_card))
    application.add_handler(CallbackQueryHandler(refresh_status, pattern=f"^{REFRESH_CALLBACK}$"))
    application.add_handler(
        CallbackQueryHandler(show_gippo_card, pattern=f"^{GIPPO_CARD_CALLBACK}$")
    )
    application.add_handler(
        CallbackQueryHandler(show_belmarket_card, pattern=f"^{BELMARKET_CARD_CALLBACK}$")
    )
    application.add_handler(
        CallbackQueryHandler(retire_legacy_refresh, pattern=f"^{LEGACY_REFRESH_CALLBACK}$")
    )
    return application


def main() -> None:
    """Load configuration and run the bot with Telegram long polling."""

    try:
        settings = BotSettings.from_environment()
    except SettingsError as exc:
        raise SystemExit(str(exc)) from exc

    logging.basicConfig(
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        level=getattr(logging, settings.log_level, logging.INFO),
    )
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    try:
        application = build_application(settings)
    except SettingsError as exc:
        raise SystemExit(str(exc)) from exc
    application.run_polling(allowed_updates=Update.ALL_TYPES)
