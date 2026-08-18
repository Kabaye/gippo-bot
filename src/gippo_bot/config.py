"""Environment-based application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .cabinet import DEFAULT_BASE_URL

DEFAULT_GIPPO_CARD_IMAGE_PATH = Path("/srv/bots/gippo-bot/private/cards/gippo.png")
DEFAULT_BELMARKET_CARD_IMAGE_PATH = Path("/srv/bots/gippo-bot/private/cards/belmarket.png")


class SettingsError(ValueError):
    """Raised when required application configuration is missing or invalid."""


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise SettingsError(f"Required environment variable is missing: {name}")
    return value


def _allowed_user_ids(raw_value: str) -> frozenset[int]:
    values = [part.strip() for part in raw_value.replace(";", ",").split(",")]
    try:
        result = frozenset(int(value) for value in values if value)
    except ValueError as exc:
        raise SettingsError("TELEGRAM_ALLOWED_USER_IDS must contain numeric IDs") from exc
    return result


def _boolean(name: str, *, default: bool = False) -> bool:
    raw_value = os.getenv(name, str(default)).strip().lower()
    if raw_value in {"1", "true", "yes", "on"}:
        return True
    if raw_value in {"0", "false", "no", "off"}:
        return False
    raise SettingsError(f"{name} must be true or false")


@dataclass(frozen=True, slots=True)
class CabinetSettings:
    """Configuration required to query the cabinet without Telegram."""

    login: str
    password: str
    base_url: str = DEFAULT_BASE_URL
    timeout_seconds: float = 20

    @classmethod
    def from_environment(cls) -> CabinetSettings:
        """Load and validate cabinet settings from process environment variables."""

        try:
            timeout_seconds = float(os.getenv("GIPPO_TIMEOUT_SECONDS", "20"))
        except ValueError as exc:
            raise SettingsError("GIPPO_TIMEOUT_SECONDS must be a number") from exc
        if timeout_seconds <= 0:
            raise SettingsError("GIPPO_TIMEOUT_SECONDS must be greater than zero")

        return cls(
            login=_required("GIPPO_LOGIN"),
            password=_required("GIPPO_PASSWORD"),
            base_url=os.getenv("GIPPO_BASE_URL", DEFAULT_BASE_URL).strip().rstrip("/"),
            timeout_seconds=timeout_seconds,
        )


@dataclass(frozen=True, slots=True)
class BotSettings:
    """Complete Telegram bot configuration."""

    token: str
    open_access: bool
    allowed_user_ids: frozenset[int]
    cabinet: CabinetSettings
    log_level: str = "INFO"
    gippo_card_image_path: Path = DEFAULT_GIPPO_CARD_IMAGE_PATH
    belmarket_card_image_path: Path = DEFAULT_BELMARKET_CARD_IMAGE_PATH

    @classmethod
    def from_environment(cls) -> BotSettings:
        """Load and validate all bot settings from process environment variables."""

        open_access = _boolean("TELEGRAM_OPEN_ACCESS")
        allowed_user_ids = _allowed_user_ids(os.getenv("TELEGRAM_ALLOWED_USER_IDS", ""))
        if not open_access and not allowed_user_ids:
            raise SettingsError(
                "Set TELEGRAM_OPEN_ACCESS=true or provide TELEGRAM_ALLOWED_USER_IDS"
            )

        return cls(
            token=_required("TELEGRAM_BOT_TOKEN"),
            open_access=open_access,
            allowed_user_ids=allowed_user_ids,
            cabinet=CabinetSettings.from_environment(),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
            gippo_card_image_path=Path(
                os.getenv("GIPPO_CARD_IMAGE_PATH", str(DEFAULT_GIPPO_CARD_IMAGE_PATH))
            ).expanduser(),
            belmarket_card_image_path=Path(
                os.getenv("BELMARKET_CARD_IMAGE_PATH", str(DEFAULT_BELMARKET_CARD_IMAGE_PATH))
            ).expanduser(),
        )
