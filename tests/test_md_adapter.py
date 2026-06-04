"""MdAdapter op tests against a real generated ``.md`` (block granularity).

These cover, via the public ``changex_core`` API + the registry where wired:

* a markdown file modeled as a sequence of blocks split on blank lines, each
  with a stable positional node_id minted at load (``md:00001`` ...);
* ``text.replace`` / ``text.insert`` apply at BLOCK granularity;
* the ``before``-match guard refuses an op whose ``before`` is absent
  (raises :class:`BeforeMismatchError`) and unknown ids raise
  :class:`NodeNotFoundError`;
* ``render_tracked`` returns an inline ``<ins>`` / ``<del>`` HTML redline (the
  ONLY review surface — markdown has no native track-changes) and the clean md
  is shippable plain text.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from changex_core.adapters.base import BeforeMismatchError, NodeNotFoundError
from changex_core.adapters.md_adapter import MdAdapter
from changex_core.ops.vocabulary import TextInsert, TextReplace


# --------------------------------------------------------------------------- #
# fixtures / helpers
# --------------------------------------------------------------------------- #
@pytest.fixture()
def sample_md(tmp_path: Path) -> Path:
    """A small markdown file: a heading, a paragraph, and a list."""
    out = tmp_path / "doc.md"
    out.write_text(
        "# Title\n"
        "\n"
        "The quick brown fox jumps over the lazy dog.\n"
        "\n"
        "- first item\n"
        "- second item\n",
        encoding="utf-8",
    )
    return out


# --------------------------------------------------------------------------- #
# Addressing: positional minted node_ids; blocks keep their raw markers
# --------------------------------------------------------------------------- #
def test_blocks_split_on_blank_lines_with_stable_ids(sample_md: Path) -> None:
    adapter = MdAdapter.load(str(sample_md))
    assert isinstance(adapter, MdAdapter)
    model = adapter.to_model()
    blocks = model.child_paragraphs()
    assert [b.node_id for b in blocks] == ["md:00001", "md:00002", "md:00003"]
    # the heading block keeps its ``#`` marker; the list block keeps both bullets
    assert blocks[0].value == "# Title"
    assert blocks[2].value == "- first item\n- second item"


def test_resolve_returns_block_by_id(sample_md: Path) -> None:
    adapter = MdAdapter.load(str(sample_md))
    node = adapter.resolve("md:00002")
    assert node is not None and node.value.startswith("The quick brown fox")
    assert adapter.resolve("md:99999") is None


# --------------------------------------------------------------------------- #
# v0.2 op application at block granularity
# --------------------------------------------------------------------------- #
def test_text_replace_and_insert_apply_at_block(sample_md: Path) -> None:
    adapter = MdAdapter.load(str(sample_md))
    adapter.apply(TextReplace(node_id="md:00002", before="quick", after="slow"))
    adapter.apply(
        TextInsert(node_id="md:00002", before_anchor="dog", text=" indeed")
    )
    value = adapter.to_model().find("md:00002").value
    assert "slow brown fox" in value
    assert "dog indeed" in value


# --------------------------------------------------------------------------- #
# before-guard: mismatch is refused; unknown id is refused
# --------------------------------------------------------------------------- #
def test_before_guard_raises_on_mismatch(sample_md: Path) -> None:
    adapter = MdAdapter.load(str(sample_md))
    with pytest.raises(BeforeMismatchError):
        adapter.apply(
            TextReplace(node_id="md:00002", before="NOT PRESENT", after="x")
        )


def test_unknown_node_id_raises(sample_md: Path) -> None:
    adapter = MdAdapter.load(str(sample_md))
    with pytest.raises(NodeNotFoundError):
        adapter.apply(TextReplace(node_id="md:99999", before="x", after="y"))


# --------------------------------------------------------------------------- #
# Overlay: HTML redline is the (only) review surface; clean md is shippable
# --------------------------------------------------------------------------- #
def test_render_tracked_contains_ins_and_del(sample_md: Path) -> None:
    adapter = MdAdapter.load(str(sample_md))
    adapter.apply(TextReplace(node_id="md:00002", before="quick", after="slow"))
    adapter.apply(
        TextInsert(node_id="md:00002", before_anchor="dog", text=" indeed")
    )
    html = adapter.render_tracked().decode("utf-8")
    assert "<ins>" in html and "<del>" in html
    assert "<del>quick</del>" in html and "<ins>slow</ins>" in html
    # the honesty note is present (markdown has no native track-changes)
    assert "no native track-changes" in html


def test_clean_md_is_plain_shippable_output(sample_md: Path) -> None:
    adapter = MdAdapter.load(str(sample_md))
    adapter.apply(TextReplace(node_id="md:00002", before="quick", after="slow"))
    clean = adapter.clean_md_bytes().decode("utf-8")
    assert "slow brown fox" in clean
    assert "quick" not in clean
    assert "<ins>" not in clean and "<del>" not in clean  # no markup in the md
