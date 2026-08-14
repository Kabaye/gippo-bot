"""Telegram application entry point."""

from __future__ import annotations

import asyncio
import logging

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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
REFRESH_CALLBACK = "refresh_status"


def _refresh_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        [[InlineKeyboardButton("Обновить", callback_data=REFRESH_CALLBACK)]]
    )


def _is_authorized(update: Update, settings: BotSettings) -> bool:
    user = update.effective_user
    return user is not None and user.id in settings.allowed_user_ids


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


async def show_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle `/start` and `/status` for authorized users."""

    settings: BotSettings = context.application.bot_data["settings"]
    if not _is_authorized(update, settings):
        await _deny(update)
        return

    client: GippoClient = context.application.bot_data["gippo_client"]
    message = await _load_message(client)
    if update.effective_message is not None:
        await update.effective_message.reply_text(message, reply_markup=_refresh_keyboard())


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
    await query.edit_message_text(message, reply_markup=_refresh_keyboard())


def build_application(settings: BotSettings) -> Application:
    """Build a configured Telegram application without starting polling."""

    cabinet = settings.cabinet
    client = GippoClient(
        cabinet.login,
        cabinet.password,
        base_url=cabinet.base_url,
        timeout_seconds=cabinet.timeout_seconds,
    )
    application = ApplicationBuilder().token(settings.token).build()
    application.bot_data["settings"] = settings
    application.bot_data["gippo_client"] = client
    application.add_handler(CommandHandler(["start", "status"], show_status))
    application.add_handler(CallbackQueryHandler(refresh_status, pattern=f"^{REFRESH_CALLBACK}$"))
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
    application = build_application(settings)
    application.run_polling(allowed_updates=Update.ALL_TYPES)
