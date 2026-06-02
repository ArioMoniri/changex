"""The csv adapter: load -> row/cell model -> apply v0.2 ops -> HTML redline.

Honesty (read this)
-------------------
csv has **no in-file revision concept at all** — a ``.csv`` is plain rows of
plain values, with nothing analogous to Word's accept/reject. The review surface
is therefore entirely the ``.changex`` journal plus a projected HTML **redline**
(unified + side-by-side). :meth:`render_tracked` returns the bytes of that HTML;
:meth:`clean_csv_bytes` returns the shippable plain ``.csv`` result of applying
the ops. The journal is authoritative; the redline is a human-readable lens.

Identity strategy
-----------------
A csv has a single implicit grid, so cells are addressed by **natural key**
``"<sheet>!<ref>"`` where ``<sheet>`` is the logical sheet name carried on the op
(the csv's basename by convention, but any name the journal used is accepted) and
``<ref>`` is an A1 reference (``"B7"``). Each row carries a stable adapter-minted
``rowId`` so a cell *follows its row* under ``row.insert`` / ``row.delete``.

Supported ops: ``cell.set``, ``row.insert``, ``row.delete``. ``formula.set`` is
not meaningful for csv (no formula evaluation) and is rejected.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Any, Optional

from changex_core.adapters.base import (
    BeforeMismatchError,
    DocumentAdapter,
    NodeNotFoundError,
    OversizedOpError,
)
from changex_core.journal.canonical import sha256_hex
from changex_core.model.nodes import Node, NodeKind
from changex_core.ops.vocabulary import (
    CellSet,
    Op,
    RowDelete,
    RowInsert,
)
from changex_core.paths import safe_path
from changex_core.render.csv import CellEdit, build_redline_html

DEFAULT_AUTHOR = "ChangeX agent"
DEFAULT_DATE = "2026-06-02T00:00:00Z"


def _col_to_index(letters: str) -> int:
    """Return the 0-based column index for A1 column ``letters`` (``"B"`` -> 1)."""
    from openpyxl.utils import column_index_from_string

    return column_index_from_string(letters) - 1


def _index_to_col(index: int) -> str:
    """Return the A1 column letters for a 0-based column ``index`` (1 -> ``"B"``)."""
    from openpyxl.utils import get_column_letter

    return get_column_letter(index + 1)


def _split_ref(ref: str) -> tuple[int, int]:
    """Split an A1 ``ref`` (``"B7"``) into 0-based ``(row_index, col_index)``.

    Raises:
        BeforeMismatchError: on a malformed reference.
    """
    from openpyxl.utils import coordinate_to_tuple

    try:
        row, col = coordinate_to_tuple(ref)
    except (ValueError, TypeError) as exc:
        raise BeforeMismatchError(f"invalid cell ref {ref!r}: {exc}") from exc
    return int(row) - 1, int(col) - 1


@dataclass
class _Row:
    """One modeled csv row: a stable rowId, ordered cell values, inserted flag."""

    row_id: int
    cells: list[str] = field(default_factory=list)
    inserted: bool = False


class CsvAdapter(DocumentAdapter):
    """Loads a .csv, applies v0.2 cell/row ops, renders an HTML redline overlay.

    csv has no native revisions; the journal is the source of truth and
    :meth:`render_tracked` projects it as a unified + side-by-side HTML redline.
    """

    def __init__(
        self,
        raw_bytes: bytes,
        *,
        sheet: str = "csv",
        author: str = DEFAULT_AUTHOR,
        date: str = DEFAULT_DATE,
    ) -> None:
        self._raw = raw_bytes
        self._author = author
        self._date = date
        self._sheet = sheet
        self._baseline_sha = sha256_hex(raw_bytes)
        self._rows: list[_Row] = []
        self._row_seq = 0
        self._baseline_rows: list[list[str]] = []
        self._deleted_rows: list[tuple[int, list[str]]] = []
        # Directly-edited cells recorded at apply-time, keyed by (row_id, col)
        # so the edit follows its row under inserts/deletes. value = (before, after).
        self._edits: dict[tuple[int, int], tuple[str, str]] = {}
        self._build_model(raw_bytes)

    # -- construction ---------------------------------------------------------

    @classmethod
    def load(
        cls,
        path: str,
        *,
        author: str = DEFAULT_AUTHOR,
        date: str = DEFAULT_DATE,
        **_: Any,
    ) -> "CsvAdapter":
        """Load a .csv from a sanitized path (extra kwargs are accepted+ignored).

        The logical sheet name defaults to the file's stem so natural-key node ids
        read ``"<stem>!<ref>"``.
        """
        resolved = safe_path(path, must_exist=True, allow_suffixes=(".csv",))
        raw = resolved.read_bytes()
        return cls(raw, sheet=resolved.stem, author=author, date=date)

    def _mint_row_id(self) -> int:
        self._row_seq += 1
        return self._row_seq

    def _build_model(self, raw: bytes) -> None:
        text = raw.decode("utf-8-sig")
        reader = csv.reader(io.StringIO(text))
        self._rows = []
        self._baseline_rows = []
        for record in reader:
            self._rows.append(_Row(row_id=self._mint_row_id(), cells=list(record)))
            self._baseline_rows.append(list(record))

    # -- DocumentAdapter contract --------------------------------------------

    def baseline_sha256(self) -> str:
        return self._baseline_sha

    def _cell_value(self, row: _Row, col_index: int) -> str:
        return row.cells[col_index] if 0 <= col_index < len(row.cells) else ""

    def to_model(self) -> Node:
        """Return the model tree: root -> one PARAGRAPH node per non-empty cell."""
        root = Node(node_id="root", node_kind=NodeKind.DOCUMENT, path="/csv")
        for r_index, row in enumerate(row for row in self._rows):
            for c_index, value in enumerate(row.cells):
                if value == "":
                    continue
                ref = f"{_index_to_col(c_index)}{r_index + 1}"
                node_id = f"{self._sheet}!{ref}"
                root.children.append(
                    Node(
                        node_id=node_id,
                        node_kind=NodeKind.PARAGRAPH,
                        path=f"/csv/{ref}",
                        value=value,
                        attrs={
                            "sheet": self._sheet,
                            "ref": ref,
                            "row_id": row.row_id,
                        },
                    )
                )
        return root

    def set_model(self, root: Node) -> None:
        """Reset adapter state to ``root`` (used by :meth:`Journal.replay`)."""
        self._rows = []
        self._row_seq = 0
        self._deleted_rows = []
        self._edits = {}
        grid: dict[int, dict[int, str]] = {}
        max_row = -1
        for node in root.children:
            if node.node_kind != NodeKind.PARAGRAPH:
                continue
            ref = str(node.attrs.get("ref", ""))
            sheet = str(node.attrs.get("sheet", ""))
            if sheet:
                self._sheet = sheet
            if not ref:
                continue
            r_index, c_index = _split_ref(ref)
            grid.setdefault(r_index, {})[c_index] = str(node.value or "")
            max_row = max(max_row, r_index)
        for r_index in range(max_row + 1):
            cols = grid.get(r_index, {})
            width = (max(cols) + 1) if cols else 0
            cells = [cols.get(c, "") for c in range(width)]
            self._rows.append(_Row(row_id=self._mint_row_id(), cells=cells))
        self._baseline_rows = [list(row.cells) for row in self._rows]

    def resolve(self, node_id: str) -> Node | None:
        return self.to_model().find(node_id)

    # -- apply ----------------------------------------------------------------

    def apply(self, op: Op) -> None:
        """Apply one v0.2 csv op (``cell.set`` / ``row.insert`` / ``row.delete``)."""
        if isinstance(op, CellSet):
            self._apply_cell_set(op)
        elif isinstance(op, RowInsert):
            self._apply_row_insert(op)
        elif isinstance(op, RowDelete):
            self._apply_row_delete(op)
        else:  # pragma: no cover - exhaustive over csv ops
            raise TypeError(
                f"unsupported op type {type(op).__name__} for csv "
                "(formula.set is not meaningful for csv)"
            )

    def _ensure_width(self, row: _Row, col_index: int) -> None:
        while len(row.cells) <= col_index:
            row.cells.append("")

    def _apply_cell_set(self, op: CellSet) -> None:
        r_index, c_index = _split_ref(op.ref)
        while len(self._rows) <= r_index:
            self._rows.append(_Row(row_id=self._mint_row_id()))
        row = self._rows[r_index]
        current = self._cell_value(row, c_index)
        if op.before != current:
            raise BeforeMismatchError(
                f"cell.set before {op.before!r} != current {current!r} at "
                f"{op.sheet}!{op.ref}"
            )
        self._ensure_width(row, c_index)
        row.cells[c_index] = op.after
        # Record the edit against the row's stable id so it follows the row even
        # if later inserts/deletes shift the row's position.
        self._edits[(row.row_id, c_index)] = (op.before, op.after)

    def _apply_row_insert(self, op: RowInsert) -> None:
        if op.at < 1:
            raise BeforeMismatchError(f"row.insert at must be >= 1 (got {op.at})")
        pos = min(op.at - 1, len(self._rows))
        self._rows.insert(pos, _Row(row_id=self._mint_row_id(), inserted=True))

    def _apply_row_delete(self, op: RowDelete) -> None:
        if op.at < 1 or op.at > len(self._rows):
            raise NodeNotFoundError(f"row.delete at {op.at} out of range")
        populated = [r for r in self._rows if any(c != "" for c in r.cells)]
        target = self._rows[op.at - 1]
        if len(populated) <= 1 and any(c != "" for c in target.cells):
            raise OversizedOpError(
                "split_required: this row.delete removes the file's only "
                "populated row; review it as a file-level change instead."
            )
        removed = self._rows.pop(op.at - 1)
        captured = list(removed.cells) or [str(v) for v in op.value]
        self._deleted_rows.append((op.at, captured))

    # -- render / save --------------------------------------------------------

    def _current_rows(self) -> list[list[str]]:
        return [list(row.cells) for row in self._rows]

    def _inserted_indices(self) -> set[int]:
        return {i for i, row in enumerate(self._rows) if row.inserted}

    def _cell_edits(self) -> list[CellEdit]:
        """Resolve the recorded ``cell.set`` edits to CURRENT (row,col) coords.

        Edits are tracked at apply-time by the cell's stable ``row_id`` (so they
        follow the row under inserts/deletes); here we map each still-present row
        back to its current index. Edits on rows that were later deleted drop out.
        Only directly-edited cells are reported — never positional shifts.
        """
        index_by_row_id = {row.row_id: i for i, row in enumerate(self._rows)}
        edits: list[CellEdit] = []
        for (row_id, c_index), (before, after) in self._edits.items():
            r_index = index_by_row_id.get(row_id)
            if r_index is None:
                continue  # the edited row was subsequently deleted
            edits.append(CellEdit(row=r_index, col=c_index, before=before, after=after))
        return edits

    def render_tracked(self) -> bytes:
        """Return the unified + side-by-side HTML redline bytes (the review surface).

        csv has no native track-changes, so this projection of the journal *is*
        the review surface. The clean csv is available via :meth:`clean_csv_bytes`.
        """
        html_doc = build_redline_html(
            self._baseline_rows,
            self._current_rows(),
            self._cell_edits(),
            self._inserted_indices(),
            list(self._deleted_rows),
        )
        return html_doc.encode("utf-8")

    def clean_csv_bytes(self) -> bytes:
        """Return the CLEAN shippable ``.csv`` bytes (no redline markup)."""
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        for row in self._rows:
            writer.writerow(row.cells)
        return buffer.getvalue().encode("utf-8")

    def save(self, out_path: str) -> None:
        """Save the HTML redline overlay next to a sanitized ``out_path``.

        ``out_path`` keeps the ``.csv`` extension (so the CLI's same-extension rule
        holds); the redline HTML is written to a sibling ``<name>.review.html`` and
        the clean csv is written to ``out_path`` itself.
        """
        resolved = safe_path(out_path, allow_suffixes=(".csv",))
        resolved.parent.mkdir(parents=True, exist_ok=True)
        resolved.write_bytes(self.clean_csv_bytes())
        review = resolved.with_suffix(".review.html")
        review.write_bytes(self.render_tracked())

    # -- accessors ------------------------------------------------------------

    def node_id_map(self) -> dict[str, str]:
        """csv addresses by natural key, so there is no carrier map."""
        return {}
