"""Pure, Qt-free third-column geometry. Splitter logical sizes exclude handles.

Never mutate saved preference widths while the workspace is maximized.
"""

def maximize_sizes(sizes, preview_index, first_min=190, list_min=190):
    """Clamp Exp/List to legal widths, give all remaining width to the third."""
    sizes = [max(0, int(size)) for size in sizes]
    if not 2 <= preview_index < len(sizes):
        return sizes
    total = sum(sizes)
    # Under extremely narrow windows, Qt's actual widget minima take priority.
    first = min(int(first_min), total)
    second = min(int(list_min), max(0, total - first))
    result = [0] * len(sizes)
    result[0], result[1] = first, second
    result[preview_index] = max(0, total - first - second)
    return result


def restore_sizes(sizes, preview_index, normal_columns):
    """Restore the three pre-maximize column widths, including after a swap."""
    sizes = [max(0, int(size)) for size in sizes]
    if not 2 <= preview_index < len(sizes) or not normal_columns:
        return sizes
    total = sum(sizes)
    first, second, _third = (max(0, int(n)) for n in normal_columns)
    normal_total = max(1, first + second + _third)
    first = min(total, round(total * first / normal_total))
    second = min(total - first, round(total * second / normal_total))
    result = [0] * len(sizes)
    result[0], result[1] = first, second
    result[preview_index] = max(0, total - first - second)
    return result
