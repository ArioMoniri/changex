import Foundation

/// Renders a `.changex` JSONL journal into a self-contained HTML redline for Quick Look.
///
/// The journal is one JSON object per line: a header (doc/session) then one op event per
/// line. We surface the document, a per-change redline (deleted/inserted text), and the
/// attributed agent — the same story `changex review` tells, with zero dependencies.
enum ChangexRenderer {
    static func html(from data: Data) -> String {
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
            rows += "<tr><td class=\"k\">\(esc(kind))</td><td>\(change)</td><td class=\"who\">\(esc(agent))</td></tr>"
        }

        let body = """
        <h1>\(esc(filename))</h1>
        <p class="meta">\(esc(format)) · \(count) tracked change\(count == 1 ? "" : "s")</p>
        <table>\(rows.isEmpty ? "<tr><td class=\"empty\">No changes recorded.</td></tr>" : rows)</table>
        """
        return wrap(body)
    }

    private static func esc(_ s: String) -> String {
        s.replacingOccurrences(of: "&", with: "&amp;")
            .replacingOccurrences(of: "<", with: "&lt;")
            .replacingOccurrences(of: ">", with: "&gt;")
    }

    private static func wrap(_ inner: String) -> String {
        """
        <!doctype html><html><head><meta charset="utf-8"><style>
        body{font:13px -apple-system,BlinkMacSystemFont,sans-serif;margin:16px;color:#1d1d1f}
        h1{font-size:17px;margin:0 0 2px;font-weight:600}
        .meta{color:#86868b;margin:0 0 14px}
        table{border-collapse:collapse;width:100%}
        td{border-top:1px solid #e5e5e7;padding:6px 8px;vertical-align:top;line-height:1.4}
        .k{font:11px ui-monospace,SFMono-Regular,monospace;color:#6e6e73;white-space:nowrap}
        .who{color:#86868b;white-space:nowrap;text-align:right}
        .empty{color:#86868b}
        ins{background:#d8f5e0;text-decoration:none;border-radius:3px;padding:0 2px}
        del{background:#ffe0e3;border-radius:3px;padding:0 2px}
        @media(prefers-color-scheme:dark){
          body{color:#f5f5f7;background:#1e1e1e}td{border-color:#3a3a3c}
          ins{background:#163a24;color:#d8f5e0}del{background:#3a1a1f;color:#ffd2d6}
        }
        </style></head><body>\(inner)</body></html>
        """
    }
}
