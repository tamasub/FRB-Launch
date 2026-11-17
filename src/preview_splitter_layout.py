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
