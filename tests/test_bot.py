from types import SimpleNamespace

from gippo_bot.bot import _is_authorized
from gippo_bot.cabinet import DEFAULT_BASE_URL
from gippo_bot.config import BotSettings, CabinetSettings


def _settings(*, open_access: bool, allowed_user_ids: frozenset[int]) -> BotSettings:
    return BotSettings(
        token="token",
        open_access=open_access,
        allowed_user_ids=allowed_user_ids,
        cabinet=CabinetSettings(
            login="login",
            password="password",
            base_url=DEFAULT_BASE_URL,
        ),
    )


def test_open_access_accepts_any_user() -> None:
    update = SimpleNamespace(effective_user=SimpleNamespace(id=999))

    assert _is_authorized(update, _settings(open_access=True, allowed_user_ids=frozenset()))


def test_restricted_access_uses_allow_list() -> None:
    allowed = _settings(open_access=False, allowed_user_ids=frozenset({123}))

    assert _is_authorized(SimpleNamespace(effective_user=SimpleNamespace(id=123)), allowed)
    assert not _is_authorized(SimpleNamespace(effective_user=SimpleNamespace(id=999)), allowed)
