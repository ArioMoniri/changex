"""ChangeX HTTP/REST API: the changex-core spine, re-exposed over plain HTTP.

This package wraps :mod:`changex_core` (reusing the MCP tool semantics from
:mod:`changex_mcp.tools`) in a FastAPI app so ANY caller can drive tracked
editing over HTTP — a local/offline model with no function-calling, a ``curl``
script, or a ChatGPT custom GPT whose Action imports the auto-generated
``/openapi.json``.

Public surface (used by the entry point and tests):

App
    ``app.app`` — the configured :class:`fastapi.FastAPI` instance;
    ``app.create_app()`` — a factory that builds a fresh app with its own
    in-process session store.

Runner
    ``__main__.main`` — the ``changex-api`` console script / ``python -m
    changex_api`` entry point (launches uvicorn, 127.0.0.1 by default).

Models
    ``models`` — the Pydantic request/response models that shape the OpenAPI
    schema consumed by ChatGPT Actions and other clients.
"""

from __future__ import annotations

__version__ = "0.1.0"

__all__ = ["__version__"]
