"""Check the certificate pinning against a real local TLS server presenting a self-signed certificate."""

from __future__ import annotations

import contextlib
import hashlib
import socket
import ssl
import subprocess
from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, patch

from aiohttp import ClientConnectorCertificateError, ClientSession, web
from aiohttp.client_reqrep import ConnectionKey
from custom_components.pi_hole_v6.api import Api
from custom_components.pi_hole_v6.certificate import _read_certificate_fingerprint
from custom_components.pi_hole_v6.exceptions import CertificateChangedError, CertificateError
import pytest

if TYPE_CHECKING:
    from collections.abc import AsyncIterator
    from pathlib import Path

# The local TLS server runs on the loopback interface only: sockets are allowed for this module.
pytestmark = pytest.mark.enable_socket

AUTH_STATUS_BODY = {
    "session": {"valid": True, "sid": None, "validity": 1800, "message": ""},
    "took": 0.0,
}


def _make_self_signed_certificate(directory: Path, name: str) -> tuple[Path, Path, str]:
    """Create a self-signed certificate and return its paths and its expected SHA-256 fingerprint."""
    cert: Path = directory / f"{name}.pem"
    key: Path = directory / f"{name}.key"
    subprocess.run(  # noqa: S603
        [  # noqa: S607
            "openssl",
            "req",
            "-x509",
            "-newkey",
            "rsa:2048",
            "-nodes",
            "-days",
            "1",
            "-subj",
            "/CN=localhost",
            "-addext",
            "subjectAltName=DNS:localhost,IP:127.0.0.1",
            "-keyout",
            str(key),
            "-out",
            str(cert),
        ],
        check=True,
        capture_output=True,
    )
    der: bytes = ssl.PEM_cert_to_DER_cert(cert.read_text(encoding="ascii"))
    return cert, key, hashlib.sha256(der).hexdigest()


def _free_port() -> int:
    """Return a TCP port that is free on the loopback interface."""
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


@pytest.fixture
async def tls_server(tmp_path: Path) -> AsyncIterator[tuple[str, str]]:
    """Run an HTTPS server with a self-signed certificate; yield its API URL and certificate fingerprint."""
    cert, key, fingerprint = _make_self_signed_certificate(tmp_path, "pihole")

    async def auth_status(_: web.Request) -> web.Response:
        return web.json_response(AUTH_STATUS_BODY)

    app = web.Application()
    # The client logs in with POST before its first request, then reads the status with GET.
    app.router.add_get("/api/auth", auth_status)
    app.router.add_post("/api/auth", auth_status)

    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(cert), keyfile=str(key))

    runner = web.AppRunner(app)
    await runner.setup()
    port = _free_port()
    site = web.TCPSite(runner, "127.0.0.1", port, ssl_context=context)
    await site.start()
    try:
        yield f"https://127.0.0.1:{port}/api", fingerprint
    finally:
        # A client that refuses the certificate closes the TLS handshake: the server then reports a reset, which is expected.
        with contextlib.suppress(ConnectionResetError):
            await runner.cleanup()


def test_fingerprint_is_sha256_of_the_der_certificate(tmp_path: Path) -> None:
    """The reader returns the SHA-256 digest of the certificate, without validating it."""
    cert, key, expected = _make_self_signed_certificate(tmp_path, "reader")
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(certfile=str(cert), keyfile=str(key))

    port = _free_port()
    listener = socket.create_server(("127.0.0.1", port))
    listener.settimeout(5)

    import threading  # noqa: PLC0415

    def serve() -> None:
        conn, _ = listener.accept()
        with context.wrap_socket(conn, server_side=True):
            pass

    thread = threading.Thread(target=serve, daemon=True)
    thread.start()
    try:
        assert _read_certificate_fingerprint("127.0.0.1", port) == expected
    finally:
        thread.join(timeout=5)
        listener.close()


async def test_untrusted_certificate_error_is_mapped_without_pin() -> None:
    """A TLS verification failure reported by aiohttp is mapped to CertificateError when no fingerprint is pinned.

    A real refused handshake is checked outside the test suite: the Home Assistant test plugin reports the
    server-side reset of a refused handshake as a test error.
    """
    connection_key = ConnectionKey(
        "127.0.0.1", 443, is_ssl=True, ssl=None, proxy=None, proxy_auth=None, proxy_headers_hash=None
    )
    refused = ClientConnectorCertificateError(connection_key, OSError("certificate verify failed"))

    async with ClientSession() as session:
        api = Api(session=session, url="https://127.0.0.1:443/api")
        with patch.object(session, "post", AsyncMock(side_effect=refused)), pytest.raises(CertificateError):
            await api.call_authentification_status()


async def test_matching_pin_is_accepted(tls_server: tuple[str, str]) -> None:
    """A pinned fingerprint matching the presented certificate allows the connection."""
    url, fingerprint = tls_server
    async with ClientSession() as session:
        api = Api(session=session, url=url, certificate_fingerprint=bytes.fromhex(fingerprint))
        result = await api.call_authentification_status()

    assert result["code"] == 200


async def test_changed_certificate_is_refused(tls_server: tuple[str, str]) -> None:
    """A pinned fingerprint that differs from the presented certificate is refused."""
    url, _ = tls_server
    other = hashlib.sha256(b"another certificate").digest()
    async with ClientSession() as session:
        api = Api(session=session, url=url, certificate_fingerprint=other)
        with pytest.raises(CertificateChangedError):
            await api.call_authentification_status()
