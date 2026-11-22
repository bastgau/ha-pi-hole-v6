"""Run the config, reauth and reconfigure flows through Home Assistant's flow manager.

The network boundaries (the connection check and the certificate read) are replaced, because a refused TLS
handshake cannot be exercised here: the Home Assistant test plugin reports the server side of it as an error.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any
from unittest.mock import AsyncMock, patch

from custom_components.pi_hole_v6.config_flow import CONF_CONFIRM_CERTIFICATE
from custom_components.pi_hole_v6.const import (
    CONF_CERT_FINGERPRINT,
    CONF_DEVICE_TRACKER_MAC_LIST,
    CONF_DEVICE_TRACKER_WHITELIST,
    CONF_ENABLE_DEVICE_TRACKER,
    CONF_UPDATE_INTERVAL_LIVE,
    CONF_UPDATE_INTERVAL_STATS,
    CONF_VERIFY_SSL,
    DOMAIN,
)
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL
from homeassistant.data_entry_flow import FlowResultType

if TYPE_CHECKING:
    from collections.abc import Generator

    from homeassistant.core import HomeAssistant

# pytest fixtures are requested by name
# pylint: disable=redefined-outer-name

CONFIG_FLOW = "custom_components.pi_hole_v6.config_flow"
URL = "https://pihole.local:443/api"
FINGERPRINT = "ab" * 32
UNTRUSTED = ({CONF_URL: "untrusted_certificate"}, True)


@pytest.fixture
def no_setup() -> Generator[None]:
    """Do not set the integration up after a flow updated its entry."""
    with patch("custom_components.pi_hole_v6.async_setup_entry", AsyncMock(return_value=True)):
        yield


def _password_default(schema: Any) -> Any:
    """Return the default value the form pre-fills the password field with."""
    for key in schema.schema:
        if str(key) == CONF_PASSWORD:
            default = key.default
            return default() if callable(default) else default
    return None


async def test_self_signed_certificate_with_wrong_password_goes_back_to_the_form(
    hass: HomeAssistant, no_setup: None
) -> None:
    """A self-signed certificate asks for its confirmation, and a wrong password is shown on the form."""
    checks = AsyncMock(side_effect=[UNTRUSTED, ({CONF_PASSWORD: "invalid_auth"}, False)])
    with (
        patch(f"{CONFIG_FLOW}._async_check_connection", checks),
        patch(f"{CONFIG_FLOW}.async_get_certificate_fingerprint", AsyncMock(return_value=FINGERPRINT)),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: "Pi-hole", CONF_URL: URL, CONF_PASSWORD: "wrong", CONF_VERIFY_SSL: True},
        )
        assert result["step_id"] == "pin_certificate"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CONFIRM_CERTIFICATE: True})

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_PASSWORD: "invalid_auth"}
    assert _password_default(result["data_schema"]) == ""


async def test_reauth_with_new_password_saves_the_password_with_the_fingerprint(
    hass: HomeAssistant, no_setup: None
) -> None:
    """Reauthenticating with a new password on an untrusted certificate keeps the new password."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=URL,
        data={
            CONF_NAME: "Pi-hole",
            CONF_URL: URL,
            CONF_PASSWORD: "old-password",
            CONF_VERIFY_SSL: True,
        },
    )
    entry.add_to_hass(hass)

    checks = AsyncMock(side_effect=[UNTRUSTED, ({}, False)])
    with (
        patch(f"{CONFIG_FLOW}._async_check_connection", checks),
        patch(f"{CONFIG_FLOW}.async_get_certificate_fingerprint", AsyncMock(return_value=FINGERPRINT)),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_REAUTH, "entry_id": entry.entry_id},
            data=entry.data,
        )
        assert result["step_id"] == "reauth_confirm"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_PASSWORD: "new-password"})
        assert result["step_id"] == "pin_certificate"

        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CONFIRM_CERTIFICATE: True})

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "new-password"
    assert entry.data[CONF_CERT_FINGERPRINT] == FINGERPRINT


async def test_reconfigure_turning_verification_off_removes_the_pinned_certificate(
    hass: HomeAssistant, no_setup: None
) -> None:
    """Disabling verification in the reconfigure flow drops the fingerprint, so no stale pin stays behind."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=URL,
        data={
            CONF_NAME: "Pi-hole",
            CONF_URL: URL,
            CONF_PASSWORD: "password",
            CONF_VERIFY_SSL: True,
            CONF_CERT_FINGERPRINT: FINGERPRINT,
            CONF_UPDATE_INTERVAL_LIVE: 120,
            CONF_UPDATE_INTERVAL_STATS: 300,
            CONF_ENABLE_DEVICE_TRACKER: False,
            CONF_DEVICE_TRACKER_WHITELIST: True,
            CONF_DEVICE_TRACKER_MAC_LIST: "",
        },
    )
    entry.add_to_hass(hass)

    with patch(f"{CONFIG_FLOW}._async_check_connection", AsyncMock(return_value=({}, False))):
        result = await entry.start_reconfigure_flow(hass)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_URL: URL, CONF_VERIFY_SSL: False},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_VERIFY_SSL] is False
    assert entry.data[CONF_PASSWORD] == "password"
    assert CONF_CERT_FINGERPRINT not in entry.data


async def test_wrong_password_then_url_change_reads_the_new_certificate(hass: HomeAssistant, no_setup: None) -> None:
    """After a wrong password, a new URL gets its own certificate read, not the fingerprint of the first URL."""
    fingerprint_a = "aa" * 32
    fingerprint_b = "bb" * 32
    other_url = "https://other.local:443/api"
    checks = AsyncMock(
        side_effect=[
            UNTRUSTED,
            ({CONF_PASSWORD: "invalid_auth"}, False),
            UNTRUSTED,
        ]
    )
    read = AsyncMock(side_effect=[fingerprint_a, fingerprint_b])
    with (
        patch(f"{CONFIG_FLOW}._async_check_connection", checks),
        patch(f"{CONFIG_FLOW}.async_get_certificate_fingerprint", read),
    ):
        result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: "Pi-hole", CONF_URL: URL, CONF_PASSWORD: "wrong", CONF_VERIFY_SSL: True},
        )
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {CONF_CONFIRM_CERTIFICATE: True})
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_NAME: "Pi-hole", CONF_URL: other_url, CONF_PASSWORD: "right", CONF_VERIFY_SSL: True},
        )

    assert result["step_id"] == "pin_certificate"
    assert result["description_placeholders"]["fingerprint"] == "BB:" * 31 + "BB"
    assert read.await_count == 2
