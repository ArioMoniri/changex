import Cocoa
import Quartz

/// Quick Look preview controller. Renders the file into a native, in-process `NSTextView`
/// (an `NSAttributedString` from `ChangexRenderer`). No WebKit — a WKWebView renders blank
/// inside the sandboxed Quick Look host, so native text is the reliable path. Rendering is
/// synchronous, so the completion handler fires immediately and the panel never hangs.
class PreviewViewController: NSViewController, QLPreviewingController {
    private var textView: NSTextView!

    override func loadView() {
        let scroll = NSScrollView(frame: NSRect(x: 0, y: 0, width: 640, height: 460))
        scroll.hasVerticalScroller = true
        scroll.drawsBackground = true
        scroll.backgroundColor = .textBackgroundColor
        scroll.autohidesScrollers = true

        let size = scroll.contentSize
        let tv = NSTextView(frame: NSRect(origin: .zero, size: size))
        tv.minSize = NSSize(width: 0, height: 0)
        tv.maxSize = NSSize(width: CGFloat.greatestFiniteMagnitude, height: CGFloat.greatestFiniteMagnitude)
        tv.isVerticallyResizable = true
        tv.isHorizontallyResizable = false
        tv.autoresizingMask = [.width]
        tv.isEditable = false
        tv.isSelectable = true
        tv.drawsBackground = true
        tv.backgroundColor = .textBackgroundColor
        tv.textContainerInset = NSSize(width: 16, height: 14)
        tv.textContainer?.containerSize = NSSize(width: size.width, height: CGFloat.greatestFiniteMagnitude)
        tv.textContainer?.widthTracksTextView = true

        scroll.documentView = tv
        textView = tv
        view = scroll
    }

    func preparePreviewOfFile(at url: URL, completionHandler handler: @escaping (Error?) -> Void) {
        do {
            let data = try Data(contentsOf: url)
            textView.textStorage?.setAttributedString(ChangexRenderer.attributed(for: url, data: data))
            handler(nil)
        } catch {
            handler(error)
        }
    }
}
