"""Privacy-minimal Obsidian HWND/CLI diagnostics for one real Windows handoff.

Log: %LOCALAPPDATA%/FRBLaunch/obsidian_dock_trace.jsonl (UTF-8).
No filenames, vault IDs, document titles, note contents, CLI code, or raw output.
The log intentionally records HWND and PID; those are ephemeral diagnostic IDs.
"""
import ctypes
from ctypes import wintypes
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path

LOG_NAME = 'obsidian_dock_trace.jsonl'
MAX_BYTES = 1024 * 1024


def log_path():
    return Path(os.environ.get('LOCALAPPDATA') or str(Path.home())) / 'FRBLaunch' / LOG_NAME


def fingerprint(text):
    """Stable-within-log, irreversible title fingerprint (not the title)."""
    return hashlib.sha256(str(text).strip().casefold().encode('utf-8')).hexdigest()[:16] if text else ''


def trace(event, **fields):
    """Best effort; logging cannot break the GUI or cause a window action."""
    try:
        path = log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size >= MAX_BYTES:
            path.replace(path.with_name(LOG_NAME + '.old'))
        item = {'time': datetime.now().astimezone().isoformat(timespec='milliseconds'),
                'launch_pid': os.getpid(), 'event': event}
        item.update(fields)
        with path.open('a', encoding='utf-8') as fp:
            fp.write(json.dumps(item, ensure_ascii=False, default=str) + '\n')
    except Exception:
        pass


def trace_windows(stage, expected_caption=None):
    """Read-only enumeration of Obsidian top-level HWNDs INCLUDING filtered windows.

    A raw window can be present even when editor_windows() silently excludes it.
    Never record literal window/document titles or executable paths.
    """
    if os.name != 'nt':
        return
    try:
        from external_win32_host import _api, _process_name
        u, k = _api()
        u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.GetClassNameW.restype = ctypes.c_int
        u.GetWindow.argtypes = [wintypes.HWND, ctypes.c_uint]
        u.GetWindow.restype = wintypes.HWND
        entries = []
        image_by_pid = {}
        expected = str(expected_caption or '').strip().casefold()
        cb_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

        @cb_type
        def callback(hwnd, _):
            pid_ref = wintypes.DWORD()
            u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid_ref))
            pid = int(pid_ref.value)
            if pid not in image_by_pid:
                image_by_pid[pid] = _process_name(k, pid)
            if image_by_pid[pid] != 'obsidian.exe':
                return True
            length = max(0, int(u.GetWindowTextLengthW(hwnd)))
            title = ctypes.create_unicode_buffer(length + 1)
            if length:
                u.GetWindowTextW(hwnd, title, length + 1)
            class_buff = ctypes.create_unicode_buffer(256)
            u.GetClassNameW(hwnd, class_buff, len(class_buff))
            style = int(u.GetWindowLongPtrW(hwnd, -16))
            visible = bool(u.IsWindowVisible(hwnd))
            reasons = []
            if style & 0x40000000:
                reasons.append('WS_CHILD')
            if length < 2:
                reasons.append('SHORT_TITLE')
            entries.append({'hwnd': int(hwnd), 'pid': pid, 'class': class_buff.value,
                            'visible': visible, 'child_style': bool(style & 0x40000000),
                            'parent': int(u.GetParent(hwnd) or 0),
                            'owner': int(u.GetWindow(hwnd, 4) or 0),
                            'caption_length': len(title.value),
                            'caption_hash': fingerprint(title.value),
                            'expected_match': bool(expected and title.value.strip().casefold() == expected),
                            'filtered_out': reasons})
            return True

        completed = bool(u.EnumWindows(callback, 0))
        trace('WINDOW_SCAN', stage=stage, success=completed,
              expected_hash=fingerprint(expected_caption), windows=entries[:60],
              candidate_count=len(entries))
    except Exception as exc:
        trace('WINDOW_SCAN_ERROR', stage=stage, error_type=type(exc).__name__)
