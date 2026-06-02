"""Run the ChangeX API with uvicorn: ``changex-api`` / ``python -m changex_api``.

Binds ``127.0.0.1`` by default (the local, trustworthy path that needs no token).
A non-local bind (any host other than ``127.0.0.1`` / ``localhost`` / ``::1``) is
*refused* unless ``CHANGEX_API_TOKEN`` is set, so the surface is never exposed to
a network without bearer-token auth — a fail-closed default rather than a footgun.

Flags / env:

* ``--host`` / ``CHANGEX_API_HOST`` (default ``127.0.0.1``)
* ``--port`` / ``CHANGEX_API_PORT`` (default ``8000``)
* ``--reload`` for development auto-reload
* ``CHANGEX_API_TOKEN`` — when set, every non-health route requires
  ``Authorization: Bearer <token>``.
"""

from __future__ import annotations

import argparse
import os
import sys

import uvicorn

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8000
_LOCAL_HOSTS = {"127.0.0.1", "localhost", "::1"}
_TOKEN_ENV = "CHANGEX_API_TOKEN"


def _parse_args(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="changex-api",
        description="Serve the ChangeX HTTP/REST API (FastAPI + uvicorn).",
    )
    parser.add_argument(
        "--host",
        default=os.environ.get("CHANGEX_API_HOST", DEFAULT_HOST),
        help="Bind host (default 127.0.0.1). Non-local hosts require CHANGEX_API_TOKEN.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("CHANGEX_API_PORT", DEFAULT_PORT)),
        help="Bind port (default 8000).",
    )
    parser.add_argument(
        "--reload", action="store_true", help="Enable uvicorn auto-reload (development)."
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    """Console-script / ``python -m changex_api`` entry point.

    Returns a process exit code (``0`` on a clean shutdown, ``2`` if a non-local
    bind was requested without a token).
    """
    args = _parse_args(argv)
    host = str(args.host)
    if host not in _LOCAL_HOSTS and not os.environ.get(_TOKEN_ENV):
        sys.stderr.write(
            f"refusing to bind non-local host {host!r} without {_TOKEN_ENV}; "
            f"set {_TOKEN_ENV}=<secret> to enable bearer-token auth, or bind 127.0.0.1.\n"
        )
        return 2
    uvicorn.run(
        "changex_api.app:app",
        host=host,
        port=int(args.port),
        reload=bool(args.reload),
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
