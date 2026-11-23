"""Read the TLS certificate presented by the Pi-hole, to pin its SHA-256 fingerprint."""

from __future__ import annotations

import hashlib
import ssl
from typing import TYPE_CHECKING
from urllib.parse import urlsplit

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant

DEFAULT_HTTPS_PORT = 443


def format_fingerprint(fingerprint: str) -> str:
    """Format a hexadecimal SHA-256 fingerprint the way openssl displays it: upper case, pairs separated by colons.

    Args:
        fingerprint (str): The fingerprint in lowercase hexadecimal, without separators.

    Returns:
        str: The fingerprint as shown by ``openssl x509 -fingerprint -sha256``, for example ``8C:1B:2F:…``.

    """
    return ":".join(fingerprint[i : i + 2] for i in range(0, len(fingerprint), 2)).upper()


# Without a timeout, an unresponsive host would block the executor and the flow indefinitely.
CERTIFICATE_TIMEOUT_SECONDS = 10


def _read_certificate_fingerprint(host: str, port: int) -> str:
    """Connect to the server and return the SHA-256 digest of the certificate it presents.

    The certificate is read without validating it: the user confirms its fingerprint instead.

    Args:
        host (str): The host name or address of the Pi-hole.
        port (int): The TCP port of the Pi-hole API.

    Returns:
        str: The SHA-256 digest of the DER-encoded certificate, in lowercase hexadecimal.

    """
    pem: str = ssl.get_server_certificate((host, port), timeout=CERTIFICATE_TIMEOUT_SECONDS)
    return hashlib.sha256(ssl.PEM_cert_to_DER_cert(pem)).hexdigest()


async def async_get_certificate_fingerprint(hass: HomeAssistant, url: str) -> str:
    """Return the SHA-256 fingerprint of the certificate presented at the given API URL.

    Args:
        hass (HomeAssistant): The Home Assistant instance, used to run the blocking socket work in an executor.
        url (str): The Pi-hole API URL, which must use https.

    Returns:
        str: The SHA-256 digest of the certificate, in lowercase hexadecimal.

    Raises:
        ValueError: If the URL does not use https or has no host name.

    """
    parts = urlsplit(url)

    if parts.scheme.lower() != "https" or not parts.hostname:
        msg: str = "A certificate can only be pinned for an https URL with a host name."
        raise ValueError(msg)

    return await hass.async_add_executor_job(
        _read_certificate_fingerprint,
        parts.hostname,
        parts.port or DEFAULT_HTTPS_PORT,
    )
