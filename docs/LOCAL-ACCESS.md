# 🔐 How ChangeX reaches your local files

**The model never touches your filesystem — the ChangeX MCP server does.**

When you run `claude mcp add changex -- uvx changex-mcp`, the `changex-mcp` server runs
**as a local process on your own Mac**, started by your desktop client (Claude Code,
Claude Desktop, Cursor, Cline, …) over stdio. So when the model calls a tool like
`open_tracked({ "path": "/Users/you/Downloads/Report.docx" })`, that call is executed
**locally**, by a process that *can* read the file. The model only sends tool calls — it
never needs filesystem access itself.

```
You ─prompt─▶  Model  ─tool call─▶  changex-mcp  ─reads/writes─▶  /Users/you/Report.docx
                       open_tracked   (runs on YOUR Mac)          (local, with provenance)
                       edit
                       save_tracked
```

## ✅ Works: local / desktop MCP clients

Claude **Code**, Claude **Desktop**, **Cursor**, **Cline**, **LM Studio** — the server runs
on your machine, so it reads and writes your local documents directly, with live provenance.
This is the intended way to let an AI edit a file on your computer.

```bash
claude mcp add changex -- uvx changex-mcp     # then just ask Claude to edit your .docx
```

## ❌ Doesn't work: web chat (claude.ai, ChatGPT in the browser)

A browser chat runs in the cloud. Even a "remote connector" runs on *a server*, not your
Mac — so it can't reach `/Users/you/…`. That's exactly why web Claude asked you to **upload**
the file. Two ways around it:

1. **Use the desktop app instead** (Claude Desktop / Claude Code) — recommended. Local MCP, done.
2. **Passive path** — let the web model edit an *uploaded copy*, download the result, and
   reconstruct the tracked changes locally:
   ```bash
   changex open  "Report.docx"     # snapshot BEFORE you upload
   #  …upload to the model, let it edit, download the edited file back over Report.docx…
   changex seal  "Report.docx"     # → Report.tracked.docx + the .changex journal
   ```
   Provenance is honestly **degraded** in this mode (who/why unknown — the edit happened
   off-machine), but you still get a faithful tracked record of *what* changed.

## 🌍 Advanced: remote MCP over a tunnel

Run `changex-mcp --http` on your Mac and expose it through an **authenticated** HTTPS tunnel
(e.g. Cloudflare Tunnel / ngrok), then point a claude.ai custom connector or the ChatGPT app
connector at the URL. Now the web model reaches *your* local server, which touches *your*
local files. Powerful, but security-sensitive — you're exposing a file-editing server, so
**always require the bearer token** (`CHANGEX_MCP_TOKEN`) and never bind publicly without it.
See [INTEGRATION.md](INTEGRATION.md).

---

### TL;DR
- **Want an AI to edit a file on your Mac?** Use **Claude Desktop or Claude Code** (or Cursor/
  Cline) and `claude mcp add changex -- uvx changex-mcp`. The local server does the file I/O.
- **Stuck in a browser chat?** It can't see local files — edit an uploaded copy, then
  `changex open` / `seal` locally to recover the tracked changes.
