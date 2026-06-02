"""Journal-aware save: replay the NON-reverted journal into a fresh adapter.

The correctness bug this closes: applying ops directly to a live adapter and then
calling ``adapter.save`` bakes *every* applied op — including ones later rejected
via :meth:`Journal.revert` — into the tracked ``.docx``. The audit trail would
say an op was reverted while the saved document still carried its revision.

The fix is to make the saved document a pure projection of the journal's
**active** (non-reverted) events: load the baseline docx into a fresh adapter,
:meth:`Journal.replay` only the active events onto it, then render + save. A
reverted op's revision is therefore genuinely absent from the output file.
"""

from __future__ import annotations

from typing import Optional

from changex_core.adapters.docx_adapter import DEFAULT_AUTHOR, DocxAdapter
from changex_core.journal.journal import Journal
from changex_core.paths import safe_path


def save_active(
    journal: Journal,
    baseline_docx: str,
    out_path: str,
    *,
    author: str = DEFAULT_AUTHOR,
) -> int:
    """Save a tracked ``.docx`` containing only the journal's active events.

    Loads ``baseline_docx`` fresh (its model is the replay baseline), replays the
    journal's non-reverted events onto a clean adapter, and writes the rendered
    tracked document to ``out_path``. Returns the number of active events applied.

    Reverted ops are skipped by :meth:`Journal.replay` (it walks
    ``active_events``), so their revisions never reach the saved file.
    """
    base_path = safe_path(baseline_docx, must_exist=True, allow_suffixes=(".docx",))
    out = safe_path(out_path, allow_suffixes=(".docx",))

    adapter = DocxAdapter.load(str(base_path), author=author)
    baseline_model = adapter.to_model()
    journal.replay(adapter, baseline_model)
    adapter.save(str(out))
    return len(journal.active_events())


def save_active_from_path(
    changex_path: str,
    baseline_docx: str,
    out_path: str,
    *,
    author: str = DEFAULT_AUTHOR,
) -> int:
    """Open the journal at ``changex_path`` and :func:`save_active`."""
    resolved = safe_path(changex_path, must_exist=True, allow_suffixes=(".changex", ".jsonl"))
    journal = Journal.open(str(resolved))
    return save_active(journal, baseline_docx, out_path, author=author)


__all__ = ["save_active", "save_active_from_path"]
