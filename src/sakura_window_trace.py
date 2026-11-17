"""Temporary Sakura window-detection trace (observation only).

UTF-8 JSON lines: %LOCALAPPDATA%/FRBLaunch/sakura_window_trace.log.
Only Sakura file opens write events. No UI or window state is modified.
Remove the diagnostic calls after collecting one real Windows trace.
"""
import ctypes
import json
import os
from ctypes import wintypes
from datetime import datetime
from pathlib import Path

LOG_NAME = 'sakura_window_trace.log'
MAX_BYTES = 1024 * 1024


def log_path():
    return Path(os.environ.get('LOCALAPPDATA') or str(Path.home())) / 'FRBLaunch' / LOG_NAME


def trace(event, **fields):
    """Best-effort local log. Never fail an editor operation."""
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
