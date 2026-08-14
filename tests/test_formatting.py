from datetime import UTC, datetime
from decimal import Decimal

from gippo_bot.cabinet import CabinetStatus
from gippo_bot.formatting import format_status


def test_format_status_uses_russian_decimal_notation() -> None:
    status = CabinetStatus(
        discount_percent=Decimal("1"),
        monthly_purchases=Decimal("1247.2"),
        until_next_level=Decimal("252.73"),
        fetched_at=datetime.now(UTC),
    )

    assert format_status(status) == (
        "Ваша текущая скидка: 1%\n"
        "Покупки в этом месяце: 1 247,20 руб.\n"
        "До следующего уровня: 252,73 руб."
    )
