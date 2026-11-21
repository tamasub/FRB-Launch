"""Temporary read-only diagnostics for third-column external editor Z-order.

No editor document contents, paths, titles or typed characters are logged.
Remove this module and its call sites after diagnosing the Windows behavior.
"""
import logging
import os
from ctypes import wintypes

GW_HWNDPREV = 3

def enabled():
    return os.environ.get('FRB_GUEST_ZTRACE', '1') != '0'


def write(stage, *, overlay=None, sequence=0, point=None, **fields):
    if not enabled():
        return
    logger = logging.getLogger('frb.launch.diagnostics')
    if not logger.isEnabledFor(logging.INFO):
        return
    result = {'seq': sequence, 'stage': stage}
    if point is not None:
        result['x'], result['y'] = int(point[0]), int(point[1])
    result.update(fields)
    if overlay is not None:
        try:
            u = overlay.u
            guest = int(overlay.hwnd)
            root = int(overlay._root_hwnd() or 0)
            fg = int(u.GetForegroundWindow() or 0)
            hit = int(u.WindowFromPoint(wintypes.POINT(*map(int, point))) or 0) if point is not None else 0
            # HWND Z-order neighbors expose the real relative window order.
            def above(hwnd):
                return int(u.GetWindow(hwnd, GW_HWNDPREV) or 0) if hwnd else 0
            result.update(guest=guest, launch=root, foreground=fg,
                          hit=hit, hit_is_guest=int(hit == guest),
                          hit_child=int(bool(hit and u.IsChild(guest, hit))),
                          above_launch=above(root), above_guest=above(guest),
                          overlay_attached=int(bool(overlay.attached)),
                          overlay_visible=int(bool(overlay._visible)))
        except Exception as error:
            result['snapshot_error'] = type(error).__name__
    try:
        logger.info('GUEST_ZTRACE ' + ' '.join('%s=%s' % (key, value) for key, value in result.items()))
    except Exception:
        pass
