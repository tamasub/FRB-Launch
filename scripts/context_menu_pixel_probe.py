"""Color-independent pixel probe used by the Windows context-menu smoke.

We compare two *rendered* images of the same QAction after changing only its
text.  Unlike a threshold for dark RGB values in a fixed x range, this works
for arbitrary foreground colors and Windows font renderers.  It still fails
closed when no actionable glyphs are actually drawn.
"""


def changed_label_pixels(before, after, row, *, x_start=52, right_margin=16,
                         rgb_delta=35):
    """Count pixels differing enough to show a label redraw, outside the icon.

    The caller must ensure the QMenu width and row geometry are unchanged
    between captures.  The two images must be the same size.  Alpha is not a
    useful signal on Windows layered/QMenu surfaces, so compare RGB only.
    """
    if before.width() != after.width() or before.height() != after.height():
        return 0
    left = max(0, row.left(), x_start)
    right = min(before.width() - right_margin, row.right() + 1)
    top = max(0, row.top() + 4)
    bottom = min(before.height(), row.bottom() - 3)
    changed = 0
    for y in range(top, bottom):
        for x in range(left, right):
            a = before.pixelColor(x, y)
            b = after.pixelColor(x, y)
            if (abs(a.red() - b.red()) + abs(a.green() - b.green()) +
                    abs(a.blue() - b.blue())) >= rgb_delta:
                changed += 1
    return changed
