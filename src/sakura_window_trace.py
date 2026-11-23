"""Temporary Sakura window-detection trace (observation only).

UTF-8 JSON lines: %LOCALAPPDATA%/FRBLaunch/sakura_window_trace.log.
Only Sakura file opens write events. No UI or window state is modified.
Remove the diagnostic calls after collecting one real Windows trace.
"""
import ctypes
import configparser
import json
import os
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

LOG_NAME = 'sakura_window_trace.log'
MAX_BYTES = 1024 * 1024


def enabled(environment=None):
    """Diagnostic-only switch. An existing state.ini can disable it anytime.

    Missing option defaults ON while this incident is being investigated;
    unlike editor invitation flags, this never changes window behavior.
    """
    env = os.environ if environment is None else environment
    parser = configparser.ConfigParser(interpolation=None)
    try:
        path = Path(env.get('LOCALAPPDATA') or str(Path.home())) / 'FRBLaunch' / 'state.ini'
        with path.open('r', encoding='utf-8-sig') as source:
            parser.read_file(source)
        if parser.has_option('General', 'sakura_trace_enabled'):
            return parser.getboolean('General', 'sakura_trace_enabled')
    except (OSError, UnicodeError, configparser.Error, ValueError):
        pass
    return env.get('FRB_SAKURA_TRACE', '1').strip().lower() not in ('0', 'false', 'off', 'no')


def log_path():
    return Path(os.environ.get('LOCALAPPDATA') or str(Path.home())) / 'FRBLaunch' / LOG_NAME


def trace(event, **fields):
    """Best-effort local log. Never fail an editor operation."""
    if not enabled():
        return
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size >= MAX_BYTES:
            # One backup; intentionally avoid settings and third-party logging.
            path.replace(path.with_name(LOG_NAME + '.old'))
        record = dict(time=datetime.now().astimezone().isoformat(timespec='milliseconds'),
                      pid=os.getpid(), event=event)
        record.update(fields)
        with path.open('a', encoding='utf-8') as fp:
            fp.write(json.dumps(record, ensure_ascii=False, default=str) + '\n')
    except Exception:
        pass


def trace_windows(stage, *, selected=None):
    """Capture RAW top-level Sakura candidates and normal filtered results.

    In particular preserve hwnd, pid, image name, title, WS_CHILD, visibility,
    and owner. A filtered-out window is the very thing being diagnosed.
    """
    if not enabled():
        return
    if os.name != 'nt':
        trace('WINDOW_SCAN_UNSUPPORTED', stage=stage, platform=os.name)
        return
    try:
        # Reuse the Win32 declarations used by Launch's real window finder.
        from external_win32_host import _api, _process_name, editor_windows
        user32, kernel = _api()
        user32.GetWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
        user32.GetWindow.restype = wintypes.HWND
        callback_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
        names = {}
        matched = []
        counts = {'total': 0, 'visible': 0, 'titled': 0}

        @callback_type
        def visit(hwnd, _):
            counts['total'] += 1
            visible = bool(user32.IsWindowVisible(hwnd))
            counts['visible'] += int(visible)
            count = user32.GetWindowTextLengthW(hwnd)
            counts['titled'] += int(count > 0)
            pid = wintypes.DWORD()
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
            proc = names.get(pid.value)
            if proc is None:
                proc = _process_name(kernel, pid.value)
                names[pid.value] = proc
            caption = ''
            if count > 0:
                buff = ctypes.create_unicode_buffer(count + 1)
                user32.GetWindowTextW(hwnd, buff, count + 1)
                caption = buff.value
            if 'sakura' not in proc.casefold() and 'サクラエディタ' not in caption:
                return True
            style = int(user32.GetWindowLongPtrW(hwnd, -16))
            parent = user32.GetParent(hwnd)
            owner = user32.GetWindow(hwnd, 4)  # GW_OWNER
            reason = []
            if not visible:
                reason.append('hidden')
            if style & 0x40000000:
                reason.append('WS_CHILD')
            if len(caption) < 2:
                reason.append('short_title')
            if proc.casefold() != 'sakura.exe':
                reason.append('process_name_mismatch')
            matched.append(dict(hwnd=int(hwnd), pid=int(pid.value), image=proc,
                                title=caption, visible=visible, ws_child=bool(style & 0x40000000),
                                parent=int(parent or 0), owner=int(owner or 0),
                                exclusion_reasons=reason))
            return True

        success = bool(user32.EnumWindows(visit, 0))
        filtered = editor_windows('sakura', include_hidden=False)
        trace('WINDOW_SCAN', stage=stage, enum_success=success, counts=counts,
              raw_matches=matched,
              filtered=[dict(hwnd=h, pid=p, title=t) for h,p,t in filtered],
              selected=selected)
    except Exception as exc:
        trace('WINDOW_SCAN_ERROR', stage=stage,
              error_type=type(exc).__name__, error=str(exc))


def trace_desktop_inventory(*, active_hwnd, parked_hwnds=()):
    """Inventory ALL Sakura top-level HWNDs, not just Launch-managed ones.

    Only reads window titles, PIDs, Win32 visibility, Z-order and geometry.
    In particular, a screenshot can show 005.log even while its tracked old
    HWND is hidden: an untracked live HWND and a compositor ghost are not the
    same problem. Never bring an HWND forward or close an editor here.
    """
    if not enabled() or os.name != 'nt':
        return
    try:
        from external_win32_host import _api, editor_windows
        user32, _kernel = _api()
        user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
        user32.GetWindowRect.restype = wintypes.BOOL
        user32.GetWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
        user32.GetWindow.restype = wintypes.HWND
        user32.GetForegroundWindow.argtypes = []
        user32.GetForegroundWindow.restype = wintypes.HWND
        known_parked = set(int(h) for h in parked_hwnds)
        active = int(active_hwnd)
        windows = []
        # editor_windows enumerates genuine top-level Sakura windows by image;
        # include hidden windows so old handles can be distinguished.
        for hwnd, pid, title in editor_windows('sakura', include_hidden=True):
            hwnd = int(hwnd)
            if not user32.IsWindow(hwnd):
                continue
            rect = wintypes.RECT()
            rectangle = None
            if user32.GetWindowRect(hwnd, ctypes.byref(rect)):
                rectangle = [int(rect.left), int(rect.top),
                             int(rect.right - rect.left),
                             int(rect.bottom - rect.top)]
            windows.append(dict(
                hwnd=hwnd, pid=int(pid), title=title,
                visible=bool(user32.IsWindowVisible(hwnd)),
                rect=rectangle,
                immediately_above_hwnd=int(user32.GetWindow(hwnd, 3) or 0),
                managed_state=('active' if hwnd == active else
                               'parked' if hwnd in known_parked else 'untracked')))
        trace('SAKURA_DESKTOP_INVENTORY', active_hwnd=active,
              foreground_hwnd=int(user32.GetForegroundWindow() or 0),
              parked_hwnds=sorted(known_parked),
              window_count=len(windows),
              visible_count=sum(bool(w['visible']) for w in windows),
              windows=windows)
    except Exception as exc:
        trace('SAKURA_DESKTOP_INVENTORY_ERROR',
              error_type=type(exc).__name__, message=str(exc))
