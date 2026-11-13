"""Check the detection of the account access from GET /auth/sessions."""

from unittest.mock import AsyncMock, MagicMock

from custom_components.pi_hole_v6.api import Api
from custom_components.pi_hole_v6.const import (
    ACCESS_APP_NO_SUDO,
    ACCESS_APP_SUDO,
    ACCESS_MAIN_PASSWORD,
    ACCESS_RESTRICTED,
)
from custom_components.pi_hole_v6.exceptions import ForbiddenError
import pytest

REFUSAL_BODY = {
    "error": {
        "key": "forbidden",
        "message": "Unable to list sessions. App sessions without webserver.api.app_sudo and CLI sessions cannot list sessions.",
    }
}


def make_api(*, sessions: list[dict] | None = None, refusal: ForbiddenError | None = None) -> Api:
    """Build an Api whose HTTP call is replaced by a canned answer."""

    # pylint: disable=protected-access
    api = Api(session=MagicMock())

    if refusal is not None:
        api._call = AsyncMock(side_effect=refusal)  # type: ignore[method-assign]
    else:
        api._call = AsyncMock(  # type: ignore[method-assign]
            return_value={"code": 200, "reason": "OK", "data": {"sessions": sessions}}
        )

    return api


@pytest.mark.parametrize(
    ("app", "expected"),
    [(False, ACCESS_MAIN_PASSWORD), (True, ACCESS_APP_SUDO)],
)
async def test_access_from_current_session(app: bool, expected: str) -> None:
    """The app flag of the current session tells main password and application password apart."""

    api = make_api(
        sessions=[
            {"id": 1, "current_session": False, "app": not app},
            {"id": 2, "current_session": True, "app": app},
        ]
    )

    await api.call_get_auth_sessions()

    assert api.account_access == expected


async def test_access_unknown_without_current_session() -> None:
    """The access stays unknown when the current session is not in the list."""

    api = make_api(sessions=[{"id": 1, "current_session": False, "app": True}])

    await api.call_get_auth_sessions()

    assert api.account_access is None


async def test_refusal_mentioning_app_sudo() -> None:
    """A 403 whose message names app_sudo is an application session without sudo, and is not raised."""

    refusal = ForbiddenError()
    refusal.body = REFUSAL_BODY
    api = make_api(refusal=refusal)
    api.cache_auth_sessions = [{"id": 1}]

    result = await api.call_get_auth_sessions()

    assert result["code"] == 403
    assert api.account_access == ACCESS_APP_NO_SUDO
    assert api.cache_auth_sessions == []


async def test_refusal_without_message_is_restricted() -> None:
    """A 403 that does not name app_sudo stays a generic restriction."""

    api = make_api(refusal=ForbiddenError())

    await api.call_get_auth_sessions()

    assert api.account_access == ACCESS_RESTRICTED
