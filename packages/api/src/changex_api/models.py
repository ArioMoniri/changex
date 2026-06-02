"""Pydantic request/response models for the ChangeX REST API.

These are deliberately explicit (typed fields + descriptions + examples) because
they ARE the OpenAPI schema that a ChatGPT custom GPT Action consumes at
``/openapi.json``. Good field descriptions here become good tool affordances for
any model calling the API. The semantics mirror the MCP tools 1:1
(:mod:`changex_mcp.tools`): an ``op`` discriminator selects one small intent and
its required payload, the exact ``before`` substring is always carried so the
adapter can refuse blind overwrites, and an oversized op is rejected so the model
splits the change.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# The intent discriminators accepted by POST /sessions/{id}/edit, mirroring
# ``changex_mcp.tools.EDIT_OPS``.
EditOp = Literal["replace_text", "insert_text_after", "delete_text", "set_paragraph_style"]


class AgentContext(BaseModel):
    """Once-per-session declared identity (captured at open, never per-edit)."""

    model: Optional[str] = Field(
        default=None,
        description="Your model id, e.g. 'claude-opus-4-8' or 'gpt-4o'. Recorded "
        "once for the whole session and used as the Word revision author.",
    )
    vendor: Optional[str] = Field(
        default=None, description="Your vendor, e.g. 'anthropic', 'openai', 'google'."
    )


# -- open / sessions ----------------------------------------------------------


class OpenTrackedRequest(BaseModel):
    """Body for POST /sessions — open a .docx for tracked editing."""

    path: str = Field(
        ...,
        description="Absolute server-side path to the .docx to open for tracked editing.",
        examples=["/data/contract.docx"],
    )
    agent_context: Optional[AgentContext] = Field(
        default=None,
        description="Optional once-per-session declared identity {model, vendor}.",
    )
    author: Optional[str] = Field(
        default=None,
        description="Override the Word revision author (defaults to the model id).",
    )


class OpenTrackedResponse(BaseModel):
    """Session handle + summary returned by POST /sessions."""

    handle: str = Field(..., description="Opaque session handle; pass it to every other call.")
    session_id: str = Field(..., description="Stable journal session id (provenance identity).")
    baseline_sha256: str = Field(..., description="SHA-256 of the opened baseline bytes.")
    summary: dict[str, Any] = Field(
        ..., description="{filename, paragraphs, agent, vendor, changex_path}."
    )


# -- outline ------------------------------------------------------------------


class OutlineEntry(BaseModel):
    """One paragraph node in a paginated outline page."""

    node_id: str = Field(..., description="Durable node id; use it as an edit target.")
    kind: str = Field(..., description="Node kind, e.g. 'paragraph'.")
    preview: str = Field(..., description="Truncated text preview for discovery.")
    style: Optional[str] = Field(default=None, description="Paragraph style name, if any.")


class OutlineResponse(BaseModel):
    """A bounded outline page plus the cursor to fetch the next one."""

    nodes: list[OutlineEntry]
    next_cursor: Optional[str] = Field(
        default=None, description="Pass back as ?cursor= to page forward; null when done."
    )
    total: int = Field(..., description="Total paragraph count in the document.")


# -- edit ---------------------------------------------------------------------


class EditRequest(BaseModel):
    """Body for POST /sessions/{id}/edit — apply ONE small intent-named edit.

    ``op`` selects the intent and its required payload:

    * ``replace_text``        — node_id, before (exact current text), after
    * ``insert_text_after``   — node_id, anchor (exact text to insert after), text
    * ``delete_text``         — node_id, before (exact text to delete)
    * ``set_paragraph_style`` — node_id, style (new), before (current style name)
    """

    op: EditOp = Field(..., description="The edit intent.")
    node_id: str = Field(..., description="Target node id (from the outline).")
    before: Optional[str] = Field(
        default=None,
        description="Exact CURRENT text/style to match; the server refuses blind overwrites.",
    )
    after: Optional[str] = Field(default=None, description="Replacement text for replace_text.")
    anchor: Optional[str] = Field(
        default=None, description="Exact text to insert after (insert_text_after)."
    )
    text: Optional[str] = Field(default=None, description="Text to insert (insert_text_after).")
    style: Optional[str] = Field(
        default=None, description="New paragraph style (set_paragraph_style)."
    )
    rationale: Optional[str] = Field(default=None, description="Optional declared 'why'.")
    prompt: Optional[str] = Field(
        default=None, description="Optional prompt; hashed to prompt_sha256, never stored verbatim."
    )
    turn_id: Optional[str] = Field(default=None, description="Optional declared turn id.")


class EditResponse(BaseModel):
    """Result of one journaled edit."""

    op_id: str = Field(..., description="Stable id of the journaled op.")
    seq: int = Field(..., description="Server-assigned monotonic sequence number.")
    node_id: str = Field(..., description="Resolved target node id.")
    provenance_source: str = Field(..., description="'declared' or 'observed'.")


# -- save / changes -----------------------------------------------------------


class SaveRequest(BaseModel):
    """Body for POST /sessions/{id}/save — render the tracked .docx."""

    out: str = Field(
        ...,
        description="Absolute server-side .docx path to write the native-revisions file to.",
        examples=["/data/contract.tracked.docx"],
    )


class SaveResponse(BaseModel):
    """Paths + verification result after a save."""

    tracked_path: str
    changex_path: str
    ops: int = Field(..., description="Number of active (non-reverted) ops written.")
    verified: bool = Field(..., description="Whether the journal hash-chain verified.")


class ChangesResponse(BaseModel):
    """The structured provenance journal (active, non-reverted events)."""

    session_id: str
    events: list[dict[str, Any]]
    count: int
    verified: bool


# -- passive open / seal ------------------------------------------------------


class PassiveOpenRequest(BaseModel):
    """Body for POST /open — start a passive (no-tool-calling) capture session."""

    docx: str = Field(..., description="Absolute path to the .docx to snapshot.")
    changex: Optional[str] = Field(
        default=None, description="Optional sidecar journal path (.changex/.jsonl)."
    )


class PassiveOpenResponse(BaseModel):
    """Outcome of POST /open."""

    changex_path: str
    session_id: str
    baseline_sha256: str
    paragraphs: int


class PassiveSealRequest(BaseModel):
    """Body for POST /seal — diff the edited docx vs the stored baseline."""

    docx: str = Field(..., description="Absolute path to the (now edited) .docx.")
    changex: Optional[str] = Field(default=None, description="Optional sidecar journal path.")


class PassiveSealResponse(BaseModel):
    """Honest, degraded capture counts from a passive seal."""

    changex_path: str
    appended: int
    replaced: int
    inserted: int
    deleted: int
    style_changed: int
    baseline_unchanged: bool
    degraded: bool = Field(
        default=True,
        description="Always true: passive ops are observed net deltas, not true provenance.",
    )


# -- report -------------------------------------------------------------------


class ReportResponse(BaseModel):
    """A rendered HTML/markdown redline of a session's journal."""

    format: str = Field(..., description="'html' or 'markdown'.")
    report: str = Field(..., description="The rendered redline.")


# -- shared -------------------------------------------------------------------


class HealthResponse(BaseModel):
    """Liveness probe payload."""

    status: Literal["ok"] = "ok"
    service: str = "changex-api"
    version: str


class ErrorResponse(BaseModel):
    """Structured boundary error mirroring the MCP ToolError shape."""

    error: str = Field(..., description="Stable machine-readable code, e.g. 'split_required'.")
    detail: str = Field(..., description="Human/agent-facing instruction.")
