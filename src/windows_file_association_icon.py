"""Read small document icons from Windows' effective file associations.

Why there are two sources: SHGetFileInfoW('.md', USEFILEATTRIBUTES)
may return the generic icon even when Explorer shows Obsidian's dedicated
Markdown *document* icon. ASSOCSTR_DEFAULTICON identifies that registered
resource. SHGetFileInfoW(real_path) is a second Explorer-style fallback.

Read-only and presentation-only: never change file associations or JSON, open
Markdown content, invoke the associated app, or persist copied icon assets.
"""
import os
import ntpath


# Values from shlwapi.h ASSOCSTR and shellapi.h SHGFI_*.
_ASSOCSTR_DEFAULTICON = 15
_ASSOCSTR_EXECUTABLE = 2
_SHGFI_ICON = 0x100
_SHGFI_SMALLICON = 0x1
_SHGFI_USEFILEATTRIBUTES = 0x10


def _split_icon_reference(raw):
    """Parse the Windows DefaultIcon resource format (path,index)."""
    if not isinstance(raw, str):
        return None
    raw = raw.strip()
    if raw.startswith('@'):
        raw = raw[1:]
    filename, sep, number = raw.rpartition(',')
    if sep:
        try:
            index = int(number.strip(), 10)
            path = filename.strip().strip('"')
        except ValueError:
            return None  # Do not guess at malformed registry resources.
    else:
        path, index = raw.strip('"'), 0
    path = os.path.expandvars(path).strip()
    if not path or not ntpath.isabs(path):
        return None
    return path, index


def _query_association_string(extension, kind):
    """Ask Windows for the current *effective* default (not legacy HKCR)."""
    if os.name != 'nt':
        return None
    try:
        import ctypes
        from ctypes import wintypes
        function = ctypes.WinDLL('shlwapi', use_last_error=True).AssocQueryStringW
        function.argtypes = [wintypes.DWORD, wintypes.DWORD, wintypes.LPCWSTR,
                             wintypes.LPCWSTR, wintypes.LPWSTR,
                             ctypes.POINTER(wintypes.DWORD)]
        function.restype = ctypes.c_long
        size = wintypes.DWORD(2048)
        buffer = ctypes.create_unicode_buffer(size.value)
        # No verb for DEFAULTICON: it belongs to the file class, not a command.
        verb = 'open' if kind == _ASSOCSTR_EXECUTABLE else None
        if function(0, kind, extension, verb, buffer, ctypes.byref(size)) == 0:
            return buffer.value or None
    except (AttributeError, OSError, ValueError):
        pass
    return None


def _safe_call(callback, *args):
    try:
        return callback(*args)
    except Exception:
        return None


def _choose_icon(extension, file_path, query, resource_icon, shell_icon):
    """Testable priority order; never substitute Obsidian for another default.

    Unlike an extension's generic icon, a file association can point at a
    dedicated document icon. For .md, try that resource first. If no resource
    is published, a *real path* may still carry an Explorer-customized icon.
    """
    if extension == '.md':
        reference = _safe_call(query, extension, _ASSOCSTR_DEFAULTICON)
        if reference:
            result = _safe_call(resource_icon, reference)
            if result is not None:
                return result
        if file_path:
            result = _safe_call(shell_icon, file_path, False)
            if result is not None:
                return result
        # Some Obsidian registrations have an executable but no DefaultIcon.
        # Only use its app icon when Obsidian is the effective *default*.
        executable = _safe_call(query, extension, _ASSOCSTR_EXECUTABLE)
        if (executable and os.path.basename(executable.replace('\\', '/')).casefold()
                == 'obsidian.exe'):
            result = _safe_call(shell_icon, executable, False)
            if result is not None:
                return result
    return _safe_call(shell_icon, extension, True)


def _qicon_from_hicon(hicon, size):
    """Render Win32 HICON into a detached Qt pixmap (no HWND lifetime issues)."""
    import ctypes
    from PySide6.QtGui import QIcon, QImage, QPixmap

    class BITMAPINFOHEADER(ctypes.Structure):
        _fields_ = [('biSize', ctypes.c_uint32), ('biWidth', ctypes.c_int32),
                    ('biHeight', ctypes.c_int32), ('biPlanes', ctypes.c_uint16),
                    ('biBitCount', ctypes.c_uint16), ('biCompression', ctypes.c_uint32),
                    ('biSizeImage', ctypes.c_uint32), ('biXPelsPerMeter', ctypes.c_int32),
                    ('biYPelsPerMeter', ctypes.c_int32), ('biClrUsed', ctypes.c_uint32),
                    ('biClrImportant', ctypes.c_uint32)]

    class BITMAPINFO(ctypes.Structure):
        _fields_ = [('bmiHeader', BITMAPINFOHEADER), ('bmiColors', ctypes.c_uint32 * 1)]

    gdi = ctypes.WinDLL('gdi32', use_last_error=True)
    user = ctypes.WinDLL('user32', use_last_error=True)
    gdi.CreateDIBSection.argtypes = [ctypes.c_void_p, ctypes.POINTER(BITMAPINFO),
                                     ctypes.c_uint32, ctypes.POINTER(ctypes.c_void_p),
                                     ctypes.c_void_p, ctypes.c_uint32]
    gdi.CreateDIBSection.restype = ctypes.c_void_p
    gdi.CreateCompatibleDC.argtypes = [ctypes.c_void_p]
    gdi.CreateCompatibleDC.restype = ctypes.c_void_p
    gdi.SelectObject.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
    gdi.SelectObject.restype = ctypes.c_void_p
    gdi.DeleteObject.argtypes = [ctypes.c_void_p]
    gdi.DeleteObject.restype = ctypes.c_int
    gdi.DeleteDC.argtypes = [ctypes.c_void_p]
    gdi.DeleteDC.restype = ctypes.c_int
    user.DrawIconEx.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                               ctypes.c_void_p, ctypes.c_int, ctypes.c_int,
                               ctypes.c_uint32, ctypes.c_void_p, ctypes.c_uint32]
    user.DrawIconEx.restype = ctypes.c_int

    dib = BITMAPINFO()
    dib.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    dib.bmiHeader.biWidth = size
    dib.bmiHeader.biHeight = -size  # top-down, BGRA bytes
    dib.bmiHeader.biPlanes = 1
    dib.bmiHeader.biBitCount = 32
    pixels = ctypes.c_void_p()
    bitmap = gdi.CreateDIBSection(None, ctypes.byref(dib), 0,
                                  ctypes.byref(pixels), None, 0)
    if not bitmap:
        return None
    try:
        if not pixels.value:
            return None
        dc = gdi.CreateCompatibleDC(None)
        if not dc:
            return None
        try:
            previous = gdi.SelectObject(dc, bitmap)
            try:
                if not user.DrawIconEx(dc, 0, 0, hicon, size, size, 0, None, 0x3):
                    return None
                bgra = ctypes.string_at(pixels, size * size * 4)
            finally:
                if previous:
                    gdi.SelectObject(dc, previous)
        finally:
            gdi.DeleteDC(dc)
    finally:
        gdi.DeleteObject(bitmap)

    # Shell icons with no usable alpha are delegated to Qt's safe fallback.
    if not any(bgra[i] for i in range(3, len(bgra), 4)):
        return None
    img = QImage(bgra, size, size, size * 4,
                 QImage.Format.Format_ARGB32_Premultiplied).copy()
    return QIcon(QPixmap.fromImage(img)) if not img.isNull() else None


def _shell_icon(path, use_file_attributes, size):
    import ctypes

    class SHFILEINFOW(ctypes.Structure):
        _fields_ = [('hIcon', ctypes.c_void_p), ('iIcon', ctypes.c_int),
                    ('dwAttributes', ctypes.c_uint32),
                    ('szDisplayName', ctypes.c_wchar * 260),
                    ('szTypeName', ctypes.c_wchar * 80)]

    shell = ctypes.WinDLL('shell32', use_last_error=True)
    user = ctypes.WinDLL('user32', use_last_error=True)
    shell.SHGetFileInfoW.argtypes = [ctypes.c_wchar_p, ctypes.c_uint32,
                                   ctypes.POINTER(SHFILEINFOW), ctypes.c_uint32,
                                   ctypes.c_uint32]
    shell.SHGetFileInfoW.restype = ctypes.c_void_p
    user.DestroyIcon.argtypes = [ctypes.c_void_p]
    user.DestroyIcon.restype = ctypes.c_int
    info = SHFILEINFOW()
    flags = _SHGFI_ICON | _SHGFI_SMALLICON
    if use_file_attributes:
        flags |= _SHGFI_USEFILEATTRIBUTES
    shell.SHGetFileInfoW(path, 0x80 if use_file_attributes else 0,
                         ctypes.byref(info), ctypes.sizeof(info), flags)
    if not info.hIcon:
        return None
    try:
        return _qicon_from_hicon(info.hIcon, size)
    finally:
        user.DestroyIcon(info.hIcon)


def _resource_icon(reference, size):
    """Load exactly the icon registered in DefaultIcon, incl. negative IDs."""
    import ctypes
    parts = _split_icon_reference(reference)
    if not parts:
        return None
    location, index = parts
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    user = ctypes.WinDLL('user32', use_last_error=True)
    shell.SHDefExtractIconW.argtypes = [ctypes.c_wchar_p, ctypes.c_int,
                                       ctypes.c_uint32, ctypes.c_void_p,
                                       ctypes.POINTER(ctypes.c_void_p),
                                       ctypes.c_uint32]
    shell.SHDefExtractIconW.restype = ctypes.c_long
    user.DestroyIcon.argtypes = [ctypes.c_void_p]
    user.DestroyIcon.restype = ctypes.c_int
    small = ctypes.c_void_p()
    # The same requested size in both LOWORD and HIWORD.
    hr = shell.SHDefExtractIconW(location, index, 0, None, ctypes.byref(small),
                                (size << 16) | size)
    if hr != 0 or not small.value:
        if small.value:
            user.DestroyIcon(small)
        return None
    try:
        return _qicon_from_hicon(small, size)
    finally:
        user.DestroyIcon(small)


def file_type_icon(extension, size=16, file_path=None):
    """Return QIcon for file type using Windows, or None for Qt fallback.

    file_path is an optional display-only source for .md; the file is never
    opened. Other extensions retain the 2026-11-23 rendering behavior.
    """
    if (os.name != 'nt' or not isinstance(extension, str)
            or not extension.startswith('.')):
        return None
    try:
        size = 16 if size <= 16 else 32
        return _choose_icon(
            extension.casefold(), file_path,
            _query_association_string,
            lambda value: _resource_icon(value, size),
            lambda path, attrs: _shell_icon(path, attrs, size))
    except Exception:
        return None  # Never crash the Explorer panels on Shell/Qt failures.
