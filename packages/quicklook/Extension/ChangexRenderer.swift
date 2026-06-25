import AppKit

/// Builds the Quick Look preview as a native `NSAttributedString` (rendered by an in-process
/// `NSTextView`). We deliberately do NOT use WKWebView: a WKWebView inside the sandboxed
/// Quick Look host renders blank (its WebContent helper can't paint there). Native text always
/// renders, in both light and dark panels (semantic `NSColor`s adapt automatically).
///
/// ChangeX previews ONLY its own `.changex` journal → a redline (deleted = red strikethrough,
/// inserted = green) + the attributed agent, the same story `changex review` tells. The
/// extension declares just `dev.changex.journal`, so code/Markdown/etc. stay with their own
/// previewers (QLMarkdown, Syntax Highlight, …) — no conflicts. The plain-text fallback below
/// only fires if a non-journal somehow reaches us, so it shows content instead of a blank panel.
enum ChangexRenderer {
    static func attributed(for url: URL, data: Data) -> NSAttributedString {
        if url.pathExtension.lowercased() == "changex" || looksLikeChangex(data) {
            return changexAttributed(from: data)
        }
        return plainTextAttributed(from: data)
    }

    private static func plainTextAttributed(from data: Data) -> NSAttributedString {
        let text = String(data: data, encoding: .utf8)
            ?? String(data: data, encoding: .isoLatin1) ?? ""
        let para = NSMutableParagraphStyle()
        para.lineSpacing = 2
        return NSAttributedString(string: text, attributes: [
            .font: monoBody, .foregroundColor: NSColor.labelColor, .paragraphStyle: para,
        ])
    }

    // MARK: - fonts

    private static let body = NSFont.systemFont(ofSize: 13)
    private static let monoBody = NSFont.monospacedSystemFont(ofSize: 12, weight: .regular)
    private static let monoSmall = NSFont.monospacedSystemFont(ofSize: 11, weight: .regular)

    private static func looksLikeChangex(_ data: Data) -> Bool {
        guard let head = String(data: data.prefix(400), encoding: .utf8) else { return false }
        return head.contains("\"type\": \"header\"") || head.contains("\"changex_version\"")
            || head.contains("\"op_schema_version\"")
    }

    // MARK: - .changex redline

    private static func changexAttributed(from data: Data) -> NSAttributedString {
        let text = String(decoding: data, as: UTF8.self)
        let lines = text.split(separator: "\n").map(String.init)
            .filter { !$0.trimmingCharacters(in: .whitespaces).isEmpty }

        guard let first = lines.first, let hd = first.data(using: .utf8),
              let header = (try? JSONSerialization.jsonObject(with: hd)) as? [String: Any]
        else { return plainText("Not a readable .changex journal.") }

        let doc = header["doc"] as? [String: Any]
        let filename = doc?["filename"] as? String ?? "(document)"
        let format = doc?["format"] as? String ?? "?"

        let out = NSMutableAttributedString()
        out.append(run(filename + "\n", NSFont.boldSystemFont(ofSize: 17), .labelColor))

        let para = NSMutableParagraphStyle()
        para.paragraphSpacing = 7
        para.lineSpacing = 1.5

        let rows = NSMutableAttributedString()
        var count = 0
        for line in lines.dropFirst() {
            guard let d = line.data(using: .utf8),
                  let ev = (try? JSONSerialization.jsonObject(with: d)) as? [String: Any],
                  let op = ev["op"] as? [String: Any] else { continue }
            count += 1
            let kind = (op["kind"] as? String) ?? "?"
            let agent = ((ev["provenance"] as? [String: Any])?["agent"] as? String) ?? "—"
            let before = (op["before"] as? String) ?? ""
            let after = (op["after"] as? String) ?? ((op["text"] as? String) ?? "")

            let row = NSMutableAttributedString()
            row.append(run(kind + "  ", monoSmall, .secondaryLabelColor))
            if !before.isEmpty {
                row.append(NSAttributedString(string: before, attributes: [
                    .font: body, .foregroundColor: NSColor.systemRed,
                    .strikethroughStyle: NSUnderlineStyle.single.rawValue,
                    .backgroundColor: NSColor.systemRed.withAlphaComponent(0.14),
                ]))
                row.append(run(" ", body, .labelColor))
            }
            if !after.isEmpty {
                row.append(NSAttributedString(string: after, attributes: [
                    .font: body, .foregroundColor: NSColor.systemGreen,
                    .backgroundColor: NSColor.systemGreen.withAlphaComponent(0.16),
                ]))
            }
            if before.isEmpty && after.isEmpty {
                row.append(run(kind, body, .secondaryLabelColor))
            }
            row.append(run("   — " + agent + "\n", NSFont.systemFont(ofSize: 11), .tertiaryLabelColor))
            row.addAttribute(.paragraphStyle, value: para, range: NSRange(location: 0, length: row.length))
            rows.append(row)
        }

        let label = "\(format) · \(count) tracked change\(count == 1 ? "" : "s")\n\n"
        out.append(run(label, NSFont.systemFont(ofSize: 12), .secondaryLabelColor))
        out.append(rows.length > 0 ? rows : run("No changes recorded.", body, .secondaryLabelColor))
        return out
    }

    // MARK: - helpers

    private static func run(_ s: String, _ font: NSFont, _ color: NSColor) -> NSAttributedString {
        NSAttributedString(string: s, attributes: [.font: font, .foregroundColor: color])
    }

    private static func plainText(_ s: String) -> NSAttributedString {
        run(s, body, .secondaryLabelColor)
    }
}
