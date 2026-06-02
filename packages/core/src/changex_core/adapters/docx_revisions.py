"""OOXML revision-mapping: each v0.1 op -> exact ``w:*`` revision elements.

This is the renderer half of the docx adapter. It is intentionally separate from
model bookkeeping so the *exact* OOXML markup is auditable in one place (the spec
in ``docs/OOXML_REVISION_MAPPING.md`` mirrors this file).

Mapping (v0.1)
--------------
=================  ====================================================
op                 OOXML revision markup
=================  ====================================================
text.insert        ``w:ins > w:r > w:t``
text.delete        ``w:del > w:r > w:delText``   (delText, NOT t!)
text.replace       ``w:del``(delText) followed by ``w:ins``(t)
style.change       ``w:pPr > w:pPrChange`` carrying the prior ``w:pStyle``
node.insert(para)  new ``w:p`` whose runs are wrapped in ``w:ins`` and whose
                   paragraph mark carries an *inserted* pilcrow revision
                   (``w:rPr/w:ins`` inside ``w:pPr``)
node.delete(para)  runs wrapped in ``w:del`` + a *deleted* pilcrow revision
=================  ====================================================

Every ``w:ins``/``w:del``/``w:pPrChange``/pilcrow-revision element needs a unique
integer ``w:id``; duplicate ids corrupt the revision set and Word refuses to
accept cleanly. :class:`WidAllocator` is the single monotonic counter per save.
"""

from __future__ import annotations

from typing import Optional

from docx.oxml.ns import qn
from lxml import etree

W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


class WidAllocator:
    """One monotonic counter per save for unique ``w:id`` revision ids."""

    def __init__(self, start: int = 0) -> None:
        self._next = start

    def next_id(self) -> int:
        self._next += 1
        return self._next


def _make(tag: str) -> etree._Element:
    return etree.SubElement(etree.Element(qn("w:body")), qn(tag))


def _el(tag: str) -> etree._Element:
    return etree.Element(qn(tag))


def _ins_wrapper(
    author: str, date: str, wid: int
) -> etree._Element:
    """Return a ``<w:ins>`` element with author/date/id attributes set."""
    ins = _el("w:ins")
    ins.set(qn("w:id"), str(wid))
    ins.set(qn("w:author"), author)
    ins.set(qn("w:date"), date)
    return ins


def _del_wrapper(author: str, date: str, wid: int) -> etree._Element:
    """Return a ``<w:del>`` element with author/date/id attributes set."""
    dele = _el("w:del")
    dele.set(qn("w:id"), str(wid))
    dele.set(qn("w:author"), author)
    dele.set(qn("w:date"), date)
    return dele


def _run_with_text(text: str, *, deleted: bool, rpr: Optional[etree._Element] = None) -> etree._Element:
    """Build a ``<w:r>`` carrying ``text``.

    Deleted runs use ``<w:delText>`` (NOT ``<w:t>``) so Word renders and accepts
    them correctly; inserted/normal runs use ``<w:t>``. ``xml:space=preserve``
    keeps leading/trailing whitespace.
    """
    run = _el("w:r")
    if rpr is not None:
        run.append(rpr)
    text_tag = "w:delText" if deleted else "w:t"
    t = etree.SubElement(run, qn(text_tag))
    t.set(qn("xml:space"), "preserve")
    t.text = text
    return run


def make_inserted_run(
    text: str, author: str, date: str, alloc: WidAllocator
) -> etree._Element:
    """Return ``<w:ins><w:r><w:t>text</w:t></w:r></w:ins>`` for text.insert."""
    ins = _ins_wrapper(author, date, alloc.next_id())
    ins.append(_run_with_text(text, deleted=False))
    return ins


def make_deleted_run(
    text: str, author: str, date: str, alloc: WidAllocator
) -> etree._Element:
    """Return ``<w:del><w:r><w:delText>text</w:delText></w:r></w:del>``."""
    dele = _del_wrapper(author, date, alloc.next_id())
    dele.append(_run_with_text(text, deleted=True))
    return dele


def make_ppr_change(
    prev_style: str, author: str, date: str, alloc: WidAllocator
) -> etree._Element:
    """Return a ``<w:pPrChange>`` capturing the *previous* paragraph style.

    Placed inside the paragraph's ``<w:pPr>``. The nested ``<w:pPr>`` holds the
    prior properties (the old ``w:pStyle``) so accept keeps the new style and
    reject restores the old one.
    """
    ppr_change = _el("w:pPrChange")
    ppr_change.set(qn("w:id"), str(alloc.next_id()))
    ppr_change.set(qn("w:author"), author)
    ppr_change.set(qn("w:date"), date)
    prior = etree.SubElement(ppr_change, qn("w:pPr"))
    if prev_style:
        pstyle = etree.SubElement(prior, qn("w:pStyle"))
        pstyle.set(qn("w:val"), prev_style)
    return ppr_change


def make_inserted_pilcrow(
    author: str, date: str, alloc: WidAllocator
) -> etree._Element:
    """Return a ``<w:rPr><w:ins/></w:rPr>`` marking the paragraph mark inserted.

    Goes inside the new paragraph's ``<w:pPr>``. This is the classic
    "won't-accept" pitfall when omitted: a brand-new paragraph's pilcrow must be
    revision-marked or Word treats the split as un-tracked.
    """
    rpr = _el("w:rPr")
    ins = etree.SubElement(rpr, qn("w:ins"))
    ins.set(qn("w:id"), str(alloc.next_id()))
    ins.set(qn("w:author"), author)
    ins.set(qn("w:date"), date)
    return rpr


def make_deleted_pilcrow(
    author: str, date: str, alloc: WidAllocator
) -> etree._Element:
    """Return a ``<w:rPr><w:del/></w:rPr>`` marking the paragraph mark deleted."""
    rpr = _el("w:rPr")
    dele = etree.SubElement(rpr, qn("w:del"))
    dele.set(qn("w:id"), str(alloc.next_id()))
    dele.set(qn("w:author"), author)
    dele.set(qn("w:date"), date)
    return rpr


def collect_wids(root: etree._Element) -> list[int]:
    """Return all integer ``w:id`` values under ``root`` (for uniqueness tests)."""
    ids: list[int] = []
    for el in root.iter():
        val = el.get(qn("w:id"))
        if val is not None and el.tag in (
            qn("w:ins"),
            qn("w:del"),
            qn("w:pPrChange"),
        ):
            try:
                ids.append(int(val))
            except ValueError:
                continue
    return ids
