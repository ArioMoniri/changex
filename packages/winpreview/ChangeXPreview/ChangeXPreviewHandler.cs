using System;
using System.Diagnostics;
using System.Drawing;
using System.IO;
using System.Runtime.InteropServices;
using System.Text;
using System.Windows.Forms;

namespace ChangeXPreview
{
    /// <summary>
    /// ChangeX Explorer preview handler. Explorer instantiates this in its preview host
    /// (prevhost.exe), hands us the file via <see cref="Initialize"/> and a parent window via
    /// <see cref="SetWindow"/>; we render the file to HTML by shelling out to
    /// <c>changex preview</c> and show it in a WebBrowser control parented into the preview pane.
    /// </summary>
    [ComVisible(true)]
    [Guid(Clsid)]
    [ClassInterface(ClassInterfaceType.None)]
    [ProgId("ChangeX.PreviewHandler")]
    public sealed class ChangeXPreviewHandler :
        IPreviewHandler, IInitializeWithFile, IObjectWithSite, IPreviewHandlerVisuals
    {
        public const string Clsid = "D3A1B2C4-5E6F-47A8-9B0C-1D2E3F4A5B6C";

        private string _filePath;
        private IntPtr _parentHwnd;
        private RECT _bounds;
        private Panel _host;
        private WebBrowser _browser;
        private object _site;
        private string _tempHtml;

        [DllImport("user32.dll")] private static extern IntPtr SetParent(IntPtr child, IntPtr parent);
        [DllImport("user32.dll")] private static extern bool MoveWindow(
            IntPtr hWnd, int x, int y, int w, int h, bool repaint);

        // ---- IInitializeWithFile ----
        public void Initialize(string pszFilePath, uint grfMode) => _filePath = pszFilePath;

        // ---- IPreviewHandler ----
        public void SetWindow(IntPtr hwnd, ref RECT rect) { _parentHwnd = hwnd; _bounds = rect; Reposition(); }
        public void SetRect(ref RECT rect) { _bounds = rect; Reposition(); }

        private void Reposition()
        {
            if (_host != null && _parentHwnd != IntPtr.Zero)
                MoveWindow(_host.Handle, 0, 0,
                    _bounds.right - _bounds.left, _bounds.bottom - _bounds.top, true);
        }

        public void DoPreview()
        {
            try
            {
                string html = RenderHtml(_filePath);
                _tempHtml = Path.Combine(Path.GetTempPath(),
                    "changex_preview_" + Guid.NewGuid().ToString("N") + ".html");
                File.WriteAllText(_tempHtml, html, new UTF8Encoding(false));

                _host = new Panel { BackColor = Color.White };
                _browser = new WebBrowser
                {
                    Dock = DockStyle.Fill,
                    AllowNavigation = false,
                    IsWebBrowserContextMenuEnabled = false,
                    ScriptErrorsSuppressed = true,
                    WebBrowserShortcutsEnabled = false,
                };
                _host.Controls.Add(_browser);

                IntPtr h = _host.Handle; // realize the window
                SetParent(h, _parentHwnd);
                MoveWindow(h, 0, 0, _bounds.right - _bounds.left, _bounds.bottom - _bounds.top, true);
                _browser.Navigate(new Uri(_tempHtml).AbsoluteUri);
            }
            catch (Exception ex)
            {
                ShowFallback(ex.Message);
            }
        }

        private void ShowFallback(string message)
        {
            try
            {
                _host = _host ?? new Panel { BackColor = Color.White };
                var label = new Label
                {
                    Dock = DockStyle.Fill,
                    Text = "ChangeX preview unavailable.\n\n" + message
                        + "\n\nInstall the engine:  pip install -U \"changex[preview]\"",
                    Padding = new Padding(16),
                    AutoEllipsis = true,
                };
                _host.Controls.Add(label);
                IntPtr h = _host.Handle;
                SetParent(h, _parentHwnd);
                MoveWindow(h, 0, 0, _bounds.right - _bounds.left, _bounds.bottom - _bounds.top, true);
            }
            catch { /* nothing more we can do in the preview host */ }
        }

        /// <summary>Shell out to <c>changex preview &lt;file&gt;</c> (the cross-platform engine).</summary>
        private static string RenderHtml(string file)
        {
            var psi = new ProcessStartInfo
            {
                FileName = "cmd.exe",
                // `where`-resolved changex on PATH; quoted arg for spaces.
                Arguments = "/c changex preview \"" + file + "\"",
                RedirectStandardOutput = true,
                RedirectStandardError = true,
                UseShellExecute = false,
                CreateNoWindow = true,
                StandardOutputEncoding = Encoding.UTF8,
            };
            using (var proc = Process.Start(psi))
            {
                string outText = proc.StandardOutput.ReadToEnd();
                proc.WaitForExit(20000);
                if (!string.IsNullOrWhiteSpace(outText) && outText.Contains("<"))
                    return outText;
            }
            // Engine missing/failed → show the raw file so the pane is never blank.
            string raw = File.ReadAllText(file);
            return "<!doctype html><meta charset='utf-8'><body style='background:#fff;"
                + "font:12px Consolas,monospace;white-space:pre-wrap;padding:12px'>"
                + System.Security.SecurityElement.Escape(raw) + "</body>";
        }

        public void Unload()
        {
            try { _browser?.Dispose(); _host?.Dispose(); } catch { }
            _browser = null; _host = null;
            if (_tempHtml != null && File.Exists(_tempHtml))
            {
                try { File.Delete(_tempHtml); } catch { }
                _tempHtml = null;
            }
        }

        public void SetFocus() => _browser?.Focus();
        public void QueryFocus(out IntPtr phwnd) => phwnd = _browser?.Handle ?? IntPtr.Zero;
        public uint TranslateAccelerator(ref MSG pmsg) => 1; // S_FALSE

        // ---- IObjectWithSite ----
        public void SetSite(object pUnkSite) => _site = pUnkSite;
        public void GetSite(ref Guid riid, out object ppvSite) => ppvSite = _site;

        // ---- IPreviewHandlerVisuals (we render our own page; ignore host visuals) ----
        public void SetBackgroundColor(uint color) { }
        public void SetFont(ref LOGFONT plf) { }
        public void SetTextColor(uint color) { }

        // ---- COM (un)registration (regasm /codebase calls these) ----
        private const string AppId = "{D3A1B2C4-5E6F-47A8-9B0C-1D2E3F4A5B6D}";

        [ComRegisterFunction]
        private static void Register(Type t)
        {
            using (var clsid = Microsoft.Win32.Registry.ClassesRoot
                .CreateSubKey("CLSID\\{" + Clsid + "}"))
            {
                clsid.SetValue(null, "ChangeX Preview Handler");
                clsid.SetValue("AppID", AppId);
                clsid.SetValue("DisplayName", "ChangeX Preview Handler");
            }
            // Run preview handlers out-of-process (prevhost surrogate) — the supported model.
            using (var appid = Microsoft.Win32.Registry.ClassesRoot.CreateSubKey("AppID\\" + AppId))
                appid?.SetValue("DllSurrogate", "");
            using (var reg = Microsoft.Win32.Registry.LocalMachine.CreateSubKey(
                "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\PreviewHandlers"))
                reg?.SetValue("{" + Clsid + "}", "ChangeX Preview Handler");
        }

        [ComUnregisterFunction]
        private static void Unregister(Type t)
        {
            try { Microsoft.Win32.Registry.ClassesRoot.DeleteSubKeyTree("AppID\\" + AppId, false); } catch { }
            try
            {
                using (var reg = Microsoft.Win32.Registry.LocalMachine.OpenSubKey(
                    "SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\PreviewHandlers", true))
                    reg?.DeleteValue("{" + Clsid + "}", false);
            }
            catch { }
        }
    }
}
