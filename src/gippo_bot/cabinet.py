"""HTTP client and parser for the GIPPO loyalty cabinet."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation

import httpx
from bs4 import BeautifulSoup

DEFAULT_BASE_URL = "https://cabinet.gippo.by"


class GippoError(RuntimeError):
    """Base error raised by the GIPPO cabinet integration."""


class GippoAuthenticationError(GippoError):
    """Raised when the cabinet does not accept the configured credentials."""


class GippoPageError(GippoError):
    """Raised when the expected loyalty values cannot be read from the page."""


@dataclass(frozen=True, slots=True)
class CabinetStatus:
    """Loyalty values displayed by the GIPPO personal cabinet."""

    discount_percent: Decimal
    monthly_purchases: Decimal
    until_next_level: Decimal
    fetched_at: datetime


_VALUE_PATTERNS = {
    "discount_percent": re.compile(
        r"Ваша\s+текущая\s+скидка\s*([0-9]+(?:[.,][0-9]+)?)\s*%",
        re.IGNORECASE,
    ),
    "monthly_purchases": re.compile(
        r"Ваши\s+покупки\s+в\s+этом\s+месяце\s*"
        r"([0-9][0-9\s]*(?:[.,][0-9]+)?)",
        re.IGNORECASE,
    ),
    "until_next_level": re.compile(
        r"До\s+следующего\s+уровня\s+осталось\s*"
        r"([0-9][0-9\s]*(?:[.,][0-9]+)?)",
        re.IGNORECASE,
    ),
}


def _to_decimal(raw_value: str) -> Decimal:
    normalized = raw_value.replace("\xa0", "").replace(" ", "").replace(",", ".")
    try:
        return Decimal(normalized)
    except InvalidOperation as exc:
        raise GippoPageError("The cabinet returned an invalid numeric value") from exc


def parse_personal_page(html: str) -> CabinetStatus:
    """Extract loyalty values from an authenticated personal-cabinet page."""

    text = BeautifulSoup(html, "html.parser").get_text(" ", strip=True)
    values: dict[str, Decimal] = {}

    for field, pattern in _VALUE_PATTERNS.items():
        match = pattern.search(text)
        if match is None:
            raise GippoPageError(f"The cabinet page does not contain {field}")
        values[field] = _to_decimal(match.group(1))

    return CabinetStatus(
        discount_percent=values["discount_percent"],
        monthly_purchases=values["monthly_purchases"],
        until_next_level=values["until_next_level"],
        fetched_at=datetime.now(UTC),
    )


class GippoClient:
    """Authenticate to the GIPPO cabinet and fetch the current loyalty status."""

    def __init__(
        self,
        login: str,
        password: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 20,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        self._login = login
        self._password = password
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds
        self._transport = transport

    def fetch_status(self) -> CabinetStatus:
        """Sign in and return the three loyalty values from `/personal/`."""

        try:
            return self._fetch_status()
        except httpx.HTTPError as exc:
            raise GippoError("Could not communicate with the GIPPO cabinet") from exc

    def _fetch_status(self) -> CabinetStatus:
        headers = {
            "Accept-Language": "ru,en;q=0.9",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
            ),
        }
        with httpx.Client(
            base_url=self._base_url,
            headers=headers,
            timeout=self._timeout_seconds,
            follow_redirects=True,
            transport=self._transport,
        ) as client:
            auth_response = client.post(
                "/local/ajax/auth.php",
                files={
                    "PROP_RQ[LOGIN]": (None, self._login),
                    "PROP_RQ[PASSWORD]": (None, self._password),
                    "PROP[REMEMBER]": (None, "Y"),
                },
                headers={
                    "Accept": "application/json, text/javascript, */*; q=0.01",
                    "Origin": self._base_url,
                    "Referer": f"{self._base_url}/index.php",
                    "X-Requested-With": "XMLHttpRequest",
                },
            )
            auth_response.raise_for_status()

            personal_response = client.get(
                "/personal/",
                headers={
                    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                    "Referer": f"{self._base_url}/index.php",
                },
            )
            personal_response.raise_for_status()

        returned_to_login = (
            "/personal" not in personal_response.url.path
            or "PROP_RQ[PASSWORD]" in personal_response.text
        )
        if returned_to_login:
            raise GippoAuthenticationError("GIPPO cabinet authentication was not accepted")

        return parse_personal_page(personal_response.text)
