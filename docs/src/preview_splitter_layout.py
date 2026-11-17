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
