"""The ChangeX HTTP/REST API — a thin FastAPI wrapper over ``changex_core``.

Why this exists: ChangeX already exposes its tracked-editing spine over MCP
(:mod:`changex_mcp`). This package re-exposes the *same* semantics over plain
HTTP so ANY caller can use it — a local/offline model with no function-calling, a
shell script with ``curl``, or a ChatGPT custom GPT whose Action consumes the
auto-generated ``/openapi.json``. The endpoint set mirrors the MCP tools 1:1.

Design notes:

* **Reuse, not reimplementation.** The tracked-editing tools delegate to
  :mod:`changex_mcp.tools` against an in-process :class:`SessionStore`, so the
  boundary enforcement (before-substring validation, oversized-op rejection) and
  the structured error codes are byte-for-byte the same as MCP. The passive
  ``/open`` + ``/seal`` and ``/report`` endpoints call the core directly.
* **Path-sanitized.** Every caller-supplied path goes through
  :func:`changex_core.paths.safe_path` (the same guard the core uses) before any
  I/O, rejecting directory traversal / NUL bytes / wrong suffixes.
* **Local by default.** ``create_app`` binds nothing itself; the runner
  (:mod:`changex_api.__main__`) defaults to ``127.0.0.1``. When a token is set via
  ``CHANGEX_API_TOKEN`` (required for any non-local bind), every route except the
  liveness probe demands a matching ``Authorization: Bearer <token>`` header.
"""

from __future__ import annotations

import os
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from fastapi.responses import HTMLResponse

from changex_core.journal.journal import Journal
from changex_core.paths import UnsafePathError, safe_path
from changex_core.passive import open_passive, seal_passive
from changex_core.render.html import render_html, render_markdown

from changex_mcp import tools
from changex_mcp.session import SessionError, SessionStore

from changex_api import __version__ as _API_VERSION
from changex_api.models import (
    ChangesResponse,
    EditRequest,
    EditResponse,
    HealthResponse,
    OpenTrackedRequest,
    OpenTrackedResponse,
    OutlineResponse,
    PassiveOpenRequest,
    PassiveOpenResponse,
    PassiveSealRequest,
    PassiveSealResponse,
    ReportResponse,
    SaveRequest,
    SaveResponse,
)

#: Environment variable holding the bearer token. When set, all non-health routes
#: require ``Authorization: Bearer <CHANGEX_API_TOKEN>``. Leave unset only for a
#: trusted local (127.0.0.1) bind.
TOKEN_ENV = "CHANGEX_API_TOKEN"

# Starlette renamed 422 to *_CONTENT; prefer the new name, fall back for older
# pins so the package works across the supported FastAPI/Starlette range. (The
# deprecated alias is only touched when the new constant is absent, so newer
# Starlette never triggers its DeprecationWarning.)
if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT"):
    HTTP_422 = status.HTTP_422_UNPROCESSABLE_CONTENT
else:  # pragma: no cover - depends on the installed Starlette version
    HTTP_422 = status.HTTP_422_UNPROCESSABLE_ENTITY

API_TITLE = "ChangeX API"
API_DESCRIPTION = (
    "Provenance-first tracked editing for Word documents, over HTTP. Open a .docx "
    "for tracked editing, discover node ids via the outline, make the SMALLEST "
    "possible intent-named edit per call (always passing the exact existing text in "
    "`before` — blind overwrites are refused), then save a native Word "
    "accept/reject revisions file plus a hash-chained .changex provenance journal. "
    "A passive (no-tool-calling) /open + /seal path serves offline models. This "
    "schema is consumable directly as a ChatGPT custom GPT Action."
)


def _require_token(authorization: str | None = Header(default=None)) -> None:
    """Enforce bearer-token auth iff ``CHANGEX_API_TOKEN`` is set.

    When the env var is unset (the local-only default) this is a no-op so the
    127.0.0.1 developer flow needs no header. When it is set, every guarded route
    requires ``Authorization: Bearer <token>`` and rejects anything else with 401.
    """
    expected = os.environ.get(TOKEN_ENV)
    if not expected:
        return
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    presented = authorization[len("Bearer ") :].strip()
    if presented != expected:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="invalid bearer token",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _tool_error_http(exc: tools.ToolError) -> HTTPException:
    """Map an MCP ToolError to an HTTP 4xx carrying its structured payload.

    ``already_open`` is a conflict (409); ``open_failed`` is a bad request (400);
    everything else (split_required, before_mismatch, node_not_found, …) is a 422
    unprocessable entity — the model should read the detail and adjust the op.
    """
    if exc.code == "already_open":
        code = status.HTTP_409_CONFLICT
    elif exc.code in ("open_failed", "bad_format"):
        code = status.HTTP_400_BAD_REQUEST
    else:
        code = HTTP_422
    return HTTPException(status_code=code, detail=exc.to_dict())


def _value_error_http(exc: Exception) -> HTTPException:
    """Map a validation / unsafe-path error to a 400 with a structured payload."""
    code = "unsafe_path" if isinstance(exc, UnsafePathError) else "invalid_argument"
    return HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail={"error": code, "detail": str(exc)},
    )


def create_app() -> FastAPI:
    """Build and return the configured FastAPI application.

    A single in-process :class:`SessionStore` backs the tracked-editing routes
    (one process, single-session-per-handle — same model as the MCP server). The
    returned app auto-serves its OpenAPI schema at ``/openapi.json``; that schema
    is exactly what a ChatGPT custom GPT Action imports.
    """
    store = SessionStore()
    app = FastAPI(
        title=API_TITLE,
        description=API_DESCRIPTION,
        version=_API_VERSION,
    )

    guard = [Depends(_require_token)]

    # -- liveness (unauthenticated) -------------------------------------------

    @app.get("/healthz", response_model=HealthResponse, tags=["meta"], operation_id="healthz")
    def healthz() -> HealthResponse:
        """Liveness probe; never requires auth."""
        return HealthResponse(version=_API_VERSION)

    # -- tracked editing (mirrors the MCP tools) ------------------------------

    @app.post(
        "/sessions",
        response_model=OpenTrackedResponse,
        tags=["tracked"],
        dependencies=guard,
        operation_id="openTracked",
    )
    def open_session(body: OpenTrackedRequest) -> Any:
        """Open a .docx for tracked editing and return a session handle + summary."""
        agent_ctx = body.agent_context.model_dump() if body.agent_context else None
        try:
            return tools.open_tracked(
                store, path=body.path, agent_context=agent_ctx, author=body.author
            )
        except tools.ToolError as exc:
            raise _tool_error_http(exc) from exc

    @app.get(
        "/sessions/{handle}/outline",
        response_model=OutlineResponse,
        tags=["tracked"],
        dependencies=guard,
        operation_id="getOutline",
    )
    def get_outline(
        handle: str,
        cursor: str | None = Query(default=None, description="Opaque pagination cursor."),
        limit: int = Query(default=100, ge=1, le=500, description="Max entries per page."),
    ) -> Any:
        """Return a bounded, paginated outline of the document's paragraphs."""
        try:
            return tools.get_outline(store, handle=handle, cursor=cursor, limit=limit)
        except tools.ToolError as exc:
            raise _tool_error_http(exc) from exc
        except SessionError as exc:
            raise _unknown_handle_http(exc) from exc
        except (ValueError, KeyError) as exc:
            raise _value_error_http(exc) from exc

    @app.post(
        "/sessions/{handle}/edit",
        response_model=EditResponse,
        tags=["tracked"],
        dependencies=guard,
        operation_id="editSession",
    )
    def edit(handle: str, body: EditRequest) -> Any:
        """Apply ONE small, intent-named tracked edit to a node and journal it."""
        try:
            return tools.edit(
                store,
                handle=handle,
                op=body.op,
                node_id=body.node_id,
                before=body.before,
                after=body.after,
                anchor=body.anchor,
                text=body.text,
                style=body.style,
                rationale=body.rationale,
                prompt=body.prompt,
                turn_id=body.turn_id,
            )
        except tools.ToolError as exc:
            raise _tool_error_http(exc) from exc
        except SessionError as exc:
            raise _unknown_handle_http(exc) from exc
        except (ValueError, KeyError) as exc:
            raise _value_error_http(exc) from exc

    @app.post(
        "/sessions/{handle}/save",
        response_model=SaveResponse,
        tags=["tracked"],
        dependencies=guard,
        operation_id="saveSession",
    )
    def save(handle: str, body: SaveRequest) -> Any:
        """Save the native-revisions .docx and report the tracked + .changex paths."""
        try:
            return tools.save_tracked(store, handle=handle, out=body.out)
        except tools.ToolError as exc:
            raise _tool_error_http(exc) from exc
        except SessionError as exc:
            raise _unknown_handle_http(exc) from exc
        except (ValueError, KeyError) as exc:
            raise _value_error_http(exc) from exc

    @app.get(
        "/sessions/{handle}/changes",
        response_model=ChangesResponse,
        tags=["tracked"],
        dependencies=guard,
        operation_id="getChanges",
    )
    def get_changes(handle: str) -> Any:
        """Return the structured provenance journal (active, non-reverted events)."""
        try:
            return tools.get_changes(store, handle=handle)
        except tools.ToolError as exc:
            raise _tool_error_http(exc) from exc
        except SessionError as exc:
            raise _unknown_handle_http(exc) from exc
        except (ValueError, KeyError) as exc:
            raise _value_error_http(exc) from exc

    # -- passive ("native to any model") open / seal --------------------------

    @app.post(
        "/open",
        response_model=PassiveOpenResponse,
        tags=["passive"],
        dependencies=guard,
        operation_id="passiveOpen",
    )
    def passive_open(body: PassiveOpenRequest) -> PassiveOpenResponse:
        """Snapshot a docx and write a pending passive journal (no tool calls).

        Any tool may then edit the docx freely; call /seal to capture the delta.
        """
        try:
            result = open_passive(body.docx, body.changex)
        except (UnsafePathError, ValueError, OSError) as exc:
            raise _value_error_http(exc) from exc
        return PassiveOpenResponse(
            changex_path=str(result.changex_path),
            session_id=result.session_id,
            baseline_sha256=result.baseline.sha256,
            paragraphs=result.paragraphs,
        )

    @app.post(
        "/seal",
        response_model=PassiveSealResponse,
        tags=["passive"],
        dependencies=guard,
        operation_id="passiveSeal",
    )
    def passive_seal(body: PassiveSealRequest) -> PassiveSealResponse:
        """Diff the edited docx vs the stored baseline and append passive ops.

        Returns honest, *degraded* counts: passive ops are observed net textual
        deltas, not true provenance (agent/vendor/prompt are null).
        """
        try:
            result = seal_passive(body.docx, body.changex)
        except (UnsafePathError, ValueError, OSError) as exc:
            raise _value_error_http(exc) from exc
        return PassiveSealResponse(
            changex_path=str(result.changex_path),
            appended=result.appended,
            replaced=result.replaced,
            inserted=result.inserted,
            deleted=result.deleted,
            style_changed=result.style_changed,
            baseline_unchanged=result.baseline_unchanged,
            degraded=result.degraded,
        )

    # -- report (HTML/markdown redline) ---------------------------------------

    @app.post(
        "/report",
        tags=["review"],
        dependencies=guard,
        operation_id="renderReport",
        responses={200: {"content": {"text/html": {}, "application/json": {}}}},
    )
    def report(
        handle: str | None = Query(
            default=None,
            description="An open tracked-session handle to render from.",
        ),
        changex: str | None = Query(
            default=None,
            description="OR a path to a .changex journal to render from (passive flow).",
        ),
        fmt: str = Query(default="html", description="'html' (default) or 'markdown'."),
        raw: bool = Query(
            default=False,
            description="If true, return the report as text/html instead of JSON.",
        ),
    ) -> Any:
        """Render an HTML/markdown redline of a session's or journal's changes.

        Supply either an open ``handle`` (tracked flow) or a ``changex`` journal
        path (passive flow). With ``raw=true`` and ``fmt=html`` the response is a
        ready-to-display ``text/html`` page; otherwise a JSON ``{format, report}``.
        """
        fmt_norm = (fmt or "html").lower()
        if fmt_norm not in ("html", "markdown"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "bad_format", "detail": "fmt must be 'html' or 'markdown'."},
            )
        if handle:
            try:
                payload = tools.render_review(store, handle=handle, fmt=fmt_norm)
            except tools.ToolError as exc:
                raise _tool_error_http(exc) from exc
            except SessionError as exc:
                raise _unknown_handle_http(exc) from exc
            except (ValueError, KeyError) as exc:
                raise _value_error_http(exc) from exc
            rendered = str(payload["report"])
        elif changex:
            rendered = _render_from_journal(changex, fmt_norm)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"error": "missing_argument", "detail": "pass either handle or changex."},
            )
        if raw and fmt_norm == "html":
            return HTMLResponse(content=rendered)
        return ReportResponse(format=fmt_norm, report=rendered)

    return app


def _render_from_journal(changex: str, fmt: str) -> str:
    """Render a redline directly from a ``.changex`` journal path (passive flow)."""
    try:
        path = safe_path(changex, must_exist=True, allow_suffixes=(".changex", ".jsonl"))
        journal = Journal.open(str(path))
    except (UnsafePathError, ValueError, OSError) as exc:
        raise _value_error_http(exc) from exc
    events = journal.active_events()
    return render_markdown(events) if fmt == "markdown" else render_html(events)


def _unknown_handle_http(exc: SessionError) -> HTTPException:
    """Map an unknown-handle error to a 404 so 'bad handle' != 'bad input'.

    ``SessionStore.get`` raises :class:`SessionError` for an unknown handle; we
    surface that as 404 with a structured payload distinct from a 400 input error.
    """
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={"error": "unknown_handle", "detail": str(exc)},
    )


#: Module-level app for ``uvicorn changex_api.app:app`` and the TestClient.
app = create_app()
