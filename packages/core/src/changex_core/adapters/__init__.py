"""Document adapters: the contract, the docx implementation, and the registry.

The :class:`~changex_core.adapters.base.DocumentAdapter` ABC is the anti-drift
contract every format adapter implements. This package also owns the **format
registry + factory** (:func:`load_adapter`) that resolves a file path to the
adapter that handles its extension.

Lazy import is load-bearing
---------------------------
The registry maps an extension to a ``"module:ClassName"`` target string and
imports the module **only when that format is actually loaded**. Concretely the
xlsx/csv/pptx adapter modules are created by phase-2 agents and may not exist (or
may pull heavy third-party deps like ``openpyxl`` / ``python-pptx``) when this
package is imported. Importing them eagerly here would (a) crash ``import
changex_core`` before phase-2 lands and (b) force every consumer to install every
format's dependencies. So this module **must not** import the adapter
implementations at top level — only ``base`` and the already-shipping
``docx_adapter`` are imported eagerly.
"""

from __future__ import annotations

from typing import Callable

from changex_core.adapters.base import (
    AdapterError,
    BeforeMismatchError,
    DocumentAdapter,
    NodeNotFoundError,
    OversizedOpError,
    UnsupportedFormatError,
)
from changex_core.adapters.docx_adapter import DocxAdapter
from changex_core.paths import safe_path

# --------------------------------------------------------------------------- #
# Format registry.
#
# Maps a lowercased file extension to a ``"<module>:<ClassName>"`` target. The
# class is resolved by a LAZY import (see ``_resolve``) so the adapter module is
# only imported when a file of that format is loaded — phase-2 modules
# (xlsx_adapter, csv_adapter, pptx_adapter) therefore need not exist at import
# time, and their third-party deps stay opt-in.
# --------------------------------------------------------------------------- #
_REGISTRY: dict[str, str] = {
    ".docx": "changex_core.adapters.docx_adapter:DocxAdapter",
    ".xlsx": "changex_core.adapters.xlsx_adapter:XlsxAdapter",
    ".csv": "changex_core.adapters.csv_adapter:CsvAdapter",
    ".pptx": "changex_core.adapters.pptx_adapter:PptxAdapter",
}

# The suffixes ``load_adapter`` will accept (used as the ``allow_suffixes`` guard
# at the path boundary so an unknown extension is rejected before any import).
SUPPORTED_SUFFIXES: tuple[str, ...] = tuple(_REGISTRY)


def supported_suffixes() -> tuple[str, ...]:
    """Return the file extensions the registry knows how to load."""
    return SUPPORTED_SUFFIXES


def _resolve(target: str) -> type[DocumentAdapter]:
    """Lazily import ``"module:ClassName"`` and return the adapter class.

    Raises:
        UnsupportedFormatError: if the module/class cannot be imported (e.g. a
            phase-2 adapter that has not been created yet, or its third-party
            dependency is missing). The original cause is chained for debugging.
    """
    import importlib

    module_name, _, class_name = target.partition(":")
    try:
        module = importlib.import_module(module_name)
        cls = getattr(module, class_name)
    except (ImportError, AttributeError) as exc:  # adapter not yet implemented
        raise UnsupportedFormatError(
            f"adapter {target!r} is not available: {exc}"
        ) from exc
    if not (isinstance(cls, type) and issubclass(cls, DocumentAdapter)):
        raise UnsupportedFormatError(
            f"{target!r} does not resolve to a DocumentAdapter subclass"
        )
    return cls


def adapter_class_for(path: str) -> type[DocumentAdapter]:
    """Return the adapter **class** registered for ``path``'s extension.

    The path is sanitized (suffix-guarded against :data:`SUPPORTED_SUFFIXES`) and
    the matching adapter class is lazily imported. The file need not exist — this
    is a pure type lookup, used by callers that want to construct the adapter
    themselves. Use :func:`load_adapter` to also load the document.

    Raises:
        UnsupportedFormatError: if the extension is not registered or the adapter
            module/class cannot be imported.
        UnsafePathError: if the path fails sanitization.
    """
    resolved = safe_path(path, allow_suffixes=SUPPORTED_SUFFIXES)
    suffix = resolved.suffix.lower()
    target = _REGISTRY.get(suffix)
    if target is None:  # pragma: no cover - safe_path already guards the suffix
        raise UnsupportedFormatError(
            f"no adapter registered for {suffix!r}; supported: {SUPPORTED_SUFFIXES}"
        )
    return _resolve(target)


def load_adapter(path: str, **kwargs: object) -> DocumentAdapter:
    """Load ``path`` with the adapter registered for its file extension.

    This is the format-aware entry point the CLI and MCP server use instead of
    hard-coding :class:`DocxAdapter`. It dispatches by **extension** (``.docx`` ->
    :class:`DocxAdapter`, ``.xlsx`` -> ``XlsxAdapter``, ``.csv`` -> ``CsvAdapter``,
    ``.pptx`` -> ``PptxAdapter``), lazily importing the adapter module so unused
    formats never pull their third-party deps.

    ``path`` is sanitized (must exist, suffix-guarded). Extra ``kwargs`` (e.g.
    ``author=`` / ``date=`` for docx) are forwarded to the adapter's ``load``
    classmethod; adapters should accept the kwargs they understand.

    Args:
        path: The document to load. Extension selects the adapter.
        **kwargs: Forwarded to ``<Adapter>.load`` (adapter-specific).

    Returns:
        A loaded :class:`DocumentAdapter` for the file.

    Raises:
        UnsupportedFormatError: if the extension is not registered or the adapter
            is not yet available.
        UnsafePathError: if the path fails sanitization or does not exist.
    """
    resolved = safe_path(path, must_exist=True, allow_suffixes=SUPPORTED_SUFFIXES)
    cls = adapter_class_for(str(resolved))
    loader: Callable[..., DocumentAdapter] = cls.load  # type: ignore[assignment]
    return loader(str(resolved), **kwargs)


__all__ = [
    # contract + errors
    "DocumentAdapter",
    "AdapterError",
    "BeforeMismatchError",
    "OversizedOpError",
    "NodeNotFoundError",
    "UnsupportedFormatError",
    # docx implementation (shipping)
    "DocxAdapter",
    # registry / factory
    "load_adapter",
    "adapter_class_for",
    "supported_suffixes",
    "SUPPORTED_SUFFIXES",
]
