"""Screen-safe geometry for floating Exp Keyboard Ex columns.

The menu may float beyond Launch's frame but must remain within the screen's
available work area (taskbar excluded).  No Exp/List navigation policy lives
here: presentation and logical location remain independent.
"""


def popup_xy(anchor_x, anchor_y, width, height, *, work_left, work_top,
             work_right, work_bottom, parent_left=None, margin=10):
    """Return left/top of a cascade whose top initially tracks the parent row.

    Coordinates use an exclusive right/bottom, matching QRect.right()+1.
    Prefer opening to the right; flip to the left of the parent if necessary.
    Slide upward to avoid the taskbar rather than shrinking the popup first.
    """
    left = work_left + margin
    top = work_top + margin
    right = work_right - margin
    bottom = work_bottom - margin
    width = min(int(width), max(1, right - left))
    height = min(int(height), max(1, bottom - top))
    x = int(anchor_x)
    if x + width > right and parent_left is not None:
        x = int(parent_left) - width
    x = max(left, min(x, right - width))
    y = max(top, min(int(anchor_y), bottom - height))
    return x, y
