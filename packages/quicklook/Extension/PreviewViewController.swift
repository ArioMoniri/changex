import Cocoa
import Quartz
import WebKit

/// Quick Look preview controller for `.changex` journals. macOS calls
/// `preparePreviewOfFile` with the file the user is previewing; we render the redline
/// HTML into a WKWebView. Network is off (the HTML is self-contained).
class PreviewViewController: NSViewController, QLPreviewingController {
    private lazy var webView: WKWebView = {
        let config = WKWebViewConfiguration()
        let wv = WKWebView(frame: .zero, configuration: config)
        wv.setValue(false, forKey: "drawsBackground")
        return wv
    }()

    override func loadView() {
        view = webView
    }

    func preparePreviewOfFile(at url: URL, completionHandler handler: @escaping (Error?) -> Void) {
        do {
            let data = try Data(contentsOf: url)
            webView.loadHTMLString(ChangexRenderer.html(from: data), baseURL: nil)
            handler(nil)
        } catch {
            handler(error)
        }
    }
}
