"""Lightweight, dependency-free validation of v0.2 ops, headers and events.

The published contract is ``schema.json`` (JSON Schema draft-07). To keep the
core importable with **zero external dependencies**, this module hand-rolls the
subset of validation we actually need (required keys, allowed kinds, type
checks, reserved-op rejection) rather than pulling in ``jsonschema`` at runtime.

The accepted v0.3 set is the docx text/structure ops, the docx run-format and
paragraph-move ops (``format.run``, ``node.move``), and the spreadsheet/slide ops
(``cell.set``, ``formula.set``, ``row.insert``, ``row.delete``, ``slide.insert``,
``slide.delete``, ``shape.edit``). No op kinds remain reserved.

The JSON Schema remains the source of truth and is what downstream consumers /
other languages validate against; this module is kept in lock-step with it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from changex_core.ops.vocabulary import (
    OP_SCHEMA_VERSION,
    V01_KINDS,
    _RESERVED_KINDS,
)

SCHEMA_PATH = Path(__file__).with_name("schema.json")

# Required keys per v0.2 op kind, mirroring schema.json definitions.
_OP_REQUIRED: dict[str, set[str]] = {
    # docx (v0.1, unchanged)
    "text.insert": {"kind", "node_id", "before_anchor", "text"},
    "text.delete": {"kind", "node_id", "before"},
    "text.replace": {"kind", "node_id", "before", "after"},
    "node.insert": {"kind", "node_kind", "position", "value"},
    "node.delete": {"kind", "node_id", "value"},
    "style.change": {"kind", "node_id", "style", "before"},
    # docx run-format + paragraph-move (v0.3)
    "format.run": {"kind", "node_id", "props", "before"},
    "node.move": {"kind", "node_id", "from_index", "to_index"},
    # xlsx / csv (v0.2)
    "cell.set": {"kind", "sheet", "ref", "before", "after"},
    "formula.set": {"kind", "sheet", "ref", "before", "after"},
    "row.insert": {"kind", "sheet", "at"},
    "row.delete": {"kind", "sheet", "at", "value"},
    # pptx (v0.2)
    "slide.insert": {"kind", "at", "value"},
    "slide.delete": {"kind", "at", "value"},
    "shape.edit": {"kind", "slide", "shape_id", "op"},
}


class SchemaValidationError(ValueError):
    """Raised when an op / header / event fails v0.1 validation."""


def load_schema() -> dict[str, Any]:
    """Load and return the published JSON Schema document."""
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_op(op: dict[str, Any]) -> None:
    """Validate a single op dict against the v0.1 op set.

    Raises:
        SchemaValidationError: on a reserved/unknown kind, missing keys, or a
            wrong-typed required field.
    """
    if not isinstance(op, dict):
        raise SchemaValidationError("op must be a JSON object")
    kind = op.get("kind")
    if kind in _RESERVED_KINDS:
        raise SchemaValidationError(
            f"op kind {kind!r} is reserved/not-yet-implemented in v{OP_SCHEMA_VERSION}"
        )
    if kind not in V01_KINDS:
        raise SchemaValidationError(f"unknown op kind {kind!r}")
    required = _OP_REQUIRED[kind]
    missing = required - set(op.keys())
    if missing:
        raise SchemaValidationError(f"op {kind!r} missing keys: {sorted(missing)}")
    extra = set(op.keys()) - required
    if extra:
        raise SchemaValidationError(f"op {kind!r} has unexpected keys: {sorted(extra)}")
    _check_op_types(kind, op)


def _check_int(op: dict[str, Any], field: str, *, minimum: int | None = None) -> None:
    """Assert ``op[field]`` is a non-bool int (optionally ``>= minimum``)."""
    value = op[field]
    if not isinstance(value, int) or isinstance(value, bool):
        raise SchemaValidationError(f"{op.get('kind')}.{field} must be an integer")
    if minimum is not None and value < minimum:
        raise SchemaValidationError(f"{op.get('kind')}.{field} must be >= {minimum}")


def _check_op_types(kind: str, op: dict[str, Any]) -> None:
    # --- docx (v0.1) -----------------------------------------------------------
    if kind == "node.insert":
        _check_int(op, "position", minimum=0)
        if not isinstance(op["value"], dict):
            raise SchemaValidationError("node.insert.value must be an object")
    elif kind == "node.delete":
        if not isinstance(op["value"], dict):
            raise SchemaValidationError("node.delete.value must be an object")
    # --- docx run-format + paragraph-move (v0.3) -------------------------------
    elif kind == "format.run":
        if not isinstance(op["props"], dict):
            raise SchemaValidationError("format.run.props must be an object")
        if not isinstance(op["before"], dict):
            raise SchemaValidationError("format.run.before must be an object")
    elif kind == "node.move":
        _check_int(op, "from_index", minimum=0)
        _check_int(op, "to_index", minimum=0)
    # --- xlsx / csv (v0.2) -----------------------------------------------------
    elif kind in ("row.insert", "row.delete"):
        _check_int(op, "at")
        if kind == "row.delete" and not isinstance(op["value"], list):
            raise SchemaValidationError("row.delete.value must be an array")
    # --- pptx (v0.2) -----------------------------------------------------------
    elif kind in ("slide.insert", "slide.delete"):
        _check_int(op, "at")
        if not isinstance(op["value"], dict):
            raise SchemaValidationError(f"{kind}.value must be an object")
    elif kind == "shape.edit":
        _check_int(op, "slide")
        if not isinstance(op["op"], dict):
            raise SchemaValidationError("shape.edit.op must be an object")
    if "before_anchor" in op and op["before_anchor"] is not None:
        if not isinstance(op["before_anchor"], str):
            raise SchemaValidationError("before_anchor must be a string or null")
    # String fields shared across ops (cell.set/formula.set add sheet/ref;
    # shape.edit adds shape_id). before/after stay strings for cell/formula ops.
    # ``format.run`` is exempt from the ``before`` string check: there ``before``
    # is the prior run-property *object*, validated above.
    str_fields = [
        "node_id",
        "text",
        "before",
        "after",
        "style",
        "node_kind",
        "sheet",
        "ref",
        "shape_id",
    ]
    if kind == "format.run":
        str_fields.remove("before")
    for str_field in str_fields:
        if str_field in op and not isinstance(op[str_field], str):
            raise SchemaValidationError(f"{kind}.{str_field} must be a string")


def validate_header(header: dict[str, Any]) -> None:
    """Validate a ``.changex`` header line."""
    if header.get("type") != "header":
        raise SchemaValidationError("header.type must be 'header'")
    for key in ("changex_version", "op_schema_version", "doc", "session"):
        if key not in header:
            raise SchemaValidationError(f"header missing {key!r}")
    doc = header["doc"]
    if not isinstance(doc, dict) or "baseline_sha256" not in doc:
        raise SchemaValidationError("header.doc must contain baseline_sha256")
    session = header["session"]
    if not isinstance(session, dict) or "session_id" not in session:
        raise SchemaValidationError("header.session must contain session_id")


def validate_event(event: dict[str, Any]) -> None:
    """Validate a full op event line (envelope + provenance + op)."""
    if event.get("type") != "op":
        raise SchemaValidationError("event.type must be 'op'")
    for key in (
        "op_id",
        "seq",
        "ts",
        "op_schema_version",
        "provenance",
        "target",
        "op",
        "hash",
        "prev_hash",
    ):
        if key not in event:
            raise SchemaValidationError(f"event missing {key!r}")
    if not isinstance(event["seq"], int) or isinstance(event["seq"], bool) or event["seq"] < 1:
        raise SchemaValidationError("event.seq must be an integer >= 1")
    prov = event["provenance"]
    if not isinstance(prov, dict):
        raise SchemaValidationError("event.provenance must be an object")
    if prov.get("provenance_source") not in ("observed", "declared"):
        raise SchemaValidationError("provenance_source must be 'observed' or 'declared'")
    target = event["target"]
    if not isinstance(target, dict) or "node_id" not in target:
        raise SchemaValidationError("event.target must contain node_id")
    validate_op(event["op"])
