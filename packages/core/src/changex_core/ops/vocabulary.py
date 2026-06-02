"""Frozen v0.2 operation vocabulary (docx + xlsx/csv/pptx contract).

This is the shared op set that both the adapter and the (separate) MCP package
build on. It is deliberately small and intent-named — the path of least
resistance for a model must still produce small, attributable ops.

Design rules baked in here:

* Text offsets are **node-relative** and **seq-ordered** — never absolute file
  coordinates. We address by ``node_id`` and validate the agent-supplied
  ``before`` substring against the node's *current* state.
* Spreadsheet/slide ops address by **natural key** (``sheet``/``ref`` for cells,
  positional ``at`` for rows/slides, ``slide``/``shape_id`` for shapes) — the
  format-native analogue of a docx ``node_id``.
* Each op carries the prior ``before`` / ``value`` it needs to be **rejected or
  replayed without the original file** (reversibility invariant).
* ``node_kind`` (not ``kind_of``) names the target structural type — resolving
  the historic ``kind`` / ``kind_of`` overload.

Frozen v0.2 op set (the kinds validation accepts and adapters implement):

docx (unchanged from v0.1)
    ``text.insert``, ``text.delete``, ``text.replace``, ``node.insert``,
    ``node.delete``, ``style.change``.
xlsx / csv
    ``cell.set``, ``formula.set``, ``row.insert``, ``row.delete``.
pptx
    ``slide.insert``, ``slide.delete``, ``shape.edit``.

Still RESERVED (rejected at parse time): ``format.run`` and ``node.move``.
Constructing a reserved kind from this set raises :class:`ReservedOpError`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, ClassVar, Union

OP_SCHEMA_VERSION = "0.2"

# Kinds that remain reserved but not implemented in v0.2; rejected at parse time.
_RESERVED_KINDS = frozenset(
    {
        "format.run",
        "node.move",
    }
)


class ReservedOpError(ValueError):
    """Raised when a journal references an op kind reserved for a later version."""


class UnknownOpError(ValueError):
    """Raised when an op ``kind`` is neither a v0.1 op nor a reserved one."""


@dataclass(frozen=True)
class TextInsert:
    """Insert ``text`` after the ``before_anchor`` substring within a node.

    If ``before_anchor`` is ``None`` the text is appended at the end of the node.
    Rendered as ``w:ins > w:r > w:t``.
    """

    node_id: str
    before_anchor: str | None
    text: str
    kind: ClassVar[str] = "text.insert"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "node_id": self.node_id,
            "before_anchor": self.before_anchor,
            "text": self.text,
        }


@dataclass(frozen=True)
class TextDelete:
    """Delete the exact ``before`` substring from a node.

    ``before`` is validated against current node content. Rendered as
    ``w:del > w:r > w:delText``.
    """

    node_id: str
    before: str
    kind: ClassVar[str] = "text.delete"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "node_id": self.node_id, "before": self.before}


@dataclass(frozen=True)
class TextReplace:
    """Replace the exact ``before`` substring with ``after`` within a node.

    Rendered as a ``w:del``(delText) immediately followed by a ``w:ins``(t).
    """

    node_id: str
    before: str
    after: str
    kind: ClassVar[str] = "text.replace"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "node_id": self.node_id,
            "before": self.before,
            "after": self.after,
        }


@dataclass(frozen=True)
class NodeInsert:
    """Insert a new structural node (a paragraph for v0.1) at ``position``.

    ``value`` is the node payload, e.g. ``{"text": "...", "style": "Normal"}``.
    The inserted paragraph mark is rendered as a pilcrow-insertion revision.
    """

    node_kind: str
    position: int
    value: dict[str, Any]
    kind: ClassVar[str] = "node.insert"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "node_kind": self.node_kind,
            "position": self.position,
            "value": dict(self.value),
        }


@dataclass(frozen=True)
class NodeDelete:
    """Delete a structural node, capturing its ``value`` for reject/replay.

    Rendered by marking the node's runs as ``w:del`` and the paragraph mark as a
    pilcrow-deletion revision.
    """

    node_id: str
    value: dict[str, Any]
    kind: ClassVar[str] = "node.delete"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "node_id": self.node_id, "value": dict(self.value)}


@dataclass(frozen=True)
class StyleChange:
    """Change a paragraph's style, capturing the prior ``before`` style name.

    Rendered as a ``w:pPrChange`` carrying the previous paragraph properties.
    """

    node_id: str
    style: str
    before: str
    kind: ClassVar[str] = "style.change"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "node_id": self.node_id,
            "style": self.style,
            "before": self.before,
        }


# --------------------------------------------------------------------------- #
# v0.2 spreadsheet ops (xlsx, csv). Addressed by natural key (sheet + ref / at).
# These carry both ``before`` and ``after`` (or ``value``) so a reject/replay
# never needs the original workbook — the reversibility invariant for cells.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class CellSet:
    """Set a cell's *value* (not formula) to ``after``, recording ``before``.

    ``sheet`` is the worksheet name and ``ref`` the A1 cell reference (e.g.
    ``"B7"``). ``before``/``after`` are the cell's displayed/stored values,
    serialized as strings (numbers stringified at the boundary) so the op shape
    is uniform and JSON-safe. Rendered as a colored cell + a threaded comment in
    the non-native xlsx overlay (csv: redline projection).
    """

    sheet: str
    ref: str
    before: str
    after: str
    kind: ClassVar[str] = "cell.set"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "sheet": self.sheet,
            "ref": self.ref,
            "before": self.before,
            "after": self.after,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CellSet":
        return cls(
            sheet=str(data["sheet"]),
            ref=str(data["ref"]),
            before=str(data["before"]),
            after=str(data["after"]),
        )

    def target_node_id(self) -> str:
        """Natural-key address of the targeted cell (``sheet!ref``)."""
        return f"{self.sheet}!{self.ref}"


@dataclass(frozen=True)
class FormulaSet:
    """Set a cell's *formula* to ``after``, recording the prior ``before``.

    Distinct from :class:`CellSet`: ``before``/``after`` are formula strings
    (e.g. ``"=B7*1.1"``). Keeping value-edits and formula-edits as separate kinds
    lets the overlay annotate "value changed" vs "formula changed" precisely.
    """

    sheet: str
    ref: str
    before: str
    after: str
    kind: ClassVar[str] = "formula.set"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "sheet": self.sheet,
            "ref": self.ref,
            "before": self.before,
            "after": self.after,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "FormulaSet":
        return cls(
            sheet=str(data["sheet"]),
            ref=str(data["ref"]),
            before=str(data["before"]),
            after=str(data["after"]),
        )

    def target_node_id(self) -> str:
        """Natural-key address of the targeted cell (``sheet!ref``)."""
        return f"{self.sheet}!{self.ref}"


@dataclass(frozen=True)
class RowInsert:
    """Insert a new (empty) row at 1-based position ``at`` on ``sheet``.

    Insert is value-free (the new row starts empty); subsequent ``cell.set`` ops
    populate it. Rendered as an inserted/highlighted row in the overlay.
    """

    sheet: str
    at: int
    kind: ClassVar[str] = "row.insert"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "sheet": self.sheet, "at": self.at}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RowInsert":
        return cls(sheet=str(data["sheet"]), at=int(data["at"]))

    def target_node_id(self) -> str:
        """Natural-key address of the targeted row (``sheet!<at>:<at>``)."""
        return f"{self.sheet}!{self.at}:{self.at}"


@dataclass(frozen=True)
class RowDelete:
    """Delete the row at 1-based position ``at`` on ``sheet``.

    ``value`` captures the deleted row's cells (list of stringified cell values)
    so the delete can be rejected/replayed without the original workbook — the
    reversibility invariant for structural row edits.
    """

    sheet: str
    at: int
    value: list[Any]
    kind: ClassVar[str] = "row.delete"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "sheet": self.sheet,
            "at": self.at,
            "value": list(self.value),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RowDelete":
        return cls(
            sheet=str(data["sheet"]),
            at=int(data["at"]),
            value=list(data["value"]),
        )

    def target_node_id(self) -> str:
        """Natural-key address of the targeted row (``sheet!<at>:<at>``)."""
        return f"{self.sheet}!{self.at}:{self.at}"


# --------------------------------------------------------------------------- #
# v0.2 slide ops (pptx). Slides addressed positionally (``at``); shapes by id.
# --------------------------------------------------------------------------- #


@dataclass(frozen=True)
class SlideInsert:
    """Insert a new slide at 0-based position ``at``.

    ``value`` is the new slide payload (e.g. ``{"layout": "...", "title": "..."}``)
    captured so the op replays without the original deck. Rendered as a revision
    callout / summary-slide entry in the non-native pptx overlay.
    """

    at: int
    value: dict[str, Any]
    kind: ClassVar[str] = "slide.insert"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "at": self.at, "value": dict(self.value)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SlideInsert":
        return cls(at=int(data["at"]), value=dict(data["value"]))

    def target_node_id(self) -> str:
        """Positional address of the targeted slide (``slide[<at>]``)."""
        return f"slide[{self.at}]"


@dataclass(frozen=True)
class SlideDelete:
    """Delete the slide at 0-based position ``at``.

    ``value`` captures the removed slide's payload for reject/replay (the
    reversibility invariant for slides).
    """

    at: int
    value: dict[str, Any]
    kind: ClassVar[str] = "slide.delete"

    def to_dict(self) -> dict[str, Any]:
        return {"kind": self.kind, "at": self.at, "value": dict(self.value)}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SlideDelete":
        return cls(at=int(data["at"]), value=dict(data["value"]))

    def target_node_id(self) -> str:
        """Positional address of the targeted slide (``slide[<at>]``)."""
        return f"slide[{self.at}]"


@dataclass(frozen=True)
class ShapeEdit:
    """Edit a shape on a slide via a nested op payload.

    ``slide`` is the 0-based slide index, ``shape_id`` the pptx shape id, and
    ``op`` the nested operation describing the change (e.g. a text op dict for a
    text-frame edit). Keeping the nested op opaque here lets the pptx adapter
    interpret text/format sub-ops without widening this contract.
    """

    slide: int
    shape_id: str
    op: dict[str, Any]
    kind: ClassVar[str] = "shape.edit"

    def to_dict(self) -> dict[str, Any]:
        return {
            "kind": self.kind,
            "slide": self.slide,
            "shape_id": self.shape_id,
            "op": dict(self.op),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ShapeEdit":
        return cls(
            slide=int(data["slide"]),
            shape_id=str(data["shape_id"]),
            op=dict(data["op"]),
        )

    def target_node_id(self) -> str:
        """Positional+id address of the targeted shape (``slide[<i>]/shape:<id>``)."""
        return f"slide[{self.slide}]/shape:{self.shape_id}"


Op = Union[
    TextInsert,
    TextDelete,
    TextReplace,
    NodeInsert,
    NodeDelete,
    StyleChange,
    CellSet,
    FormulaSet,
    RowInsert,
    RowDelete,
    SlideInsert,
    SlideDelete,
    ShapeEdit,
]

_BY_KIND: dict[str, type] = {
    TextInsert.kind: TextInsert,
    TextDelete.kind: TextDelete,
    TextReplace.kind: TextReplace,
    NodeInsert.kind: NodeInsert,
    NodeDelete.kind: NodeDelete,
    StyleChange.kind: StyleChange,
    CellSet.kind: CellSet,
    FormulaSet.kind: FormulaSet,
    RowInsert.kind: RowInsert,
    RowDelete.kind: RowDelete,
    SlideInsert.kind: SlideInsert,
    SlideDelete.kind: SlideDelete,
    ShapeEdit.kind: ShapeEdit,
}

# Kept named ``V01_KINDS`` for source compatibility; now the full v0.2 accepted
# set (every non-reserved kind validation/from_dict will construct).
V01_KINDS = frozenset(_BY_KIND.keys())
V02_KINDS = V01_KINDS


def op_to_dict(op: Op) -> dict[str, Any]:
    """Serialize any v0.2 op to its journal dict form."""
    return op.to_dict()


def op_from_dict(data: dict[str, Any]) -> Op:
    """Reconstruct a v0.2 op from its dict form.

    Ops that define a ``from_dict`` classmethod (the v0.2 spreadsheet/slide ops,
    which coerce numeric fields) are built through it; the original v0.1 docx ops
    keep the historic ``cls(**payload)`` path.

    Raises:
        ReservedOpError: if ``kind`` is a reserved-but-unimplemented op.
        UnknownOpError: if ``kind`` is not recognised at all.
    """
    kind = data.get("kind")
    if kind in _RESERVED_KINDS:
        raise ReservedOpError(
            f"op kind {kind!r} is reserved and not implemented in v{OP_SCHEMA_VERSION}"
        )
    cls = _BY_KIND.get(kind or "")
    if cls is None:
        raise UnknownOpError(f"unknown op kind {kind!r}")
    from_dict = getattr(cls, "from_dict", None)
    if callable(from_dict):
        return from_dict(data)  # type: ignore[no-any-return]
    payload = {k: v for k, v in data.items() if k != "kind"}
    return cls(**payload)  # type: ignore[arg-type]


def target_node_id(op: Op) -> str | None:
    """Return the address an op targets, or ``None`` when it has no fixed target.

    For docx ops this is the ``node_id`` attribute. For the v0.2 spreadsheet/slide
    ops (which address by natural key) it is the op's ``target_node_id()`` method
    (e.g. ``"Q3!B7"`` for a cell, ``"slide[3]"`` for a slide/row). ``node.insert``
    (which has no ``node_id`` and defines no ``target_node_id``) returns ``None``;
    the row/slide insert ops return their positional address.
    """
    method = getattr(op, "target_node_id", None)
    if callable(method):
        return method()  # type: ignore[no-any-return]
    return getattr(op, "node_id", None)
