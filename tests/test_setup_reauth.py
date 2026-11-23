"""Check that a certificate problem found while the integration runs asks the user to reauthenticate.

The data fetch functions are replaced: a refused TLS handshake cannot be exercised in the test plugin.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from custom_components.pi_hole_v6.const import CONF_VERIFY_SSL, DOMAIN
from custom_components.pi_hole_v6.exceptions import CertificateChangedError, CertificateError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.const import CONF_NAME, CONF_PASSWORD, CONF_URL

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

URL = "https://pihole.local:443/api"
INTEGRATION = "custom_components.pi_hole_v6"


@pytest.mark.parametrize("error", [CertificateError, CertificateChangedError])
async def test_certificate_problem_at_setup_starts_reauth(hass: HomeAssistant, error: type[Exception]) -> None:
    """A certificate that is not trusted, or that changed, opens the reauthentication flow instead of failing silently."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=URL,
        data={CONF_NAME: "Pi-hole", CONF_URL: URL, CONF_PASSWORD: "password", CONF_VERIFY_SSL: True},
    )
    entry.add_to_hass(hass)

    with (
        patch(f"{INTEGRATION}.async_get_live_data", AsyncMock(side_effect=error())),
        patch(f"{INTEGRATION}.async_get_stats_data", AsyncMock(side_effect=error())),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]
