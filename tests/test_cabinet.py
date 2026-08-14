from decimal import Decimal
from pathlib import Path

import httpx
import pytest

from gippo_bot.cabinet import (
    GippoAuthenticationError,
    GippoClient,
    GippoError,
    GippoPageError,
    parse_personal_page,
)

FIXTURES = Path(__file__).parent / "fixtures"


def test_parse_personal_page() -> None:
    status = parse_personal_page((FIXTURES / "personal.html").read_text(encoding="utf-8"))

    assert status.discount_percent == Decimal("1")
    assert status.monthly_purchases == Decimal("247.27")
    assert status.until_next_level == Decimal("252.73")


def test_parse_personal_page_accepts_grouped_values() -> None:
    html = """
    Ваша текущая скидка 2,5%
    Ваши покупки в этом месяце 1&nbsp;247,27
    До следующего уровня осталось 2 252.73
    """

    status = parse_personal_page(html)

    assert status.discount_percent == Decimal("2.5")
    assert status.monthly_purchases == Decimal("1247.27")
    assert status.until_next_level == Decimal("2252.73")


def test_parse_personal_page_rejects_missing_value() -> None:
    with pytest.raises(GippoPageError, match="monthly_purchases"):
        parse_personal_page("Ваша текущая скидка 1%")


def test_client_posts_multipart_and_reuses_session_cookie() -> None:
    page = (FIXTURES / "personal.html").read_text(encoding="utf-8")

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/local/ajax/auth.php":
            assert request.method == "POST"
            assert request.headers["x-requested-with"] == "XMLHttpRequest"
            assert "multipart/form-data" in request.headers["content-type"]
            return httpx.Response(200, headers={"set-cookie": "PHPSESSID=valid; Path=/"})
        assert request.url.path == "/personal/"
        assert "PHPSESSID=valid" in request.headers["cookie"]
        return httpx.Response(200, text=page)

    status = GippoClient(
        "+375000000000",
        "secret",
        transport=httpx.MockTransport(handler),
    ).fetch_status()

    assert status.monthly_purchases == Decimal("247.27")


def test_client_rejects_redirected_login_page() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/local/ajax/auth.php":
            return httpx.Response(200)
        return httpx.Response(
            200,
            text='<input name="PROP_RQ[PASSWORD]">',
            request=httpx.Request("GET", "https://cabinet.gippo.by/index.php"),
        )

    with pytest.raises(GippoAuthenticationError):
        GippoClient("login", "wrong", transport=httpx.MockTransport(handler)).fetch_status()


def test_client_wraps_network_errors() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection failed", request=request)

    with pytest.raises(GippoError, match="communicate"):
        GippoClient("login", "password", transport=httpx.MockTransport(handler)).fetch_status()
