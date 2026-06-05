import AppKit

/// Headless guard for the Quick Look renderer: asserts the native NSAttributedString actually
/// contains the redline text + the right attributes (strikethrough deletion, coloured
/// insertion) and that code is syntax-coloured — the regression that once made the preview
/// blank. Run in CI:
///   swiftc -O Extension/ChangexRenderer.swift Tests/RenderCheck.swift -o rendercheck && ./rendercheck
@main
struct RenderCheck {
    static func main() {
        var fails = 0
        func check(_ cond: Bool, _ msg: String) {
            if cond { print("ok  · \(msg)") } else { print("FAIL· \(msg)"); fails += 1 }
        }

        func hasAttr(_ s: NSAttributedString, _ key: NSAttributedString.Key,
                     where pred: (Any) -> Bool) -> Bool {
            var found = false
            s.enumerateAttribute(key, in: NSRange(location: 0, length: s.length)) { v, _, stop in
                if let v = v, pred(v) { found = true; stop.pointee = true }
            }
            return found
        }

        // .changex → redline
        let journal = """
        {"type":"header","doc":{"filename":"Doc.docx","format":"docx"}}
        {"op":{"kind":"text.replace","before":"old","after":"new"},"provenance":{"agent":"Claude"}}
        """
        let chx = ChangexRenderer.attributed(for: URL(fileURLWithPath: "/tmp/x.changex"),
                                             data: Data(journal.utf8))
        let chxText = chx.string
        check(chxText.contains("Doc.docx"), "changex shows filename")
        check(chxText.contains("old") && chxText.contains("new"), "changex shows before/after")
        check(chxText.contains("1 tracked change"), "changex counts ops")
        check(chx.length > 0, "changex preview is non-empty (never blank)")
        check(hasAttr(chx, .strikethroughStyle) { ($0 as? Int ?? 0) != 0 }, "deletion is struck through")
        check(hasAttr(chx, .foregroundColor) { ($0 as? NSColor) == .systemGreen }, "insertion is green")

        // code → syntax highlight (keyword coloured)
        let code = ChangexRenderer.attributed(for: URL(fileURLWithPath: "/tmp/x.py"),
                                              data: Data("import os  # c\nx = 1\n".utf8))
        check(code.string.contains("import"), "code shows the source")
        check(hasAttr(code, .foregroundColor) { ($0 as? NSColor) == .systemPink }, "keyword coloured")
        check(hasAttr(code, .foregroundColor) { ($0 as? NSColor) == .systemGray }, "comment coloured")

        // plain text (.txt) → shown as-is, NOT mis-highlighted as code
        let txt = ChangexRenderer.attributed(for: URL(fileURLWithPath: "/tmp/note.txt"),
                                             data: Data("for the type is done\n".utf8))
        check(txt.string.contains("for the type is done"), "text file shows its content")
        check(!hasAttr(txt, .foregroundColor) { ($0 as? NSColor) == .systemPink },
              "prose words are NOT coloured like keywords")

        if fails > 0 { print("\n\(fails) render check(s) failed"); exit(1) }
        print("\nall render checks passed")
    }
}
