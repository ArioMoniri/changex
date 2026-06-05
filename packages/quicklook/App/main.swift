import Cocoa

/// Must match the embedded Quick Look extension's bundle id (see project.yml).
let extensionBundleID = "dev.changex.ChangeXQuickLook.QuickLookExtension"
/// Where the canonical install lives — registrations from anywhere else are stale duplicates.
let canonicalAppPath = "/Applications/ChangeXQuickLook.app"

/// Minimal host app for the ChangeX Quick Look extension. It exists so macOS can register the
/// extension, and doubles as the controller: enable / disable the preview, clean up stale
/// duplicate registrations, and report coexisting code previewers (e.g. Qedit). The
/// `changex quicklook` CLI does the same headlessly.
final class AppDelegate: NSObject, NSApplicationDelegate {
    private var window: NSWindow!
    private let statusLabel = NSTextField(labelWithString: "")
    private let envLabel = NSTextField(labelWithString: "")
    private let cleanButton = NSButton(title: "Clean duplicates", target: nil, action: nil)

    func applicationDidFinishLaunching(_ note: Notification) {
        let rect = NSRect(x: 0, y: 0, width: 540, height: 320)
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
            "Preview .changex journals (the tracked-change redline — who changed what) and "
            + "source-code files (syntax-highlighted) in Finder — select a file and press Space, "
            + "no app needed.")
        blurb.textColor = .secondaryLabelColor

        statusLabel.font = .systemFont(ofSize: 13, weight: .medium)
        envLabel.textColor = .secondaryLabelColor
        envLabel.font = .systemFont(ofSize: 11)
        envLabel.maximumNumberOfLines = 3

        let enableBtn = NSButton(title: "Enable", target: self, action: #selector(enable))
        enableBtn.keyEquivalent = "\r"
        let disableBtn = NSButton(title: "Disable", target: self, action: #selector(disable))
        cleanButton.target = self
        cleanButton.action = #selector(cleanDuplicates)
        cleanButton.isHidden = true
        let toggles = NSStackView(views: [enableBtn, disableBtn, cleanButton])
        toggles.spacing = 8

        let settingsBtn = NSButton(
            title: "Open Extensions settings…", target: self, action: #selector(openExtensions)
        )

        let stack = NSStackView(views: [title, blurb, statusLabel, envLabel, toggles, settingsBtn])
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
        // macOS discovers a freshly-installed extension asynchronously; re-check shortly.
        scheduleRefresh(after: 1.5)
    }

    // MARK: - pluginkit

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

    /// All filesystem paths macOS currently has registered for our extension id.
    private func registeredPaths() -> [String] {
        let out = pluginkit(["-m", "-vvv", "-i", extensionBundleID])
        return out.split(separator: "\n").compactMap { line in
            guard let r = line.range(of: "Path = ") else { return nil }
            return String(line[r.upperBound...]).trimmingCharacters(in: .whitespaces)
        }
    }

    private var isEnabled: Bool {
        pluginkit(["-m", "-i", extensionBundleID])
            .trimmingCharacters(in: .whitespacesAndNewlines)
            .hasPrefix("+")
    }

    /// Other third-party Quick Look preview extensions that also handle code (informational —
    /// so the user understands which previewer wins and where to switch it).
    private func coexistingPreviewers() -> [String] {
        let out = pluginkit(["-m", "-p", "com.apple.quicklook.preview"])
        var names: [String] = []
        for line in out.split(separator: "\n") {
            let id = line.trimmingCharacters(in: CharacterSet(charactersIn: "+ \t"))
                .components(separatedBy: "(").first ?? ""
            if id.contains("changex") || id.hasPrefix("com.apple.") { continue }
            if id.lowercased().contains("qedit") { names.append("Qedit") }
            else if id.contains("SourceCodeSyntaxHighlight") { names.append("Syntax Highlight") }
            else if id.contains("QLMarkdown") { names.append("QLMarkdown") }
        }
        return Array(Set(names)).sorted()
    }

    // MARK: - Actions

    @objc private func enable() {
        pluginkit(["-e", "use", "-i", extensionBundleID])
        refresh(); scheduleRefresh(after: 0.5); scheduleRefresh(after: 1.5)
    }

    @objc private func disable() {
        pluginkit(["-e", "ignore", "-i", extensionBundleID])
        refresh(); scheduleRefresh(after: 0.5)
    }

    /// Remove registrations that point anywhere other than the canonical /Applications copy —
    /// stale dev builds / old DerivedData copies that would otherwise duplicate the previewer.
    @objc private func cleanDuplicates() {
        for path in registeredPaths() where !path.hasPrefix(canonicalAppPath) {
            pluginkit(["-r", path])
        }
        refresh(); scheduleRefresh(after: 0.8)
    }

    @objc private func openExtensions() {
        if let url = URL(string: "x-apple.systempreferences:com.apple.ExtensionsPreferences") {
            NSWorkspace.shared.open(url)
        }
    }

    // MARK: - Status

    private func scheduleRefresh(after seconds: TimeInterval) {
        DispatchQueue.main.asyncAfter(deadline: .now() + seconds) { [weak self] in self?.refresh() }
    }

    private func refresh() {
        let paths = registeredPaths()
        if paths.isEmpty {
            statusLabel.stringValue = "Status: registering… keep this app in /Applications, then click Enable."
            statusLabel.textColor = .secondaryLabelColor
        } else if isEnabled {
            statusLabel.stringValue = "Status: enabled ✓ — press Space on a .changex or code file."
            statusLabel.textColor = .systemGreen
        } else {
            statusLabel.stringValue = "Status: installed but off — click Enable."
            statusLabel.textColor = .secondaryLabelColor
        }

        // Duplicate detection (stale copies registered from outside /Applications).
        let stale = paths.filter { !$0.hasPrefix(canonicalAppPath) }
        cleanButton.isHidden = stale.isEmpty

        var notes: [String] = []
        if !stale.isEmpty {
            notes.append("⚠︎ \(stale.count) duplicate registration\(stale.count == 1 ? "" : "s") "
                + "from old builds — click “Clean duplicates”.")
        }
        let others = coexistingPreviewers()
        if !others.isEmpty {
            notes.append("Coexisting code previewers: \(others.joined(separator: ", ")). "
                + "If they conflict, choose the active one in Extensions settings.")
        }
        envLabel.stringValue = notes.joined(separator: "\n")
        envLabel.isHidden = notes.isEmpty
    }
}

let app = NSApplication.shared
let delegate = AppDelegate()
app.delegate = delegate
app.setActivationPolicy(.regular)
app.run()
