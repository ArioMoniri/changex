import Foundation

/// Headless guard for the Quick Look renderer (no WebKit needed): asserts the HTML
/// actually contains the redline / syntax-highlight markup and a solid background — the
/// regression that once made the preview look blank. Run in CI:
///   swiftc -O Extension/ChangexRenderer.swift Tests/RenderCheck.swift -o rendercheck && ./rendercheck
@main
struct RenderCheck {
    static func main() {
        var fails = 0
        func check(_ cond: Bool, _ msg: String) {
            if cond { print("ok  · \(msg)") } else { print("FAIL· \(msg)"); fails += 1 }
        }

        // .changex → redline
        let journal = """
        {"type":"header","doc":{"filename":"Doc.docx","format":"docx"}}
        {"op":{"kind":"text.replace","before":"old","after":"new"},"provenance":{"agent":"Claude"}}
        """
        let chx = ChangexRenderer.html(for: URL(fileURLWithPath: "/tmp/x.changex"),
                                       data: Data(journal.utf8), hljs: nil)
        check(chx.contains("Doc.docx"), "changex shows filename")
        check(chx.contains("<del>old</del>"), "changex shows deletion")
        check(chx.contains("<ins>new</ins>"), "changex shows insertion")
        check(chx.contains("1 tracked change"), "changex counts ops")
        check(chx.contains("background:#ffffff"), "solid background (never blank)")

        // code → syntax highlight
        let code = ChangexRenderer.html(for: URL(fileURLWithPath: "/tmp/x.py"),
                                        data: Data("import os\nprint(1)\n".utf8), hljs: "/*HLJS*/")
        check(code.contains("class=\"language-python\""), "python tagged for highlight.js")
        check(code.contains("/*HLJS*/"), "highlight.js inlined into the page")
        check(code.contains("<pre class=\"code\">"), "code block rendered")
        check(code.contains("background:#ffffff"), "code view solid background")

        // a .changex extension still wins even with code-ish content
        let amb = ChangexRenderer.html(for: URL(fileURLWithPath: "/tmp/y.changex"),
                                       data: Data(journal.utf8), hljs: "/*HLJS*/")
        check(!amb.contains("language-"), "changex extension routes to redline, not code")

        if fails > 0 { print("\n\(fails) render check(s) failed"); exit(1) }
        print("\nall render checks passed")
    }
}
