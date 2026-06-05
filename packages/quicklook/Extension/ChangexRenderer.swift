import AppKit

/// Builds the Quick Look preview as a native `NSAttributedString` (rendered by an in-process
/// `NSTextView`). We deliberately do NOT use WKWebView: a WKWebView inside the sandboxed
/// Quick Look host renders blank (its WebContent helper can't paint there). Native text always
/// renders, in both light and dark panels (semantic `NSColor`s adapt automatically).
///
/// Two modes, chosen by the file:
///   * `.changex` journal → a redline (deleted = red strikethrough, inserted = green) + the
///     attributed agent, the same story `changex review` tells;
///   * any other file → its source, syntax-highlighted with a small language-agnostic tokenizer.
enum ChangexRenderer {
    static func attributed(for url: URL, data: Data) -> NSAttributedString {
        let ext = url.pathExtension.lowercased()
        if ext == "changex" || looksLikeChangex(data) {
            return changexAttributed(from: data)
        }
        return codeAttributed(from: data)
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

    // MARK: - source code (language-agnostic highlighter)

    private static let keywords: Set<String> = [
        "abstract", "and", "as", "assert", "async", "await", "break", "case", "catch", "class",
        "const", "continue", "def", "default", "del", "do", "elif", "else", "end", "enum",
        "except", "export", "extends", "extension", "false", "final", "finally", "fn", "for",
        "from", "func", "function", "global", "go", "guard", "if", "impl", "import", "in",
        "init", "instanceof", "interface", "is", "lambda", "let", "match", "mod", "module",
        "mut", "new", "nil", "none", "not", "null", "or", "override", "package", "pass",
        "private", "protected", "protocol", "pub", "public", "raise", "return", "self",
        "static", "struct", "super", "switch", "this", "throw", "throws", "trait", "true",
        "try", "type", "typedef", "typeof", "union", "unsafe", "use", "var", "void", "where",
        "while", "with", "yield",
    ]

    private static func codeAttributed(from data: Data) -> NSAttributedString {
        let src = String(data: data, encoding: .utf8)
            ?? String(data: data, encoding: .isoLatin1) ?? ""
        let out = NSMutableAttributedString()
        let chars = Array(src)
        let n = chars.count
        var i = 0

        let commentColor = NSColor.systemGray
        let stringColor = NSColor.systemRed
        let numberColor = NSColor.systemTeal
        let keywordColor = NSColor.systemPink
        let plainColor = NSColor.labelColor

        func emit(_ s: String, _ color: NSColor) {
            out.append(NSAttributedString(string: s, attributes: [.font: monoBody, .foregroundColor: color]))
        }

        while i < n {
            let c = chars[i]
            // line comment: //  #  --
            if (c == "/" && i + 1 < n && chars[i + 1] == "/")
                || c == "#"
                || (c == "-" && i + 1 < n && chars[i + 1] == "-") {
                var j = i
                while j < n && chars[j] != "\n" { j += 1 }
                emit(String(chars[i..<j]), commentColor); i = j; continue
            }
            // block comment /* ... */
            if c == "/" && i + 1 < n && chars[i + 1] == "*" {
                var j = i + 2
                while j + 1 < n && !(chars[j] == "*" && chars[j + 1] == "/") { j += 1 }
                j = min(j + 2, n)
                emit(String(chars[i..<j]), commentColor); i = j; continue
            }
            // string  "  '  `
            if c == "\"" || c == "'" || c == "`" {
                let q = c
                var j = i + 1
                while j < n {
                    if chars[j] == "\\" { j += 2; continue }
                    if chars[j] == q { j += 1; break }
                    if chars[j] == "\n" { break }
                    j += 1
                }
                emit(String(chars[i..<min(j, n)]), stringColor); i = min(j, n); continue
            }
            // number
            if c.isNumber {
                var j = i
                while j < n && (chars[j].isHexDigit || chars[j] == "." || chars[j] == "x"
                               || chars[j] == "_" || chars[j] == "e") { j += 1 }
                emit(String(chars[i..<j]), numberColor); i = j; continue
            }
            // identifier / keyword
            if c.isLetter || c == "_" {
                var j = i
                while j < n && (chars[j].isLetter || chars[j].isNumber || chars[j] == "_") { j += 1 }
                let word = String(chars[i..<j])
                emit(word, keywords.contains(word) ? keywordColor : plainColor); i = j; continue
            }
            emit(String(c), plainColor); i += 1
        }
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
