"""Remote HTTP transport smoke test for the ChangeX MCP server.

Starts the FastMCP **Streamable HTTP** app on an *ephemeral* loopback port via
uvicorn in a background thread, performs a real MCP ``initialize`` + ``tools/list``
handshake over HTTP with the official MCP client, asserts the expected tools are
exposed, then shuts the server down. A second case asserts the bearer-token guard
rejects an unauthenticated request with 401.

The whole module skips cleanly (``pytest.skip``) when the HTTP transport deps
(uvicorn / starlette / the MCP Streamable-HTTP client) are unavailable, so the
core suite still runs in a minimal environment.
"""

from __future__ import annotations

import socket
import threading
import time
from collections.abc import Iterator
from contextlib import closing
from typing import Any

import pytest

# Skip the whole module unless every HTTP-transport dependency is importable.
pytest.importorskip("uvicorn", reason="uvicorn is required for the HTTP transport")
pytest.importorskip("starlette", reason="starlette is required for the HTTP transport")
pytest.importorskip("httpx", reason="httpx is required for the MCP HTTP client")
pytest.importorskip(
    "mcp.client.streamable_http",
    reason="mcp Streamable-HTTP client is required for this test",
)

import uvicorn  # noqa: E402

from changex_mcp import server, transport  # noqa: E402

# The six MVP tools plus accept/reject — what tools/list must surface over HTTP.
EXPECTED_TOOLS = {
    "open_tracked",
    "get_outline",
    "edit",
    "save_tracked",
    "reject",
    "accept",
    "get_changes",
    "render_review",
}

TEST_TOKEN = "test-bearer-token-123"


def _free_socket() -> tuple[socket.socket, int]:
    """Bind a loopback socket on an ephemeral port and return it + the port."""
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("127.0.0.1", 0))
    return sock, sock.getsockname()[1]


class _ServerThread:
    """Run a uvicorn server on a pre-bound socket in a daemon thread."""

    def __init__(self, app: Any, sock: socket.socket) -> None:
        config = uvicorn.Config(app, log_level="warning")
        self._server = uvicorn.Server(config)
        self._server.config.load()
        self._sock = sock
        self._thread = threading.Thread(target=self._run, daemon=True)

    def _run(self) -> None:
        import asyncio

        asyncio.run(self._server.serve(sockets=[self._sock]))

    def __enter__(self) -> "_ServerThread":
        self._thread.start()
        deadline = time.monotonic() + 10.0
        while not self._server.started and time.monotonic() < deadline:
            time.sleep(0.02)
        if not self._server.started:  # pragma: no cover - startup failure
            raise RuntimeError("uvicorn server did not start in time")
        return self

    def __exit__(self, *_exc: object) -> None:
        self._server.should_exit = True
        self._thread.join(timeout=10.0)


@pytest.fixture()
def http_url() -> Iterator[str]:
    """Serve the authed Streamable-HTTP app on an ephemeral port; yield its URL."""
    sock, port = _free_socket()
    settings = transport.TransportSettings(
        transport="http",
        host="127.0.0.1",
        port=port,
        path="/mcp",
        token=TEST_TOKEN,
    )
    # Bind to 127.0.0.1 ONLY — this test never opens a routable interface.
    assert settings.is_loopback
    # A fresh FastMCP per server: its Streamable-HTTP session manager can only
    # start once, so the two server fixtures must not share one instance.
    app = transport.build_http_app(server.build_mcp(), settings)
    with closing(sock):
        with _ServerThread(app, sock):
            yield f"http://127.0.0.1:{port}/mcp"


async def _initialize_and_list(url: str, token: str) -> list[str]:
    """Run an MCP initialize + tools/list over Streamable HTTP; return tool names."""
    import inspect

    from mcp import ClientSession
    import mcp.client.streamable_http as sh

    headers = {"Authorization": f"Bearer {token}"}
    # The SDK ships two spellings across versions with different signatures: the
    # legacy ``streamablehttp_client(url, headers=...)`` takes headers directly;
    # the newer ``streamable_http_client(url, *, http_client=...)`` wants a
    # pre-configured httpx client. Pick whichever accepts a ``headers`` kwarg.
    legacy = getattr(sh, "streamablehttp_client", None)
    modern = getattr(sh, "streamable_http_client", None)
    if legacy is not None and "headers" in inspect.signature(legacy).parameters:
        ctx = legacy(url, headers=headers)
    else:  # pragma: no cover - exercised only on SDKs without the headers kwarg
        import httpx

        client = httpx.AsyncClient(headers=headers)
        ctx = modern(url, http_client=client)

    async with ctx as (read, write, _):
        async with ClientSession(read, write) as session:
            await session.initialize()
            listed = await session.list_tools()
            return [tool.name for tool in listed.tools]


def test_initialize_and_tools_list_over_http(http_url: str) -> None:
    """A full MCP handshake over HTTP exposes every ChangeX tool."""
    import anyio

    names = anyio.run(_initialize_and_list, http_url, TEST_TOKEN)
    assert EXPECTED_TOOLS.issubset(set(names)), f"missing tools: {EXPECTED_TOOLS - set(names)}"


def test_missing_bearer_token_is_rejected(http_url: str) -> None:
    """The MCP endpoint refuses a request without a valid bearer token (401)."""
    import httpx

    # No Authorization header at all → 401 from the bearer-auth middleware.
    resp = httpx.post(
        http_url,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
        json={"jsonrpc": "2.0", "id": 1, "method": "ping"},
        timeout=10.0,
    )
    assert resp.status_code == 401
    assert "bearer" in resp.text.lower()


def test_build_settings_refuses_public_bind_without_token() -> None:
    """Sanity: the bind policy refuses a non-loopback host lacking flag/token."""
    with pytest.raises(transport.InsecureBindError):
        transport.build_settings(["--http", "--host", "0.0.0.0", "--public"])
