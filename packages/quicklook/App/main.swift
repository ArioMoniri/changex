import Cocoa

/// Must match the embedded Quick Look extension's bundle id (see project.yml).
let extensionBundleID = "dev.changex.ChangeXQuickLook.QuickLookExtension"

/// Minimal host app for the ChangeX Quick Look extension. It exists so macOS can register
/// the extension, and doubles as the controller: enable / disable the preview and jump to
/// the Extensions settings pane. The `changex quicklook` CLI does the same headlessly.
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow!
    private let statusLabel = NSTextField(labelWithString: "")

    func applicationDidFinishLaunching(_ note: Notification) {
        let rect = NSRect(x: 0, y: 0, width: 500, height: 280)
        window = NSWindow(
            contentRect: rect,
            styleMask: [.titled, .closable, .miniaturizable],
            backing: .buffered,
            defer: false
        )
        window.title = "ChangeX Quick Look"
        window.center()

        let title = NSTextField(labelWithString: "ChangeX Quick Look")
        title.font = .systemFont(ofSize: 20, weight: .semibold)

        let blurb = NSTextField(wrappingLabelWithString:
            "Preview .changex journals in Finder — select any .changex file and press Space "
            + "to see the tracked changes (who changed what), no app needed.")
        blurb.textColor = .secondaryLabelColor

        statusLabel.textColor = .secondaryLabelColor

        let enableBtn = NSButton(title: "Enable", target: self, action: #selector(enable))
        let disableBtn = NSButton(title: "Disable", target: self, action: #selector(disable))
        let settingsBtn = NSButton(
            title: "Open Extensions settings…", target: self, action: #selector(openExtensions)
        )
        let toggles = NSStackView(views: [enableBtn, disableBtn])
        toggles.spacing = 8

        let stack = NSStackView(views: [title, blurb, statusLabel, toggles, settingsBtn])
        stack.orientation = .vertical
        stack.alignment = .leading
        stack.spacing = 12
        stack.translatesAutoresizingMaskIntoConstraints = false

        let content = NSView(frame: rect)
        content.addSubview(stack)
        NSLayoutConstraint.activate([
            stack.leadingAnchor.constraint(equalTo: content.leadingAnchor, constant: 24),
            stack.trailingAnchor.constraint(equalTo: content.trailingAnchor, constant: -24),
            stack.topAnchor.constraint(equalTo: content.topAnchor, constant: 24),
        ])
        window.contentView = content
        window.makeKeyAndOrderFront(nil)
        NSApp.activate(ignoringOtherApps: true)
        refresh()
    }

    @discardableResult
    private func pluginkit(_ args: [String]) -> String {
        let proc = Process()
        proc.executableURL = URL(fileURLWithPath: "/usr/bin/pluginkit")
        proc.arguments = args
        let pipe = Pipe()
        proc.standardOutput = pipe
        proc.standardError = pipe
        try? proc.run()
        proc.waitUntilExit()
        return String(data: pipe.fileHandleForReading.readDataToEndOfFile(), encoding: .utf8) ?? ""
    }

    private func refresh() {
        let out = pluginkit(["-m", "-i", extensionBundleID]).trimmingCharacters(in: .whitespacesAndNewlines)
        if out.isEmpty {
            statusLabel.stringValue = "Status: not registered yet — keep this app in /Applications."
        } else {
            statusLabel.stringValue = out.hasPrefix("+") ? "Status: enabled ✓" : "Status: disabled"
        }
    }

    @objc private func enable() { pluginkit(["-e", "use", "-i", extensionBundleID]); refresh() }
    @objc private func disable() { pluginkit(["-e", "ignore", "-i", extensionBundleID]); refresh() }
    @objc private func openExtensions() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.ExtensionsPreferences") {
            NSWorkspace.shared.open(url)
        }
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
