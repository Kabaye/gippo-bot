"""User-facing formatting for cabinet values."""

from __future__ import annotations

from decimal import Decimal

from .cabinet import CabinetStatus


def _format_decimal(value: Decimal, places: int, *, trim_trailing: bool = False) -> str:
    rendered = f"{value:.{places}f}".replace(".", ",")
    if trim_trailing:
        return rendered.rstrip("0").rstrip(",")
    if places == 2:
        whole, fraction = rendered.split(",")
        whole = f"{int(whole):,}".replace(",", " ")
        return f"{whole},{fraction}"
    return rendered


def format_status(status: CabinetStatus) -> str:
    """Format the cabinet status as a concise Russian Telegram message."""

    return "\n".join(
        (
            "Ваша текущая скидка: "
            f"{_format_decimal(status.discount_percent, 2, trim_trailing=True)}%",
            f"Покупки в этом месяце: {_format_decimal(status.monthly_purchases, 2)} руб.",
            f"До следующего уровня: {_format_decimal(status.until_next_level, 2)} руб.",
        )
    )
