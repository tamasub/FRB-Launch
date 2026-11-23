"""Short, read-only Windows trace for Obsidian's post-pop-out focus issue.

Enabled automatically for 90 seconds after an explicit third-column Obsidian
pop-out/close. No hooks, input synthesis, SetWindowPos or foreground requests.
Only transient HWND/PID, native style bits, Z-order and event labels are stored.
No names, file paths, URLs, note contents, or typed text enter the log.
"""
import ctypes
from ctypes import wintypes
from datetime import datetime
import json
import os
from pathlib import Path
import time

TRACE_NAME = 'obsidian_popout_activation_trace.jsonl'
TRACE_SECONDS = 90
MAX_BYTES = 1024 * 1024
WS_EX_TOPMOST = 0x00000008
GWL_EXSTYLE = -20
GW_HWNDPREV = 3
GW_OWNER = 4
_SESSION = None


def trace_path():
    return Path(os.environ.get('LOCALAPPDATA') or str(Path.home())) / 'FRBLaunch' / TRACE_NAME


def _write(event, **fields):
    try:
        path = trace_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size >= MAX_BYTES:
            path.replace(path.with_name(TRACE_NAME + '.old'))
        data = {'time': datetime.now().astimezone().isoformat(timespec='milliseconds'),
                'event': event, 'launch_pid': os.getpid()}
        data.update(fields)
        with path.open('a', encoding='utf-8') as fp:
            fp.write(json.dumps(data, ensure_ascii=False, separators=(',', ':')) + '\n')
    except Exception:
        pass  # Diagnostics must never interrupt editing or navigation.


def _native_snapshot(launch_hwnd, obsidian_hwnd):
    """Read only. Results are safe to compare even when either HWND vanished."""
    if os.name != 'nt':
        return {'native_unavailable': True}
    try:
        u = ctypes.WinDLL('user32', use_last_error=True)
        h = wintypes.HWND
        u.IsWindow.argtypes = [h]
        u.IsWindow.restype = wintypes.BOOL
        u.IsWindowVisible.argtypes = [h]
        u.IsWindowVisible.restype = wintypes.BOOL
        u.GetWindowLongPtrW.argtypes = [h, ctypes.c_int]
        u.GetWindowLongPtrW.restype = ctypes.c_ssize_t
        u.GetWindow.argtypes = [h, ctypes.c_uint]
        u.GetWindow.restype = h
        u.GetParent.argtypes = [h]
        u.GetParent.restype = h
        u.GetForegroundWindow.argtypes = []
        u.GetForegroundWindow.restype = h
        u.GetActiveWindow.argtypes = []
        u.GetActiveWindow.restype = h
        u.GetTopWindow.argtypes = [h]
        u.GetTopWindow.restype = h
        u.GetWindowThreadProcessId.argtypes = [h, ctypes.POINTER(wintypes.DWORD)]
        u.GetWindowThreadProcessId.restype = wintypes.DWORD

        def snapshot_one(hwnd):
            hwnd = int(hwnd or 0)
            if not hwnd or not u.IsWindow(hwnd):
                return {'hwnd': hwnd, 'valid': False}
            pid = wintypes.DWORD()
            thread_id = int(u.GetWindowThreadProcessId(hwnd, ctypes.byref(pid)))
            exstyle = int(u.GetWindowLongPtrW(hwnd, GWL_EXSTYLE))
            return {'hwnd': hwnd, 'valid': True,
                    'pid': int(pid.value), 'thread_id': thread_id,
                    'visible': bool(u.IsWindowVisible(hwnd)),
                    'topmost': bool(exstyle & WS_EX_TOPMOST),
                    'parent': int(u.GetParent(hwnd) or 0),
                    'owner': int(u.GetWindow(hwnd, GW_OWNER) or 0),
                    'prev': int(u.GetWindow(hwnd, GW_HWNDPREV) or 0)}

        # Ranking is for observing Z-order, never for modifying it.
        positions = {}
        top = int(u.GetTopWindow(0) or 0)
        seen = set()
        for order in range(300):
            if not top or top in seen:
                break
            seen.add(top)
            if top in (launch_hwnd, obsidian_hwnd):
                positions[top] = order
            if len(positions) == 2:
                break
            top = int(u.GetWindow(top, 2) or 0)  # GW_HWNDNEXT
        launch_pos = positions.get(launch_hwnd)
        obs_pos = positions.get(obsidian_hwnd)
        fg = int(u.GetForegroundWindow() or 0)
        return {'foreground': fg, 'active_thread_window': int(u.GetActiveWindow() or 0),
                'foreground_role': ('launch' if fg == launch_hwnd else
                                    'obsidian' if fg == obsidian_hwnd else 'other'),
                'launch': snapshot_one(launch_hwnd),
                'obsidian': snapshot_one(obsidian_hwnd),
                'launch_z': launch_pos, 'obsidian_z': obs_pos,
                'obsidian_above_launch': (obs_pos < launch_pos
                                          if obs_pos is not None and launch_pos is not None
                                          else None)}
    except Exception as exc:
        return {'snapshot_error': type(exc).__name__}


def begin(obsidian_hwnd, launch_hwnd, *, route):
    """Start just before restoring Obsidian to the desktop."""
    global _SESSION
    obsidian_hwnd, launch_hwnd = int(obsidian_hwnd or 0), int(launch_hwnd or 0)
    if not (obsidian_hwnd and launch_hwnd):
        return False
    _SESSION = {'obsidian': obsidian_hwnd, 'launch': launch_hwnd,
                'started': time.monotonic(), 'last_state': None,
                'last_heartbeat': 0.0, 'route': route}
    record('detach_before')
    return True


def active():
    return _SESSION is not None


def launch_click_needs_zorder_repair(launch_hwnd):
    """Detect the exact foreground/Z-order split seen after Obsidian pop-out.

    The optional repair is permitted only on a user mouse press inside the
    active Launch, during a known detached Obsidian trace session. It must
    never affect ordinary Launch clicks or a currently attached Obsidian.
    """
    session = _SESSION
    if (session is None or int(launch_hwnd or 0) != session['launch']
            or time.monotonic() - session['started'] > TRACE_SECONDS):
        return False
    snap = _native_snapshot(session['launch'], session['obsidian'])
    launch = snap.get('launch', {})
    obsidian = snap.get('obsidian', {})
    return bool(
        snap.get('foreground') == session['launch']
        and snap.get('obsidian_above_launch') is True
        and launch.get('valid', False) and obsidian.get('valid', False)
        and not launch.get('topmost') and not obsidian.get('topmost')
        and obsidian.get('parent') == 0
    )


def record(event, **fields):
    """Explicit checkpoints (including Launch mouse press), no input changes."""
    global _SESSION
    session = _SESSION
    if session is None:
        return
    elapsed = time.monotonic() - session['started']
    if elapsed > TRACE_SECONDS:
        _write('trace_end', elapsed_ms=round(elapsed * 1000), reason='timeout')
        _SESSION = None
        return
    _write(event, elapsed_ms=round(elapsed * 1000),
           route=session['route'],
           **_native_snapshot(session['launch'], session['obsidian']), **fields)


def poll():
    """Called from the existing 160ms preview timer after the guest detaches."""
    global _SESSION
    session = _SESSION
    if session is None:
        return
    elapsed = time.monotonic() - session['started']
    if elapsed >= TRACE_SECONDS:
        _write('trace_end', elapsed_ms=round(elapsed * 1000), reason='timeout')
        _SESSION = None
        return
    snap = _native_snapshot(session['launch'], session['obsidian'])
    state = (snap.get('foreground'), snap.get('obsidian_above_launch'),
             snap.get('launch', {}).get('topmost'), snap.get('obsidian', {}).get('topmost'),
             snap.get('obsidian', {}).get('parent'), snap.get('obsidian', {}).get('owner'))
    change = state != session['last_state']
    heartbeat = elapsed - session['last_heartbeat'] >= 2.0
    if change or heartbeat:
        session['last_state'] = state
        session['last_heartbeat'] = elapsed
        _write('window_state_changed' if change else 'window_state_heartbeat',
               elapsed_ms=round(elapsed * 1000), route=session['route'], **snap)


def reset_for_test():
    """Test isolation only; never invoked from the application."""
    global _SESSION
    _SESSION = None
