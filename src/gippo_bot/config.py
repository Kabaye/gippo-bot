"""Environment-based application settings."""

from __future__ import annotations

import os
from dataclasses import dataclass

from .cabinet import DEFAULT_BASE_URL


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
    if not result:
        raise SettingsError("TELEGRAM_ALLOWED_USER_IDS must not be empty")
    return result


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
    allowed_user_ids: frozenset[int]
    cabinet: CabinetSettings
    log_level: str = "INFO"

    @classmethod
    def from_environment(cls) -> BotSettings:
        """Load and validate all bot settings from process environment variables."""

        return cls(
            token=_required("TELEGRAM_BOT_TOKEN"),
            allowed_user_ids=_allowed_user_ids(_required("TELEGRAM_ALLOWED_USER_IDS")),
            cabinet=CabinetSettings.from_environment(),
            log_level=os.getenv("LOG_LEVEL", "INFO").strip().upper() or "INFO",
        )
