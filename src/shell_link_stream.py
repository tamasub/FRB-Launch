"""Windows Shell Link tracking held inside JSON, never in .lnk files.

IShellLinkW + IPersistStream + an in-memory IStream. This module deliberately
has no PySide6/pywin32 dependency. The Win32 calls are only made on Windows.
An unresolved link is NEVER replaced with a guessed similarly named file.
"""
from __future__ import annotations

import base64
import ctypes
import os
import uuid
from contextlib import contextmanager
from pathlib import Path


PREFIX = 'win-shell-link-stream-v1:'
MAX_PAYLOAD = 1_048_576


class ShellLinkError(RuntimeError):
    pass


def _guid(value):
    class GUID(ctypes.Structure):
        _fields_ = [('Data1', ctypes.c_uint32), ('Data2', ctypes.c_uint16),
                    ('Data3', ctypes.c_uint16), ('Data4', ctypes.c_ubyte * 8)]
    return GUID.from_buffer_copy(uuid.UUID(value).bytes_le)


def _hr(result, context):
    if result < 0:
        raise ShellLinkError(f'{context} failed: 0x{result & 0xffffffff:08X}')


def _call(ptr, slot, argtypes, *values):
    # COM methods use stdcall, and the COM object's own pointer is `this`.
    winfunc = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, *argtypes)
    vtable = ctypes.cast(ptr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
    return winfunc(vtable[slot])(ptr, *values)


def _release(ptr):
    if ptr and ptr.value:
        _call(ptr, 2, (), )


@contextmanager
def _com():
    if os.name != 'nt':
        raise ShellLinkError('Windows専用機能です')
    ole = ctypes.OleDLL('ole32')
    ole.CoInitializeEx.argtypes = [ctypes.c_void_p, ctypes.c_uint32]
    ole.CoInitializeEx.restype = ctypes.c_long
    # Qt GUI thread is usually STA. A conflicting MTA apartment must fail
    # explicitly; calling Shell COM without proper initialization is unsafe.
    hr = ole.CoInitializeEx(None, 2)  # COINIT_APARTMENTTHREADED
    _hr(hr, 'CoInitializeEx')
    try:
        yield ole
    finally:
        ole.CoUninitialize()


def _make_link(ole):
    pointer = ctypes.c_void_p()
    clsid = _guid('00021401-0000-0000-C000-000000000046')  # ShellLink
    iid = _guid('000214F9-0000-0000-C000-000000000046')    # IShellLinkW
    ole.CoCreateInstance.argtypes = [ctypes.c_void_p, ctypes.c_void_p,
                                     ctypes.c_uint32, ctypes.c_void_p, ctypes.c_void_p]
    ole.CoCreateInstance.restype = ctypes.c_long
    _hr(ole.CoCreateInstance(ctypes.byref(clsid), None, 1,
                             ctypes.byref(iid), ctypes.byref(pointer)), 'CoCreateInstance')
    return pointer


def _persist(link):
    pointer = ctypes.c_void_p()
    iid = _guid('00000109-0000-0000-C000-000000000046')  # IPersistStream
    _hr(_call(link, 0, (ctypes.c_void_p, ctypes.c_void_p),
              ctypes.byref(iid), ctypes.byref(pointer)), 'QueryInterface(IPersistStream)')
    return pointer


def _stream(ole):
    ptr = ctypes.c_void_p()
    ole.CreateStreamOnHGlobal.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p]
    ole.CreateStreamOnHGlobal.restype = ctypes.c_long
    _hr(ole.CreateStreamOnHGlobal(None, 1, ctypes.byref(ptr)), 'CreateStreamOnHGlobal')
    return ptr


def _seek(stream, offset, origin):
    position = ctypes.c_ulonglong()
    _hr(_call(stream, 5, (ctypes.c_longlong, ctypes.c_uint32, ctypes.c_void_p),
              offset, origin, ctypes.byref(position)), 'IStream.Seek')
    return position.value


def _serialize(link, ole):
    persist = _persist(link)
    stream = ctypes.c_void_p()
    try:
        stream = _stream(ole)
        _hr(_call(persist, 6, (ctypes.c_void_p, ctypes.c_int), stream, 1),
            'IPersistStream.Save')
        length = _seek(stream, 0, 2)
        if not 0 < length <= MAX_PAYLOAD:
            raise ShellLinkError('Shell Linkの保存データサイズが不正です')
        _seek(stream, 0, 0)
        buffer = ctypes.create_string_buffer(length)
        read = ctypes.c_ulong()
        _hr(_call(stream, 3, (ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p),
                  buffer, length, ctypes.byref(read)), 'IStream.Read')
        if read.value != length:
            raise ShellLinkError('Shell Linkの保存データが途中で切れました')
        return PREFIX + base64.b64encode(buffer.raw).decode('ascii')
    finally:
        _release(stream)
        _release(persist)


def _deserialize(link, ole, blob):
    if not isinstance(blob, str) or not blob.startswith(PREFIX):
        raise ShellLinkError('Shell Linkデータの形式が不正です')
    try:
        raw = base64.b64decode(blob[len(PREFIX):], validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise ShellLinkError('Shell LinkデータのBase64が不正です') from exc
    if not 0 < len(raw) <= MAX_PAYLOAD:
        raise ShellLinkError('Shell Linkデータの長さが不正です')
    persist = _persist(link)
    stream = ctypes.c_void_p()
    try:
        stream = _stream(ole)
        buffer = ctypes.create_string_buffer(raw)
        written = ctypes.c_ulong()
        _hr(_call(stream, 4, (ctypes.c_void_p, ctypes.c_ulong, ctypes.c_void_p),
                  buffer, len(raw), ctypes.byref(written)), 'IStream.Write')
        if written.value != len(raw):
            raise ShellLinkError('Shell Linkデータを復元できませんでした')
        _seek(stream, 0, 0)
        _hr(_call(persist, 5, (ctypes.c_void_p,), stream), 'IPersistStream.Load')
    finally:
        _release(stream)
        _release(persist)


def make_link_data(path):
    """Return an IPersistStream snapshot (base64 JSON string), no .lnk IO."""
    if not Path(path).is_file():
        raise ShellLinkError('既存のファイルだけが追跡対象です')
    with _com() as ole:
        link = _make_link(ole)
        try:
            _hr(_call(link, 20, (ctypes.c_wchar_p,), str(Path(path).resolve())),
                'IShellLink.SetPath')
            return _serialize(link, ole)
        finally:
            _release(link)


def resolve_link_data(blob):
    """Return (existing_path, updated_blob); NEVER open/execute the target.

    Explicit Resolve is mandatory for links held in an IStream: Windows does
    not implicitly repair a link that is not stored as a physical .lnk file.
    """
    with _com() as ole:
        link = _make_link(ole)
        try:
            _deserialize(link, ole, blob)
            # 3-second timeout, no UI, request tracked target update.
            flags = (3000 << 16) | 0x0001 | 0x0004  # SLR_NO_UI | SLR_UPDATE
            _hr(_call(link, 19, (ctypes.c_void_p, ctypes.c_uint32), None, flags),
                'IShellLink.Resolve')
            buffer = ctypes.create_unicode_buffer(32768)
            _hr(_call(link, 3, (ctypes.c_void_p, ctypes.c_int,
                                ctypes.c_void_p, ctypes.c_uint32),
                      buffer, len(buffer), None, 0), 'IShellLink.GetPath')
            target = buffer.value
            if not target or not os.path.isfile(target):
                raise ShellLinkError('追跡先が見つかりません')
            return target, _serialize(link, ole)
        finally:
            _release(link)
