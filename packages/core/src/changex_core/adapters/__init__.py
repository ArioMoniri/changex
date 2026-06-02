"""Document adapters: the contract + the docx native-revisions implementation."""

from __future__ import annotations

from changex_core.adapters.base import (
    AdapterError,
    BeforeMismatchError,
    DocumentAdapter,
    NodeNotFoundError,
    OversizedOpError,
)
from changex_core.adapters.docx_adapter import DocxAdapter

__all__ = [
    "DocumentAdapter",
    "DocxAdapter",
    "AdapterError",
    "BeforeMismatchError",
    "OversizedOpError",
    "NodeNotFoundError",
]
