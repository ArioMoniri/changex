"""ChangeX core (M0 spine): canonical model, provenance journal, docx adapter.

Public API (the surface other packages — ``changex-mcp``, the CLI — code against):

Model
    ``Node``, ``NodeKind``, ``NodeIdAllocator``, ``AnchorFingerprint``,
    ``rebind`` — addressable nodes with opaque, edit-invariant ids.

Ops (frozen v0.2)
    docx: ``TextInsert``, ``TextDelete``, ``TextReplace``, ``NodeInsert``,
    ``NodeDelete``, ``StyleChange``. xlsx/csv: ``CellSet``, ``FormulaSet``,
    ``RowInsert``, ``RowDelete``. pptx: ``SlideInsert``, ``SlideDelete``,
    ``ShapeEdit``. Plus ``op_from_dict`` / ``op_to_dict`` and ``validate_op``.
    (``format.run`` / ``node.move`` remain reserved.)

Journal
    ``Journal`` (append / read / replay / verify / revert), ``Header``,
    ``Event``, ``Provenance``, ``Target``, ``VerifyResult``, and the
    canonicalization primitives ``canonicalize`` / ``chain_hash``.

Adapters
    ``DocumentAdapter`` (the contract), ``DocxAdapter`` (native Word
    revisions), and ``load_adapter`` (the extension-keyed factory that lazily
    imports the right adapter for ``.docx`` / ``.xlsx`` / ``.csv`` / ``.pptx``),
    plus the boundary errors ``BeforeMismatchError`` / ``OversizedOpError``.

Render / baseline
    ``render_html`` / ``render_markdown`` and ``snapshot`` /
    ``check_out_of_band``.
"""

from __future__ import annotations

from changex_core.adapters import load_adapter
from changex_core.adapters.base import (
    AdapterError,
    BeforeMismatchError,
    DocumentAdapter,
    NodeNotFoundError,
    OversizedOpError,
    UnsupportedFormatError,
)
from changex_core.adapters.docx_adapter import DocxAdapter
from changex_core.baseline import (
    Baseline,
    OutOfBandWarning,
    check_out_of_band,
    snapshot,
)
from changex_core.journal.canonical import canonicalize, chain_hash, sha256_hex
from changex_core.journal.events import Event, Header, Provenance, Target
from changex_core.journal.journal import Journal, JournalError, VerifyResult
from changex_core.model.addressing import (
    AnchorFingerprint,
    NodeIdAllocator,
    RebindResult,
    rebind,
)
from changex_core.model.nodes import Node, NodeKind
from changex_core.ops.vocabulary import (
    OP_SCHEMA_VERSION,
    CellSet,
    FormulaSet,
    NodeDelete,
    NodeInsert,
    Op,
    ReservedOpError,
    RowDelete,
    RowInsert,
    ShapeEdit,
    SlideDelete,
    SlideInsert,
    StyleChange,
    TextDelete,
    TextInsert,
    TextReplace,
    UnknownOpError,
    op_from_dict,
    op_to_dict,
    target_node_id,
)
from changex_core.diff.text_diff import (
    ParagraphSpec,
    ReconstructedOp,
    diff_paragraphs,
    reconstruct_ops,
)
from changex_core.ops.validation import SchemaValidationError, validate_op
from changex_core.passive import (
    OpenResult,
    SealResult,
    open_passive,
    seal_passive,
)
from changex_core.render.html import render_html, render_markdown
from changex_core.render.save import save_active, save_active_from_path
from changex_core.render.server import build_server, serve

__version__ = "0.1.0"

__all__ = [
    "__version__",
    # model
    "Node",
    "NodeKind",
    "NodeIdAllocator",
    "AnchorFingerprint",
    "RebindResult",
    "rebind",
    # ops (docx, v0.1)
    "Op",
    "TextInsert",
    "TextDelete",
    "TextReplace",
    "NodeInsert",
    "NodeDelete",
    "StyleChange",
    # ops (xlsx/csv + pptx, v0.2)
    "CellSet",
    "FormulaSet",
    "RowInsert",
    "RowDelete",
    "SlideInsert",
    "SlideDelete",
    "ShapeEdit",
    "OP_SCHEMA_VERSION",
    "op_from_dict",
    "op_to_dict",
    "target_node_id",
    "validate_op",
    "SchemaValidationError",
    "ReservedOpError",
    "UnknownOpError",
    # journal
    "Journal",
    "JournalError",
    "VerifyResult",
    "Header",
    "Event",
    "Provenance",
    "Target",
    "canonicalize",
    "chain_hash",
    "sha256_hex",
    # adapters
    "DocumentAdapter",
    "DocxAdapter",
    "load_adapter",
    "AdapterError",
    "BeforeMismatchError",
    "OversizedOpError",
    "NodeNotFoundError",
    "UnsupportedFormatError",
    # render / baseline
    "render_html",
    "render_markdown",
    "Baseline",
    "OutOfBandWarning",
    "snapshot",
    "check_out_of_band",
    # render: journal-aware save + interactive review server
    "save_active",
    "save_active_from_path",
    "build_server",
    "serve",
    # passive ("native to any model") capture + diff reconstruction
    "open_passive",
    "seal_passive",
    "OpenResult",
    "SealResult",
    "ParagraphSpec",
    "ReconstructedOp",
    "diff_paragraphs",
    "reconstruct_ops",
]
