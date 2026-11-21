"""Windows Shell file drag, standard for Files List and optional elsewhere.

Creates the IDataObject with Windows Shell's own IShellItemArray provider.
No file contents are read. The original Qt URL path remains available
through [General] files_list_explorer_drag=false in user state.ini.
"""

import ctypes
import os
import uuid


class _GUID(ctypes.Structure):
    _fields_ = [('Data1', ctypes.c_uint32), ('Data2', ctypes.c_uint16),
                ('Data3', ctypes.c_uint16), ('Data4', ctypes.c_ubyte * 8)]


def _guid(value):
    return _GUID.from_buffer_copy(uuid.UUID(value).bytes_le)


def _method(pointer, index, return_type, *argument_types):
    """Resolve a COM vtable method (Windows-only)."""
    address = ctypes.cast(pointer, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents[index]
    return ctypes.WINFUNCTYPE(return_type, ctypes.c_void_p, *argument_types)(address)


def _check_hresult(hr, what):
    if hr < 0:
        raise OSError(f'{what}: HRESULT=0x{hr & 0xffffffff:08X}')


def begin_native_shell_file_drag(widget, paths):
    """Start a copy-only Explorer-style Shell drag. True means drag attempted.

    Raises before the drag loop on failure; caller may fall back to its original
    Qt URL drag. Once SHDoDragDrop starts, cancellation is *not* a fallback:
    otherwise the same mouse gesture would unintentionally initiate two drags.
    """
    if os.name != 'nt' or not paths:
        return False

    ole32 = ctypes.WinDLL('ole32', use_last_error=True)
    shell32 = ctypes.WinDLL('shell32', use_last_error=True)

    ole32.OleInitialize.argtypes = [ctypes.c_void_p]
    ole32.OleInitialize.restype = ctypes.c_long
    ole32.OleUninitialize.argtypes = []
    ole32.OleUninitialize.restype = None
    ole32.CoTaskMemFree.argtypes = [ctypes.c_void_p]
    ole32.CoTaskMemFree.restype = None
    shell32.ILCreateFromPathW.argtypes = [ctypes.c_wchar_p]
    shell32.ILCreateFromPathW.restype = ctypes.c_void_p
    shell32.SHCreateShellItemArrayFromIDLists.argtypes = [
        ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p), ctypes.POINTER(ctypes.c_void_p)]
    shell32.SHCreateShellItemArrayFromIDLists.restype = ctypes.c_long
    shell32.SHDoDragDrop.argtypes = [
        ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p, ctypes.c_uint32,
        ctypes.POINTER(ctypes.c_uint32)]
    shell32.SHDoDragDrop.restype = ctypes.c_long

    # Native OLE drag requires OleInitialize on the GUI STA. When Qt has
    # initialized it already, S_FALSE still needs its matching uninitialize.
    hr = ole32.OleInitialize(None)
    _check_hresult(hr, 'OleInitialize')
    pidls = []
    array_ptr = ctypes.c_void_p()
    data_ptr = ctypes.c_void_p()
    try:
        for path in paths:
            pidl = shell32.ILCreateFromPathW(os.fspath(path))
            if not pidl:
                raise OSError('ILCreateFromPathW failed')
            pidls.append(pidl)
        path_array = (ctypes.c_void_p * len(pidls))(*pidls)
        _check_hresult(
            shell32.SHCreateShellItemArrayFromIDLists(
                len(pidls), path_array, ctypes.byref(array_ptr)),
            'SHCreateShellItemArrayFromIDLists')
        if not array_ptr.value:
            raise OSError('IShellItemArray not returned')

        bhid_data_object = _guid('B8C0BD9F-ED24-455C-83E6-D5390C4FE8C4')
        iid_data_object = _guid('0000010E-0000-0000-C000-000000000046')
        bind_to_handler = _method(array_ptr, 3, ctypes.c_long,
                                  ctypes.c_void_p, ctypes.POINTER(_GUID),
                                  ctypes.POINTER(_GUID), ctypes.POINTER(ctypes.c_void_p))
        _check_hresult(
            bind_to_handler(array_ptr, None, ctypes.byref(bhid_data_object),
                            ctypes.byref(iid_data_object), ctypes.byref(data_ptr)),
            'IShellItemArray.BindToHandler(BHID_DataObject)')
        if not data_ptr.value:
            raise OSError('Shell IDataObject not returned')

        # Use the native owner window and the OS default IDropSource.
        hwnd = int(widget.window().winId())
        effect = ctypes.c_uint32(0)
        # Shell performs the native drag, including CF_HDROP and its additional
        # shell formats. Do NOT start a second Qt drag after cancellation.
        shell32.SHDoDragDrop(ctypes.c_void_p(hwnd), data_ptr, None, 1,
                             ctypes.byref(effect))  # DROPEFFECT_COPY
        return True
    finally:
        if data_ptr.value:
            _method(data_ptr, 2, ctypes.c_ulong)(data_ptr)
        if array_ptr.value:
            _method(array_ptr, 2, ctypes.c_ulong)(array_ptr)
        for pidl in pidls:
            ole32.CoTaskMemFree(pidl)
        ole32.OleUninitialize()
