"""Standalone Windows-native progress window for the independent Updater.

Intentionally uses only Python's standard library and Win32 (ctypes), NOT
Tkinter/Tcl, Qt, or an external UI runtime.  In particular, a PyInstaller
--onefile Updater must be able to start *before* attempting Journal recovery;
missing Tcl data used to kill the executable in the PyInstaller runtime hook.

The update runs once in a worker thread.  All Win32 window calls that update
controls are made on the main UI thread through a queue and WM_TIMER.
"""
from __future__ import annotations

import os
import queue
import threading

STAGE_NAMES = {
    'wait': 'Launch・Studio終了待ち',
    'download': '更新ファイルの取得',
    'verify': '更新ファイルの検証',
    'backup': '旧Systemのバックアップ',
    'stage': '新Systemの展開',
    'apply': '新Systemの適用',
    'rollback': '旧Systemへの復旧',
    'restart': 'Launch再起動',
    'verify_installed': '適用後の整合性検証',
    'completed': '完了',
    'failed': '更新失敗',
}


def show_progress_window(task, *, on_ready=None):
    """Run task(report) once, showing native progress on Windows.

    On non-Windows development/test hosts, a console callback is enough.
    Before the worker starts, a Windows UI initialization failure raises to
    the caller, which can safely fall back to a headless update once.
    """
    if os.name != 'nt':
        if on_ready is not None:
            on_ready()
        return task(lambda phase, message, current=None, total=None:
                    print('[%s] %s' % (phase.upper(), message), flush=True))
    return _win32_progress_window(task, on_ready=on_ready)


def _win32_progress_window(task, *, on_ready=None):
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.WinDLL('user32', use_last_error=True)
    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    comctl32 = ctypes.WinDLL('comctl32', use_last_error=True)

    HWND = wintypes.HWND
    HINSTANCE = wintypes.HINSTANCE
    LPCWSTR = wintypes.LPCWSTR
    LRESULT = ctypes.c_ssize_t  # pointer-sized return on 64-bit Windows
    WPARAM = ctypes.c_size_t
    LPARAM = ctypes.c_ssize_t
    WNDPROC = ctypes.WINFUNCTYPE(LRESULT, HWND, wintypes.UINT, WPARAM, LPARAM)

    class POINT(ctypes.Structure):
        _fields_ = [('x', wintypes.LONG), ('y', wintypes.LONG)]

    class MSG(ctypes.Structure):
        _fields_ = [('hwnd', HWND), ('message', wintypes.UINT), ('wParam', WPARAM),
                    ('lParam', LPARAM), ('time', wintypes.DWORD), ('pt', POINT),
                    ('lPrivate', wintypes.DWORD)]

    class WNDCLASSW(ctypes.Structure):
        _fields_ = [('style', wintypes.UINT), ('lpfnWndProc', WNDPROC),
                    ('cbClsExtra', ctypes.c_int), ('cbWndExtra', ctypes.c_int),
                    ('hInstance', HINSTANCE), ('hIcon', wintypes.HICON),
                    ('hCursor', wintypes.HANDLE), ('hbrBackground', wintypes.HBRUSH),
                    ('lpszMenuName', LPCWSTR), ('lpszClassName', LPCWSTR)]

    class INITCOMMONCONTROLSEX(ctypes.Structure):
        _fields_ = [('dwSize', wintypes.DWORD), ('dwICC', wintypes.DWORD)]

    def api(dll, name, restype, argtypes):
        fn = getattr(dll, name)
        fn.restype = restype
        fn.argtypes = argtypes
        return fn

    create = api(user32, 'CreateWindowExW', HWND, [
        wintypes.DWORD, LPCWSTR, LPCWSTR, wintypes.DWORD,
        ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
        HWND, wintypes.HMENU, HINSTANCE, ctypes.c_void_p])
    set_text = api(user32, 'SetWindowTextW', wintypes.BOOL, [HWND, LPCWSTR])
    enable = api(user32, 'EnableWindow', wintypes.BOOL, [HWND, wintypes.BOOL])
    send_message = api(user32, 'SendMessageW', LRESULT,
                       [HWND, wintypes.UINT, WPARAM, LPARAM])
    default_proc = api(user32, 'DefWindowProcW', LRESULT,
                       [HWND, wintypes.UINT, WPARAM, LPARAM])
    destroy = api(user32, 'DestroyWindow', wintypes.BOOL, [HWND])
    post_quit = api(user32, 'PostQuitMessage', None, [ctypes.c_int])
    set_window_pos = api(user32, 'SetWindowPos', wintypes.BOOL, [
        HWND, HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT])
    set_foreground = api(user32, 'SetForegroundWindow', wintypes.BOOL, [HWND])
    set_timer = api(user32, 'SetTimer', ctypes.c_size_t,
                    [HWND, ctypes.c_size_t, wintypes.UINT, ctypes.c_void_p])
    kill_timer = api(user32, 'KillTimer', wintypes.BOOL, [HWND, ctypes.c_size_t])
    register = api(user32, 'RegisterClassW', wintypes.ATOM,
                   [ctypes.POINTER(WNDCLASSW)])
    module_handle = api(kernel32, 'GetModuleHandleW', HINSTANCE, [LPCWSTR])
    init_controls = api(comctl32, 'InitCommonControlsEx', wintypes.BOOL,
                        [ctypes.POINTER(INITCOMMONCONTROLSEX)])
    show_window = api(user32, 'ShowWindow', wintypes.BOOL, [HWND, ctypes.c_int])
    update_window = api(user32, 'UpdateWindow', wintypes.BOOL, [HWND])
    get_message = api(user32, 'GetMessageW', wintypes.BOOL,
                      [ctypes.POINTER(MSG), HWND, wintypes.UINT, wintypes.UINT])
    translate = api(user32, 'TranslateMessage', wintypes.BOOL,
                    [ctypes.POINTER(MSG)])
    dispatch = api(user32, 'DispatchMessageW', LRESULT, [ctypes.POINTER(MSG)])

    WM_TIMER, WM_CLOSE, WM_DESTROY, WM_COMMAND = 0x0113, 0x0010, 0x0002, 0x0111
    WM_USER = 0x0400
    PBM_SETRANGE32, PBM_SETPOS, PBM_SETMARQUEE = WM_USER + 6, WM_USER + 2, WM_USER + 10
    PBS_MARQUEE = 0x08
    SWP_NOSIZE, SWP_NOMOVE, SWP_SHOWWINDOW = 0x0001, 0x0002, 0x0040
    HWND_TOPMOST = HWND(-1)
    WS_CHILD, WS_VISIBLE = 0x40000000, 0x10000000
    WS_OVERLAPPEDWINDOW = 0x00CF0000
    WS_CAPTION_ONLY = WS_OVERLAPPEDWINDOW & ~0x00040000 & ~0x00010000  # no resizing/maximize

    state = {'finished': False, 'result': 1, 'indeterminate': False}
    events = queue.Queue()
    widgets = {}

    def update_events():
        while True:
            try:
                item = events.get_nowait()
            except queue.Empty:
                break
            if item[0] == 'progress':
                _, phase, message, current, total = item
                determinate = isinstance(total, (int, float)) and total > 0 and isinstance(current, (int, float))
                percent = max(0, min(100, round(current * 100 / total))) if determinate else None
                stage_text = STAGE_NAMES.get(phase, phase)
                set_text(widgets['stage'], stage_text + (f'  {percent}%' if percent is not None else ''))
                set_text(widgets['detail'], str(message))
                if determinate:
                    if state['indeterminate']:
                        send_message(widgets['bar'], PBM_SETMARQUEE, 0, 0)
                        state['indeterminate'] = False
                    position = max(0, min(1000, round(current * 1000 / total)))
                    send_message(widgets['bar'], PBM_SETPOS, position, 0)
                elif phase in ('completed', 'failed'):
                    if state['indeterminate']:
                        send_message(widgets['bar'], PBM_SETMARQUEE, 0, 0)
                        state['indeterminate'] = False
                    send_message(widgets['bar'], PBM_SETPOS, 1000 if phase == 'completed' else 0, 0)
                elif not state['indeterminate']:
                    send_message(widgets['bar'], PBM_SETMARQUEE, 1, 45)
                    state['indeterminate'] = True
            elif item[0] == 'done':
                state['finished'] = True
                set_text(widgets['stage'], '更新処理が完了しました' if state['result'] == 0 else '更新できませんでした')
                set_text(widgets['notice'], '処理が終了しました。結果を確認して閉じてください。')
                enable(widgets['close'], True)

    @WNDPROC
    def window_proc(hwnd, msg, wparam, lparam):
        if msg == WM_TIMER:
            update_events()
            return 0
        if msg == WM_COMMAND and lparam == widgets.get('close'):
            if state['finished']:
                destroy(hwnd)
            return 0
        if msg == WM_CLOSE:
            if state['finished']:
                destroy(hwnd)
            return 0  # Never close the UI while update/rollback is active.
        if msg == WM_DESTROY:
            kill_timer(hwnd, 1)
            post_quit(0)
            return 0
        return default_proc(hwnd, msg, wparam, lparam)

    instance = module_handle(None)
    controls = INITCOMMONCONTROLSEX(ctypes.sizeof(INITCOMMONCONTROLSEX), 0x20)
    if not init_controls(ctypes.byref(controls)):
        raise OSError('Windows進捗コントロールを初期化できません')
    class_name = 'FRBUpdaterProgress_' + str(os.getpid())
    wc = WNDCLASSW()
    wc.lpfnWndProc = window_proc
    wc.hInstance = instance
    wc.hbrBackground = ctypes.c_void_p(6)  # COLOR_WINDOW + 1
    wc.lpszClassName = class_name
    if not register(ctypes.byref(wc)):
        raise ctypes.WinError(ctypes.get_last_error())

    hwnd = create(0, class_name, 'FRB Updater — 更新状況', WS_CAPTION_ONLY | WS_VISIBLE,
                  -2147483648, -2147483648, 510, 290, None, None, instance, None)
    if not hwnd:
        raise ctypes.WinError(ctypes.get_last_error())

    def child(class_, text, style, x, y, width, height, ident=0):
        control = create(0, class_, text, WS_CHILD | WS_VISIBLE | style,
                         x, y, width, height, hwnd, ident, instance, None)
        if not control:
            raise ctypes.WinError(ctypes.get_last_error())
        return control

    # The system's own fonts, contrast and high-DPI handling follow the user's
    # current Windows theme rather than requiring a separate bundled UI stack.
    widgets['title'] = child('STATIC', 'FRB Updater', 0, 22, 18, 460, 28)
    widgets['stage'] = child('STATIC', '更新の準備をしています...', 0, 22, 53, 460, 24)
    widgets['bar'] = child('msctls_progress32', '', PBS_MARQUEE, 22, 86, 452, 24)
    send_message(widgets['bar'], PBM_SETRANGE32, 0, 1000)
    widgets['detail'] = child('STATIC', 'Launcher が終了するまで確認しています', 0,
                              22, 122, 450, 48)
    widgets['notice'] = child('STATIC', '※更新中はLaunchやStudioを起動しないでください。', 0,
                              22, 181, 455, 24)
    widgets['close'] = child('BUTTON', '閉じる', 0, 375, 216, 100, 29, 1001)
    enable(widgets['close'], False)
    # ShowWindow's *first* call can be overridden by inherited STARTUPINFO.
    # Reassert visibility and z-order when launched from a tray/background app.
    show_window(hwnd, 5)
    show_window(hwnd, 5)
    if not set_window_pos(hwnd, HWND_TOPMOST, 0, 0, 0, 0,
                          SWP_NOSIZE | SWP_NOMOVE | SWP_SHOWWINDOW):
        destroy(hwnd)
        raise ctypes.WinError(ctypes.get_last_error())
    set_foreground(hwnd)  # Best effort: Windows may reject focus stealing.
    update_window(hwnd)
    if not set_timer(hwnd, 1, 100, None):
        destroy(hwnd)
        raise ctypes.WinError(ctypes.get_last_error())
    # A ready marker means UI creation succeeded. The worker has not started.
    if on_ready is not None:
        try:
            on_ready()
        except BaseException:
            destroy(hwnd)
            raise

    def report(phase, message, current=None, total=None):
        events.put(('progress', phase, message, current, total))

    def worker():
        try:
            state['result'] = int(task(report))
        except BaseException as exc:
            state['result'] = 1
            report('failed', str(exc))
        finally:
            events.put(('done',))

    threading.Thread(target=worker, name='FRB-updater', daemon=True).start()
    message = MSG()
    while True:
        status = get_message(ctypes.byref(message), None, 0, 0)
        if status == 0:
            break
        if status == -1:
            raise ctypes.WinError(ctypes.get_last_error())
        translate(ctypes.byref(message))
        dispatch(ctypes.byref(message))
    return state['result']
