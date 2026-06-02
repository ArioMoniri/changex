"""Frozen v0.1 operation vocabulary + dependency-free validation."""

from __future__ import annotations

from changex_core.ops.validation import (
    SchemaValidationError,
    load_schema,
    validate_event,
    validate_header,
    validate_op,
)
from changex_core.ops.vocabulary import (
    OP_SCHEMA_VERSION,
    V01_KINDS,
    NodeDelete,
    NodeInsert,
    Op,
    ReservedOpError,
    StyleChange,
    TextDelete,
    TextInsert,
    TextReplace,
    UnknownOpError,
    op_from_dict,
    op_to_dict,
    target_node_id,
)

__all__ = [
    "Op",
    "TextInsert",
    "TextDelete",
    "TextReplace",
    "NodeInsert",
    "NodeDelete",
    "StyleChange",
    "OP_SCHEMA_VERSION",
    "V01_KINDS",
    "op_to_dict",
    "op_from_dict",
    "target_node_id",
    "ReservedOpError",
    "UnknownOpError",
    "validate_op",
    "validate_header",
    "validate_event",
    "load_schema",
    "SchemaValidationError",
]
