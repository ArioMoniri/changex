# 🛠️ Make Claude actually edit your local files

If you asked Claude *"open /Users/you/Report.docx with changex…"* and it replied
**"I can't reach that file, please upload it"** — that means the **changex MCP server
isn't connected yet**, so Claude has no `changex` tools and no way to touch local files.
Once it's connected, the local server reads/writes your files and Claude just drives it.

> ⚠️ This works in **Claude Desktop** and **Claude Code** (they run the server *on your
> Mac*). It does **not** work in **claude.ai in a browser** — a web tab can't see local
> files at all. See [LOCAL-ACCESS.md](LOCAL-ACCESS.md).

---

## 0. One-time prerequisite

You already have `changex` installed. Find the server's absolute path (GUI apps don't
inherit your shell `PATH`, so we use the full path):

```bash
which changex-mcp
# e.g. /opt/homebrew/bin/changex-mcp   (copy whatever it prints)
```

Sanity-check it runs (it starts a silent stdio server; press **Ctrl-C** to stop):

```bash
changex-mcp        # no output + no error = good. Ctrl-C to exit.
```

---

## A. Claude Code (terminal `claude`) — easiest

```bash
claude mcp add changex -- changex-mcp
claude mcp list                 # should show: changex  ✓ connected
```

Then in a session:

> *Use changex to open "/Users/ario/Downloads/SCM Case Report v13 copy.docx", tighten the
> intro and fix the heading, and save tracked changes.*

(If `claude mcp list` shows it not connected, use the absolute path:
`claude mcp add changex -- /opt/homebrew/bin/changex-mcp`.)

## B. Claude Desktop (the app)

1. Open the config file (create it if missing):
   `~/Library/Application Support/Claude/claude_desktop_config.json`
2. Put this in it — **use the absolute path from `which changex-mcp`**:

   ```json
   {
     "mcpServers": {
       "changex": {
         "command": "/opt/homebrew/bin/changex-mcp"
       }
     }
   }
   ```
3. **Fully quit and reopen Claude Desktop** (⌘Q — not just close the window).
4. You should see a 🔨 **tools** icon in the message box. Click it — `open_tracked`,
   `edit`, `save_tracked`, etc. should be listed.

Then ask the same thing as above.

---

## ✅ Verify it's actually connected

Ask Claude: **"What changex tools do you have?"** — it should list `open_tracked`,
`get_outline`, `edit`, `save_tracked`, `get_changes`, `render_review` (and `accept`/`reject`).
If it lists them, you're set. If it still says "upload the file," the server isn't
connected — recheck the absolute path and that you fully restarted the app.

## 🧩 Troubleshooting

| Symptom | Fix |
|---|---|
| "I can't access that file / upload it" | Server not connected — verify with the tools list above; use the **absolute** `changex-mcp` path; fully restart Claude. |
| `command not found: changex-mcp` | `pip install -U changex` (or `uv tool install changex`); re-run `which changex-mcp`. |
| Tools icon missing in Desktop | JSON typo (validate the file), or didn't ⌘Q-restart. |
| Want zero-PATH-hassle | Use `uvx`: set `"command": "uvx"`, `"args": ["changex-mcp@latest"]` (needs `uv` installed and on the app's PATH). |
| Using **claude.ai in a browser** | Can't reach local files — use Claude **Desktop/Code**, or the `changex open`/`seal` path on a downloaded copy. |
