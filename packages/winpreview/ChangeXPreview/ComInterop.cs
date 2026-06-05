using System;
using System.Runtime.InteropServices;

namespace ChangeXPreview
{
    // Minimal COM surface needed to implement a Windows Explorer preview handler.
    // GUIDs are the Windows-defined interface IIDs — do not change them.

    [ComImport, Guid("8895b1c6-b41f-4c1c-a562-0d564250836f"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IPreviewHandler
    {
        void SetWindow(IntPtr hwnd, ref RECT rect);
        void SetRect(ref RECT rect);
        void DoPreview();
        void Unload();
        void SetFocus();
        void QueryFocus(out IntPtr phwnd);
        [PreserveSig]
        uint TranslateAccelerator(ref MSG pmsg);
    }

    [ComImport, Guid("b7d14566-0509-4cce-a71f-0a554233bd9b"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IInitializeWithFile
    {
        void Initialize([MarshalAs(UnmanagedType.LPWStr)] string pszFilePath, uint grfMode);
    }

    [ComImport, Guid("fc4801a3-2ba9-11cf-a229-00aa003d7352"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IObjectWithSite
    {
        void SetSite([MarshalAs(UnmanagedType.IUnknown)] object pUnkSite);
        void GetSite(ref Guid riid, [MarshalAs(UnmanagedType.IUnknown)] out object ppvSite);
    }

    [ComImport, Guid("196bf9a5-b346-4ef0-aa1e-5dcdb76768b1"),
     InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
    public interface IPreviewHandlerVisuals
    {
        void SetBackgroundColor(uint color);
        void SetFont(ref LOGFONT plf);
        void SetTextColor(uint color);
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct RECT
    {
        public int left, top, right, bottom;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct POINT
    {
        public int x, y;
    }

    [StructLayout(LayoutKind.Sequential)]
    public struct MSG
    {
        public IntPtr hwnd;
        public uint message;
        public IntPtr wParam;
        public IntPtr lParam;
        public uint time;
        public POINT pt;
    }

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    public struct LOGFONT
    {
        public int lfHeight, lfWidth, lfEscapement, lfOrientation, lfWeight;
        public byte lfItalic, lfUnderline, lfStrikeOut, lfCharSet, lfOutPrecision,
                    lfClipPrecision, lfQuality, lfPitchAndFamily;
        [MarshalAs(UnmanagedType.ByValTStr, SizeConst = 32)]
        public string lfFaceName;
    }
}
