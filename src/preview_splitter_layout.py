"""Choose third-pane sizes by widget identity, not creation order.

Browser and NativeShell panes are created lazily in either order. Never
assume the newly visible preview is automatically at splitter index 2.
"""


def preview_sizes(base_sizes, count, pane_index, preview_width, min_list_width):
    if len(base_sizes) != 2 or count < 3 or not 2 <= pane_index < count:
        raise ValueError('invalid Files splitter preview geometry')
    total = sum(base_sizes)
    first = base_sizes[0]
    sizes = [0] * count
    sizes[0] = first
    sizes[1] = max(min_list_width, total - first - preview_width)
    sizes[pane_index] = preview_width
    return sizes


def restored_preview_width(saved, default, base_sizes, min_list_width):
    """Return persisted third column width constrained to available space."""
    try:
        requested = int(saved)
        if requested < 250:
            raise ValueError('invalid preview width')
    except (ValueError, TypeError):
        requested = int(default)
    total = sum(base_sizes)
    upper = max(1, total - int(base_sizes[0]) - int(min_list_width))
    return max(1, min(requested, upper))


def saved_preview_columns(value):
    """Decode a Studio third-pane snapshot (Files Exp, Files List, Studio).

    Width alone is insufficient: the user can resize *both* splitter handles
    while Studio is visible. An invalid legacy/partial value falls back to the
    separate Studio width setting without altering the original state.
    """
    try:
        parts = [int(part) for part in str(value or '').split('|')]
    except (ValueError, TypeError):
        return None
    if (len(parts) != 3 or parts[0] < 0 or parts[1] < 100
            or parts[2] < 250):
        return None
    return parts


def plan_restored_preview_sizes(base_sizes, count, pane_index, preview_width,
                                saved_columns=None, min_first_width=190,
                                min_list_width=170):
    """Restore the *position* of the two dividers, not just pane 3 width.

    On reopen the two-column Files layout may have a wider first column than
    it had when Studio was docked. The old width-only clamp subtracted this
    unrelated width and silently shrank Studio. Prefer the saved 3-pane
    snapshot. For an older state.ini, reclaim room from the first pane before
    sacrificing the requested third-pane width.

    If the Launch window/screen is genuinely too narrow, enforce first/list
    minima and shrink Studio only as the last resort. Hidden sibling previews
    stay at zero; the real index is supplied by QSplitter.indexOf().
    """
    if len(base_sizes) != 2 or count < 3 or not 2 <= pane_index < count:
        raise ValueError('invalid Files splitter preview geometry')
    total = sum(int(value) for value in base_sizes)
    minimum = int(min_first_width) + int(min_list_width)
    if total <= minimum:
        # A frameless Launch window can temporarily be narrower than the
        # combined widget minima. Let Qt enforce those minima; do not crash
        # the document-open route just because no valid 3-pane fit exists.
        first = max(0, min(int(base_sizes[0]), max(0, total - 1)))
        return preview_sizes([first, max(0, total - first)], count,
                             pane_index, 1, min_list_width=0)
    columns = saved_preview_columns(saved_columns)
    first = int(columns[0]) if columns else int(base_sizes[0])
    third = int(columns[2]) if columns else int(preview_width)
    third = max(1, min(third, total - minimum))
    first = max(int(min_first_width), min(first, total - third - int(min_list_width)))
    # preview_sizes() owns the zero-width placeholders for other previews.
    return preview_sizes([first, total - first], count, pane_index, third,
                         min_list_width=min_list_width)
