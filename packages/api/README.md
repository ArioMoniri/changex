# changex-api

A thin HTTP/REST API over the [ChangeX](https://github.com/ArioMoniri/changex)
core spine, so **any** app or model can drive provenance-first tracked editing of
Word documents over plain HTTP — a local/offline LLM with no function-calling, a
`curl` script, or a **ChatGPT custom GPT Action** that imports the
auto-generated OpenAPI schema.

It wraps `changex-core` and reuses the exact MCP tool semantics
(`changex-mcp`): an `op` discriminator selects one small intent, the exact
`before` substring is always carried so blind overwrites are refused, and an
oversized op is rejected so the model splits the change.

## Run

```bash
# install (workspace) and launch on 127.0.0.1:8000
uv sync
changex-api                     # or: python -m changex_api
# custom bind / port:
changex-api --host 0.0.0.0 --port 9000   # non-local host REQUIRES a token:
CHANGEX_API_TOKEN=secret changex-api --host 0.0.0.0
```

Bind is `127.0.0.1` by default. A non-local host is **refused** unless
`CHANGEX_API_TOKEN` is set; when it is, every non-`/healthz` route requires
`Authorization: Bearer <token>`.

## Endpoints

| Method & path | Purpose |
|---|---|
| `POST /sessions` | Open a `.docx` for tracked editing (returns a `handle`). |
| `GET  /sessions/{handle}/outline` | Bounded, paginated paragraph outline (discover `node_id`s). |
| `POST /sessions/{handle}/edit` | One small, intent-named tracked edit. |
| `POST /sessions/{handle}/save` | Write the native-revisions `.docx` + `.changex` journal. |
| `GET  /sessions/{handle}/changes` | The structured provenance journal. |
| `POST /open` | Passive (no-tool-calling) capture: snapshot a docx. |
| `POST /seal` | Diff the edited docx vs the baseline; append passive ops. |
| `POST /report` | Render an HTML/markdown redline (by `handle` or `.changex` path). |
| `GET  /healthz` | Liveness probe (never requires auth). |

## OpenAPI / function-calling schemas

FastAPI serves the schema at **`/openapi.json`** — that file IS the ChatGPT
custom GPT Action schema; point a GPT's Action import at it. Static copies plus
OpenAI/Gemini function-calling schemas live in the repo's `integrations/`:

- `integrations/openapi.json` — the dumped OpenAPI 3.1 schema (ChatGPT Actions).
- `integrations/openai-functions.json` — OpenAI `tools` format.
- `integrations/gemini-functions.json` — Gemini `functionDeclarations` format.
