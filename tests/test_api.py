"""HTTP/REST API tests for ``changex-api`` (the FastAPI wrapper over the spine).

Two things are asserted:

1. The end-to-end happy path over the REST surface — open -> outline -> edit ->
   save -> report — drives ``examples/sample.docx`` through a real tracked-editing
   round trip via :class:`fastapi.testclient.TestClient`, with no network and no
   running server. The edit reuses a word discovered from the live outline so the
   ``before`` substring genuinely matches the node's current text (the same
   boundary the adapter enforces).

2. ``/openapi.json`` is valid and lists every endpoint — this is the exact schema
   a ChatGPT custom GPT Action imports, so a regression here breaks every
   Action/function-calling consumer.

The whole module is skipped (not failed) when FastAPI / its TestClient transport
is unavailable, mirroring how the docx-dependent suites ``importorskip`` docx.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

# FastAPI (and httpx, which TestClient needs) are optional at the repo level.
pytest.importorskip("fastapi", reason="fastapi is required for the REST API tests")
pytest.importorskip("httpx", reason="httpx is required for the FastAPI TestClient")
pytest.importorskip("docx", reason="python-docx is required for docx round-trip tests")

from fastapi.testclient import TestClient  # noqa: E402

from changex_api.app import create_app  # noqa: E402

_EXAMPLE_DOCX = Path(__file__).resolve().parent.parent / "examples" / "sample.docx"


@pytest.fixture()
def client() -> TestClient:
    """A TestClient over a FRESH app instance (its own in-process session store)."""
    return TestClient(create_app())


@pytest.fixture()
def workdir_docx(tmp_path: Path) -> Path:
    """A copy of the committed sample.docx in this test's temp dir.

    Editing happens against the copy so the save output and the ``.changex``
    sidecar never touch the repo's ``examples/`` tree.
    """
    if not _EXAMPLE_DOCX.exists():
        pytest.skip(f"sample docx not found at {_EXAMPLE_DOCX}")
    dest = tmp_path / "sample.docx"
    shutil.copyfile(_EXAMPLE_DOCX, dest)
    return dest


# --------------------------------------------------------------------------- #
# (1) open -> outline -> edit -> save -> report happy path over REST.
# --------------------------------------------------------------------------- #
def test_open_edit_save_report_happy_path(client: TestClient, workdir_docx: Path) -> None:
    # open
    r = client.post(
        "/sessions",
        json={
            "path": str(workdir_docx),
            "agent_context": {"model": "test-model", "vendor": "test"},
        },
    )
    assert r.status_code == 200, r.text
    opened = r.json()
    handle = opened["handle"]
    assert handle and opened["session_id"] and opened["baseline_sha256"]
    assert opened["summary"]["paragraphs"] >= 1

    # outline -> pick a node and an exact word from its preview to edit.
    r = client.get(f"/sessions/{handle}/outline")
    assert r.status_code == 200, r.text
    outline = r.json()
    assert outline["total"] >= 1
    node, word = _first_editable(outline["nodes"])
    assert node is not None and word, "no editable word found in outline preview"

    # edit: a small, attributable replace_text on a single word.
    r = client.post(
        f"/sessions/{handle}/edit",
        json={
            "op": "replace_text",
            "node_id": node["node_id"],
            "before": word,
            "after": word.upper(),
            "rationale": "uppercase the first word for emphasis",
        },
    )
    assert r.status_code == 200, r.text
    edited = r.json()
    assert edited["op_id"] and isinstance(edited["seq"], int)
    assert edited["node_id"] == node["node_id"]

    # changes: the journaled op shows up, chain verified.
    r = client.get(f"/sessions/{handle}/changes")
    assert r.status_code == 200, r.text
    changes = r.json()
    assert changes["count"] == 1
    assert changes["verified"] is True

    # save: write the tracked .docx + report the sidecar path.
    out_path = workdir_docx.with_name("sample.tracked.docx")
    r = client.post(f"/sessions/{handle}/save", json={"out": str(out_path)})
    assert r.status_code == 200, r.text
    saved = r.json()
    assert saved["ops"] == 1
    assert saved["verified"] is True
    assert Path(saved["tracked_path"]).exists()
    assert Path(saved["changex_path"]).exists()

    # report: HTML redline of the one change (JSON form).
    r = client.post("/report", params={"handle": handle, "fmt": "html"})
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["format"] == "html"
    assert word.upper() in report["report"]

    # report: raw HTML form is served as text/html.
    r = client.post("/report", params={"handle": handle, "fmt": "html", "raw": True})
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/html")


def test_healthz(client: TestClient) -> None:
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "changex-api"


def test_unknown_handle_is_404(client: TestClient) -> None:
    r = client.get("/sessions/does-not-exist/outline")
    assert r.status_code == 404
    assert r.json()["detail"]["error"] == "unknown_handle"


def test_before_mismatch_is_422(client: TestClient, workdir_docx: Path) -> None:
    r = client.post("/sessions", json={"path": str(workdir_docx)})
    handle = r.json()["handle"]
    # Target the LONGEST node so a short bogus `before` trips the before-check, not
    # the >50%-rewrite (split_required) guard.
    node, _word = _first_editable(client.get(f"/sessions/{handle}/outline").json()["nodes"])
    assert node is not None
    r = client.post(
        f"/sessions/{handle}/edit",
        json={
            "op": "replace_text",
            "node_id": node["node_id"],
            "before": "zzznotpresentzzz",
            "after": "qqq",
        },
    )
    assert r.status_code == 422, r.text
    assert r.json()["detail"]["error"] == "before_mismatch"


# --------------------------------------------------------------------------- #
# (2) /openapi.json is valid and lists every endpoint.
# --------------------------------------------------------------------------- #
def test_openapi_is_valid_and_lists_endpoints(client: TestClient) -> None:
    r = client.get("/openapi.json")
    assert r.status_code == 200, r.text
    schema = r.json()

    # OpenAPI 3.1.x — required for ChatGPT custom GPT Actions.
    assert schema["openapi"].startswith("3.")
    assert schema["info"]["title"] == "ChangeX API"

    paths = schema["paths"]
    expected = {
        "/healthz": "get",
        "/sessions": "post",
        "/sessions/{handle}/outline": "get",
        "/sessions/{handle}/edit": "post",
        "/sessions/{handle}/save": "post",
        "/sessions/{handle}/changes": "get",
        "/open": "post",
        "/seal": "post",
        "/report": "post",
    }
    for path, method in expected.items():
        assert path in paths, f"missing path {path}"
        assert method in paths[path], f"missing {method.upper()} {path}"

    # Stable, clean operationIds are what Actions/function-calling key on.
    op_ids = {
        spec["operationId"]
        for methods in paths.values()
        for spec in methods.values()
        if "operationId" in spec
    }
    assert {"openTracked", "editSession", "saveSession", "renderReport"} <= op_ids


def _first_editable(nodes: list[dict]) -> tuple[dict | None, str]:
    """Return (longest_node, its_first_word) for a small, in-bounds replace_text.

    We pick the node with the LONGEST preview so a single-word replace stays well
    under the adapter's >50%-rewrite (``split_required``) guard, and use the
    preview's leading token — an exact substring of the node text — as the
    ``before`` value. That is exactly the minimal, attributable edit ChangeX is
    built for.
    """
    best: dict | None = None
    best_len = -1
    for node in nodes:
        preview = (node.get("preview") or "").strip()
        if not preview:
            continue
        if len(preview) > best_len:
            best, best_len = node, len(preview)
    if best is None:
        return None, ""
    word = (best.get("preview") or "").strip().split()[0]
    return best, word
