import Cocoa
import Quartz
import WebKit

/// Quick Look preview controller. macOS calls `preparePreviewOfFile` with the file the
/// user is previewing; we render HTML (a `.changex` redline, or syntax-highlighted source)
/// into a WKWebView. The WebView draws its own opaque background so the content is never
/// invisible against Quick Look's dark panel.
class PreviewViewController: NSViewController, QLPreviewingController {
    private lazy var webView: WKWebView = {
        let config = WKWebViewConfiguration()
        let wv = WKWebView(frame: .zero, configuration: config)
        // Draw an opaque background (the HTML sets a solid colour for light & dark) — the
        // previous transparent webview showed dark text on the dark panel = blank.
        if wv.responds(to: NSSelectorFromString("setDrawsBackground:")) {
            wv.setValue(true, forKey: "drawsBackground")
        }
        return wv
    }()

    /// Bundled highlight.min.js, read once from the extension's Resources.
    private static let hljs: String? = {
        let bundle = Bundle(for: PreviewViewController.self)
        guard let url = bundle.url(forResource: "highlight.min", withExtension: "js") else { return nil }
        return try? String(contentsOf: url, encoding: .utf8)
    }()

    override func loadView() {
        view = webView
    }

    func preparePreviewOfFile(at url: URL, completionHandler handler: @escaping (Error?) -> Void) {
        do {
            let data = try Data(contentsOf: url)
            let html = ChangexRenderer.html(for: url, data: data, hljs: Self.hljs)
            webView.loadHTMLString(html, baseURL: nil)
            handler(nil)
        } catch {
            handler(error)
        }
    }
}
