import Foundation

/// Renders a Quick Look preview as a self-contained HTML page.
///
/// Two modes, chosen by the file:
///   * `.changex` journals  → a redline (deleted/inserted text + attributed agent),
///     the same story `changex review` tells.
///   * any other file       → its source, syntax-highlighted with a bundled copy of
///     highlight.js (auto-detection, or the language hinted by the file extension).
///
/// Everything (CSS + JS) is inlined into the returned HTML so the WKWebView never
/// needs network or external resource access — important inside the App Sandbox.
enum ChangexRenderer {
    /// `hljs` is the contents of the bundled highlight.min.js (nil → no colouring).
    static func html(for url: URL, data: Data, hljs: String?) -> String {
        let ext = url.pathExtension.lowercased()
        if ext == "changex" || looksLikeChangex(data) {
            return changexHTML(from: data)
        }
        return codeHTML(from: data, ext: ext, hljs: hljs)
    }

    // MARK: - .changex redline -------------------------------------------------

    private static func looksLikeChangex(_ data: Data) -> Bool {
        guard let head = String(data: data.prefix(400), encoding: .utf8) else { return false }
        return head.contains("\"type\": \"header\"") || head.contains("\"changex_version\"")
            || head.contains("\"op_schema_version\"")
    }

    private static func changexHTML(from data: Data) -> String {
        let text = String(data: data, encoding: .utf8) ?? ""
        let lines = text
            .split(separator: "\n", omittingEmptySubsequences: true)
            .map(String.init)
            .filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }

        guard let first = lines.first,
              let headerData = first.data(using: .utf8),
              let header = (try? JSONSerialization.jsonObject(with: headerData)) as? [String: Any]
        else {
            return wrap("<p class=\"empty\">Not a readable .changex journal.</p>")
        }

        let doc = header["doc"] as? [String: Any]
        let filename = doc?["filename"] as? String ?? "(document)"
        let format = doc?["format"] as? String ?? "?"

        var rows = ""
        var count = 0
        for line in lines.dropFirst() {
            guard let d = line.data(using: .utf8),
                  let ev = (try? JSONSerialization.jsonObject(with: d)) as? [String: Any],
                  let op = ev["op"] as? [String: Any]
            else { continue }
            count += 1
            let kind = (op["kind"] as? String) ?? "?"
            let prov = ev["provenance"] as? [String: Any]
            let agent = (prov?["agent"] as? String) ?? "—"
            let before = (op["before"] as? String) ?? ""
            let after = (op["after"] as? String) ?? ((op["text"] as? String) ?? "")
            var change = ""
            if !before.isEmpty { change += "<del>\(esc(before))</del> " }
            if !after.isEmpty { change += "<ins>\(esc(after))</ins>" }
            if change.isEmpty { change = "<span class=\"k\">\(esc(kind))</span>" }
            rows += "<tr><td class=\"k\">\(esc(kind))</td><td>\(change)</td>"
                + "<td class=\"who\">\(esc(agent))</td></tr>"
        }

        let body = """
        <h1>\(esc(filename))</h1>
        <p class="meta">\(esc(format)) · \(count) tracked change\(count == 1 ? "" : "s")</p>
        <table>\(rows.isEmpty ? "<tr><td class=\"empty\">No changes recorded.</td></tr>" : rows)</table>
        """
        return wrap(body)
    }

    // MARK: - source code ------------------------------------------------------

    private static func codeHTML(from data: Data, ext: String, hljs: String?) -> String {
        let source = String(data: data, encoding: .utf8)
            ?? String(data: data, encoding: .isoLatin1)
            ?? ""
        let lang = language(for: ext)
        let cls = lang.map { " class=\"language-\($0)\"" } ?? ""

        // Inline highlight.js if we have it; otherwise show plain (still readable) source.
        let hl: String
        if let hljs, !hljs.isEmpty {
            hl = """
            <script>\(hljs)</script>
            <script>
            try { hljs.configure({ ignoreUnescapedHTML: true });
                  document.querySelectorAll('pre code').forEach(function(b){ hljs.highlightElement(b); });
            } catch (e) {}
            </script>
            """
        } else {
            hl = ""
        }

        let body = "<pre class=\"code\"><code\(cls)>\(esc(source))</code></pre>"
        return wrap(body, extraHead: hljsTheme, trailing: hl, wide: true)
    }

    /// File-extension → highlight.js language id. nil ⇒ let highlight.js auto-detect.
    private static func language(for ext: String) -> String? {
        let map: [String: String] = [
            "swift": "swift", "py": "python", "pyw": "python", "rb": "ruby", "js": "javascript",
            "mjs": "javascript", "cjs": "javascript", "jsx": "javascript", "ts": "typescript",
            "tsx": "typescript", "c": "c", "h": "c", "cc": "cpp", "cpp": "cpp", "cxx": "cpp",
            "hpp": "cpp", "hh": "cpp", "m": "objectivec", "mm": "objectivec", "java": "java",
            "kt": "kotlin", "kts": "kotlin", "go": "go", "rs": "rust", "php": "php",
            "pl": "perl", "pm": "perl", "sh": "bash", "bash": "bash", "zsh": "bash",
            "fish": "bash", "ps1": "powershell", "sql": "sql", "r": "r", "scala": "scala",
            "lua": "lua", "dart": "dart", "ex": "elixir", "exs": "elixir", "erl": "erlang",
            "hs": "haskell", "clj": "clojure", "cs": "csharp", "fs": "fsharp", "vb": "vbnet",
            "json": "json", "jsonl": "json", "yaml": "yaml", "yml": "yaml", "toml": "ini",
            "ini": "ini", "cfg": "ini", "conf": "ini", "xml": "xml", "html": "xml",
            "htm": "xml", "svg": "xml", "plist": "xml", "css": "css", "scss": "scss",
            "less": "less", "md": "markdown", "markdown": "markdown", "tex": "latex",
            "dockerfile": "dockerfile", "makefile": "makefile", "mk": "makefile",
            "gradle": "gradle", "groovy": "groovy", "diff": "diff", "patch": "diff",
            "graphql": "graphql", "proto": "protobuf", "vue": "xml", "tf": "terraform",
        ]
        return map[ext]
    }

    // MARK: - helpers ----------------------------------------------------------

    private static func esc(_ s: String) -> String {
        s.replacingOccurrences(of: "&", with: "&amp;")
            .replacingOccurrences(of: "<", with: "&lt;")
            .replacingOccurrences(of: ">", with: "&gt;")
    }

    /// Page chrome. A SOLID background is always painted (in both colour schemes) so the
    /// preview is never dark-text-on-dark — the bug that made it look blank.
    private static func wrap(_ inner: String, extraHead: String = "", trailing: String = "",
                             wide: Bool = false) -> String {
        """
        <!doctype html><html><head><meta charset="utf-8">
        <meta name="color-scheme" content="light dark">
        <style>
        :root{color-scheme:light dark}
        html,body{margin:0}
        body{font:13px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;
             padding:\(wide ? "0" : "16px");color:#1d1d1f;background:#ffffff}
        h1{font-size:17px;margin:0 0 2px;font-weight:600}
        .meta{color:#86868b;margin:0 0 14px}
        table{border-collapse:collapse;width:100%}
        td{border-top:1px solid #e5e5e7;padding:6px 8px;vertical-align:top;line-height:1.4}
        .k{font:11px ui-monospace,SFMono-Regular,Menlo,monospace;color:#6e6e73;white-space:nowrap}
        .who{color:#86868b;white-space:nowrap;text-align:right}
        .empty{color:#86868b}
        ins{background:#d8f5e0;text-decoration:none;border-radius:3px;padding:0 2px}
        del{background:#ffe0e3;border-radius:3px;padding:0 2px}
        pre.code{margin:0;padding:14px 16px;overflow:auto;
                 font:12px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;line-height:1.5;
                 -webkit-text-size-adjust:100%;tab-size:4}
        pre.code code{white-space:pre}
        @media(prefers-color-scheme:dark){
          body{color:#f5f5f7;background:#1e1e1e}
          td{border-color:#3a3a3c}.meta,.who,.k,.empty{color:#9a9a9e}
          ins{background:#163a24;color:#d8f5e0}del{background:#3a1a1f;color:#ffd2d6}
        }
        \(extraHead)
        </style></head><body>\(inner)\(trailing)</body></html>
        """
    }

    /// A compact highlight.js theme (GitHub-ish) for both light and dark schemes.
    private static let hljsTheme = """
    .hljs{display:block}
    .hljs-comment,.hljs-quote{color:#6e7781;font-style:italic}
    .hljs-keyword,.hljs-selector-tag,.hljs-literal,.hljs-doctag{color:#cf222e}
    .hljs-type,.hljs-class .hljs-title,.hljs-title.class_{color:#953800}
    .hljs-string,.hljs-meta .hljs-string,.hljs-regexp,.hljs-addition{color:#0a3069}
    .hljs-number,.hljs-symbol,.hljs-bullet{color:#0550ae}
    .hljs-title,.hljs-title.function_,.hljs-section,.hljs-name{color:#8250df}
    .hljs-attr,.hljs-attribute,.hljs-variable,.hljs-template-variable{color:#0550ae}
    .hljs-built_in,.hljs-builtin-name{color:#0550ae}
    .hljs-meta,.hljs-tag{color:#116329}
    .hljs-deletion{color:#82071e;background:#ffebe9}
    .hljs-emphasis{font-style:italic}.hljs-strong{font-weight:600}
    @media(prefers-color-scheme:dark){
      .hljs-comment,.hljs-quote{color:#8b949e}
      .hljs-keyword,.hljs-selector-tag,.hljs-literal,.hljs-doctag{color:#ff7b72}
      .hljs-type,.hljs-class .hljs-title,.hljs-title.class_{color:#ffa657}
      .hljs-string,.hljs-meta .hljs-string,.hljs-regexp,.hljs-addition{color:#a5d6ff}
      .hljs-number,.hljs-symbol,.hljs-bullet{color:#79c0ff}
      .hljs-title,.hljs-title.function_,.hljs-section,.hljs-name{color:#d2a8ff}
      .hljs-attr,.hljs-attribute,.hljs-variable,.hljs-template-variable{color:#79c0ff}
      .hljs-built_in,.hljs-builtin-name{color:#79c0ff}
      .hljs-meta,.hljs-tag{color:#7ee787}
      .hljs-deletion{color:#ffdcd7;background:#67060c}
    }
    """
}
