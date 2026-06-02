"""Transport selection + secure remote HTTP serving for the ChangeX MCP server.

The default transport is **stdio**, unchanged: ``changex-mcp`` keeps launching the
local stdio server that desktop MCP clients spawn. The new path is a **remote
Streamable HTTP** transport (``changex-mcp --http``) so connector-URL clients —
claude.ai *custom connectors* and ChatGPT *app connectors*, both of which dial an
MCP server over a URL rather than spawning a local process — can reach this
server.

Security posture (this server edits local files on disk, so a careless bind is a
remote-write hole):

* The default bind host is ``127.0.0.1`` (loopback only). Loopback needs no token.
* Binding to any **non-loopback** host (a routable IP, a hostname, or ``0.0.0.0``)
  is refused unless BOTH are true:
    1. the operator passed the explicit ``--public`` flag (or
       ``CHANGEX_MCP_PUBLIC=1``), acknowledging the exposure, and
    2. a bearer token is configured via ``CHANGEX_MCP_TOKEN``.
  A public bind without a token raises :class:`InsecureBindError` and prints a
  clear warning, rather than silently exposing file-editing tools to the network.
* When a token is configured, the HTTP app enforces ``Authorization: Bearer
  <token>`` on the MCP endpoint(s); loopback binds may still set a token and it is
  enforced if present.

Everything here is typed and side-effect-light: :func:`build_settings` does the
pure policy/validation, :func:`serve_http` does the uvicorn I/O. Tests import
:func:`build_http_app` to drive the ASGI app on an ephemeral port without binding
a routable interface.
"""

from __future__ import annotations

import argparse
import hmac
import os
import sys
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any, Optional

# Loopback hosts that are safe to bind without a bearer token.
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000
DEFAULT_PATH = "/mcp"

# Environment variable names (documented in the README).
ENV_TRANSPORT = "CHANGEX_MCP_TRANSPORT"  # "stdio" | "http" | "sse"
ENV_HOST = "CHANGEX_MCP_HOST"
ENV_PORT = "CHANGEX_MCP_PORT"
ENV_PATH = "CHANGEX_MCP_PATH"
ENV_TOKEN = "CHANGEX_MCP_TOKEN"  # bearer token for the HTTP transport
ENV_PUBLIC = "CHANGEX_MCP_PUBLIC"  # "1"/"true" to acknowledge a non-loopback bind


class TransportConfigError(ValueError):
    """Raised for an invalid transport configuration (bad port, unknown name)."""


class InsecureBindError(TransportConfigError):
    """Raised when a non-loopback bind is requested without flag + token.

    This is the load-bearing security guard: it stops a file-editing MCP server
    from being exposed to the network without an explicit, authenticated opt-in.
    """


@dataclass(frozen=True)
class TransportSettings:
    """A validated, ready-to-serve transport configuration.

    ``transport`` is one of ``"stdio"``, ``"http"`` (Streamable HTTP), or
    ``"sse"``. The HTTP fields are only meaningful for the two HTTP transports.
    ``token`` is the bearer secret enforced on the HTTP endpoint (or ``None`` for
    an unauthenticated loopback bind).
    """

    transport: str = "stdio"
    host: str = DEFAULT_HOST
    port: int = DEFAULT_PORT
    path: str = DEFAULT_PATH
    token: Optional[str] = None

    @property
    def is_loopback(self) -> bool:
        """True when the host is a recognized loopback address."""
        return is_loopback_host(self.host)

    @property
    def url(self) -> str:
        """The connector URL shape an MCP client would dial for this bind."""
        return f"http://{self.host}:{self.port}{self.path}"


def is_loopback_host(host: str) -> bool:
    """Return True if ``host`` is loopback-only (safe without a token)."""
    return host.strip().lower() in _LOOPBACK_HOSTS


# -- CLI / env parsing --------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the ``changex-mcp`` argument parser (stdio by default)."""
    parser = argparse.ArgumentParser(
        prog="changex-mcp",
        description=(
            "ChangeX MCP server. Default transport is local stdio. Use --http for "
            "a remote Streamable HTTP transport that connector-URL clients "
            "(claude.ai custom connectors, ChatGPT app connectors) can reach."
        ),
    )
    parser.add_argument(
        "--http",
        action="store_true",
        help="Serve over remote Streamable HTTP instead of stdio.",
    )
    parser.add_argument(
        "--sse",
        action="store_true",
        help="Serve over the (legacy) HTTP+SSE transport instead of stdio.",
    )
    parser.add_argument(
        "--host",
        default=None,
        help=f"HTTP bind host (default {DEFAULT_HOST}; env {ENV_HOST}).",
    )
    parser.add_argument(
        "--port",
        default=None,
        help=f"HTTP bind port (default {DEFAULT_PORT}; env {ENV_PORT}).",
    )
    parser.add_argument(
        "--path",
        default=None,
        help=f"HTTP endpoint path (default {DEFAULT_PATH}; env {ENV_PATH}).",
    )
    parser.add_argument(
        "--public",
        action="store_true",
        help=(
            "Acknowledge binding a non-loopback host. REQUIRED (with a bearer "
            f"token in {ENV_TOKEN}) to expose this file-editing server off "
            "localhost."
        ),
    )
    return parser


def build_settings(argv: Optional[list[str]] = None) -> TransportSettings:
    """Resolve CLI args + environment into a validated :class:`TransportSettings`.

    Precedence is CLI flag > environment variable > built-in default. The
    security policy (non-loopback ⇒ ``--public`` + token) is enforced here, before
    any socket is opened.
    """
    args = build_parser().parse_args(argv)
    env = os.environ

    transport = _resolve_transport(args, env)
    if transport == "stdio":
        # stdio ignores host/port/token entirely — it is the unchanged local path.
        return TransportSettings(transport="stdio")

    host = (args.host or env.get(ENV_HOST) or DEFAULT_HOST).strip()
    port = _resolve_port(args.port if args.port is not None else env.get(ENV_PORT))
    path = _normalize_path(args.path or env.get(ENV_PATH) or DEFAULT_PATH)
    token = _clean_token(env.get(ENV_TOKEN))
    public = bool(args.public) or _env_flag(env.get(ENV_PUBLIC))

    _enforce_bind_policy(host=host, token=token, public=public)

    return TransportSettings(
        transport=transport,
        host=host,
        port=port,
        path=path,
        token=token,
    )


def _resolve_transport(args: argparse.Namespace, env: Mapping[str, str]) -> str:
    """Decide the transport name from flags then env, defaulting to stdio."""
    if args.http and args.sse:
        raise TransportConfigError("choose only one of --http / --sse")
    if args.http:
        return "http"
    if args.sse:
        return "sse"
    raw = (env.get(ENV_TRANSPORT) or "stdio").strip().lower()
    if raw in ("", "stdio"):
        return "stdio"
    if raw in ("http", "streamable-http", "streamable_http"):
        return "http"
    if raw == "sse":
        return "sse"
    raise TransportConfigError(
        f"{ENV_TRANSPORT}={raw!r} is invalid; use 'stdio', 'http', or 'sse'."
    )


def _resolve_port(value: Any) -> int:
    """Coerce a CLI/env port to an int in the valid TCP range (0 ⇒ ephemeral)."""
    if value is None:
        return DEFAULT_PORT
    try:
        port = int(str(value).strip())
    except (TypeError, ValueError) as exc:
        raise TransportConfigError(f"port must be an integer, got {value!r}") from exc
    if not (0 <= port <= 65535):
        raise TransportConfigError(f"port {port} out of range 0-65535")
    return port


def _normalize_path(path: str) -> str:
    """Ensure the endpoint path starts with a single leading slash."""
    p = path.strip()
    if not p.startswith("/"):
        p = "/" + p
    return p.rstrip("/") or "/"


def _clean_token(value: Optional[str]) -> Optional[str]:
    """Return a stripped, non-empty token or ``None``."""
    if value is None:
        return None
    token = value.strip()
    return token or None


def _env_flag(value: Optional[str]) -> bool:
    """Interpret an env var as a boolean opt-in flag."""
    if value is None:
        return False
    return value.strip().lower() in ("1", "true", "yes", "on")


def _enforce_bind_policy(*, host: str, token: Optional[str], public: bool) -> None:
    """Refuse an unsafe non-loopback bind; loopback binds are always allowed."""
    if is_loopback_host(host):
        return
    problems: list[str] = []
    if not public:
        problems.append("pass --public (or set CHANGEX_MCP_PUBLIC=1)")
    if not token:
        problems.append(f"set a bearer token in {ENV_TOKEN}")
    if problems:
        warning = (
            f"REFUSING to bind ChangeX MCP (a local-file editor) to non-loopback "
            f"host {host!r}: " + " AND ".join(problems) + ". "
            "Binding off localhost without authentication would expose "
            "file-editing tools to the network."
        )
        print(f"[changex-mcp] {warning}", file=sys.stderr)
        raise InsecureBindError(warning)


# -- bearer-auth middleware ---------------------------------------------------


def _make_auth_middleware(token: str, protected_prefix: str) -> Any:
    """Build a Starlette BaseHTTPMiddleware class enforcing a bearer token.

    Only requests whose path is under ``protected_prefix`` are guarded, so a
    future health endpoint stays open while the MCP endpoint requires the token.
    Comparison is constant-time to avoid leaking the token via timing.
    """
    from starlette.middleware.base import BaseHTTPMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse

    class BearerAuthMiddleware(BaseHTTPMiddleware):
        async def dispatch(self, request: Request, call_next: Any) -> Any:
            if request.url.path.startswith(protected_prefix):
                header = request.headers.get("authorization", "")
                if not _bearer_ok(header, token):
                    return JSONResponse(
                        {"error": "unauthorized", "detail": "missing/invalid bearer token"},
                        status_code=401,
                        headers={"WWW-Authenticate": 'Bearer realm="changex-mcp"'},
                    )
            return await call_next(request)

    return BearerAuthMiddleware


def _bearer_ok(authorization_header: str, expected: str) -> bool:
    """Constant-time check of an ``Authorization: Bearer <token>`` header."""
    parts = authorization_header.split(" ", 1)
    if len(parts) != 2 or parts[0].lower() != "bearer":
        return False
    return hmac.compare_digest(parts[1].strip(), expected)


# -- app construction + serving -----------------------------------------------


def build_http_app(mcp: Any, settings: TransportSettings) -> Any:
    """Return the Starlette ASGI app for the chosen HTTP transport, with auth.

    ``mcp`` is the configured :class:`~mcp.server.fastmcp.FastMCP` instance. We
    set its host/port/path settings, obtain the SDK's Streamable-HTTP (or SSE)
    Starlette app, and wrap it with bearer auth when a token is configured.
    """
    mcp.settings.host = settings.host
    mcp.settings.port = settings.port
    if settings.transport == "sse":
        mcp.settings.sse_path = settings.path
        app = mcp.sse_app()
    else:
        mcp.settings.streamable_http_path = settings.path
        app = mcp.streamable_http_app()

    if settings.token:
        app.add_middleware(
            _make_auth_middleware(settings.token, protected_prefix=settings.path)
        )
    return app


def serve_http(mcp: Any, settings: TransportSettings) -> None:
    """Serve ``mcp`` over HTTP via uvicorn (blocking) using ``settings``.

    Prints the connector URL and whether auth is active so the operator sees the
    exact URL to paste into a claude.ai / ChatGPT connector.
    """
    import uvicorn

    app = build_http_app(mcp, settings)
    auth_state = "bearer-token auth ON" if settings.token else "NO auth (loopback)"
    scope = "loopback" if settings.is_loopback else "PUBLIC"
    print(
        f"[changex-mcp] serving {settings.transport} on {settings.url} "
        f"({scope}, {auth_state})",
        file=sys.stderr,
    )
    config = uvicorn.Config(
        app,
        host=settings.host,
        port=settings.port,
        log_level="info",
    )
    uvicorn.Server(config).run()
