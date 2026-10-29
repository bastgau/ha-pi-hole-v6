"""Shared fixtures for the Pi-hole V6 Integration tests."""

# Imported before any Home Assistant fixture starts: Home Assistant then finds the
# integration under the repository's custom_components/, not under the test plugin's
# own testing_config package, which would otherwise be imported first.
import custom_components  # noqa: F401  # pylint: disable=unused-import
import pytest


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Let every test load the integration from custom_components/."""
