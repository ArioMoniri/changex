"""Shared pytest fixtures for the ChangeX M0 spine tests.

Everything here builds on the *public* ``changex_core`` API plus the repo's own
``scripts/make_sample_docx.py`` fixture generator. A real ``.docx`` is generated
once per test into a temp directory so the docx-adapter tests run against a true
Word file (with native ``w14:paraId``s).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType

import pytest

_REPO_ROOT = Path(__file__).resolve().parent.parent
_SCRIPTS = _REPO_ROOT / "scripts"


def _load_make_sample() -> ModuleType:
    """Import ``scripts/make_sample_docx.py`` as a module without a package."""
    path = _SCRIPTS / "make_sample_docx.py"
    spec = importlib.util.spec_from_file_location("changex_make_sample", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def make_sample() -> ModuleType:
    """The sample-docx generator module (skips the suite if docx is missing)."""
    pytest.importorskip("docx", reason="python-docx is required for docx fixtures")
    return _load_make_sample()


@pytest.fixture()
def sample_docx(tmp_path: Path, make_sample: ModuleType) -> Path:
    """A freshly generated sample ``.docx`` in this test's temp dir."""
    out = tmp_path / "sample.docx"
    return make_sample.write_sample(out)


@pytest.fixture()
def journal_path(tmp_path: Path) -> Path:
    """A path for a fresh ``.changex`` journal (file not yet created)."""
    return tmp_path / "session.changex"
