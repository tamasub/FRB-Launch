"""Pure width calculations for FRB Launch Files Exp/List/third pane.

An EXPRESSED user width is independent of the available viewport width.
Qt splitter sizes are only transient allocations, never source preferences.
"""


def desired_exp_width(value, fallback=275):
    """Read an absolute pixel width; old splitter ratio is only a fallback."""
    try:
        width = int(value)
        if 100 <= width <= 10000:
            return width
    except (ValueError, TypeError, OverflowError):
        pass
    return int(fallback)


def resize_with_fixed_exp(sizes, exp_width, *, first_min=190, list_min=170,
                          third_index=None):
    """Hold first pane constant when the whole Launch window changes size.

    Never invent a new 'preferred' width from Qt's current proportional sizes.
    If the actual window is too small, Qt's minima take precedence.
    """
    sizes = [max(0, int(v)) for v in sizes]
    if len(sizes) < 2 or sum(sizes) == 0:
        return sizes
    total = sum(sizes)
    third_visible = (third_index is not None and
                     2 <= third_index < len(sizes) and sizes[third_index] > 0)
    third_min = 170 if third_visible else 0
    first = min(max(first_min, int(exp_width)),
                max(first_min, total - list_min - third_min))
    if first > total:
        first = total
    result = list(sizes)
    result[0] = first
    if third_visible:
        # A normal third pane keeps its current width if there is room;
        # the Files List absorbs the difference on window resize.
        third = min(result[third_index], max(0, total - first - list_min))
        result[third_index] = third
        result[1] = max(0, total - first - third)
    else:
        result[1] = max(0, total - first)
    return result


def maximize_with_fixed_exp_and_name(sizes, preview_index, *, exp_width,
                                     name_width, back_lane=24,
                                     list_chrome=8, first_min=190,
                                     list_min=170, third_min=170):
    """Maximize third pane without hiding Files List's metadata columns.

    The List viewport can scroll horizontally; only its allocated WIDTH is
    limited to the *saved Name section width* plus the side operation lane.
    All sections retain their full saved widths.
    """
    sizes = [max(0, int(v)) for v in sizes]
    if not 2 <= preview_index < len(sizes):
        return sizes
    total = sum(sizes)
    if total == 0:
        return sizes
    first = min(max(first_min, int(exp_width)),
                max(first_min, total - list_min - third_min))
    first = min(first, total)
    wanted_list = max(list_min, int(name_width) + int(back_lane) + int(list_chrome))
    second = min(wanted_list, max(0, total - first - third_min))
    # In a tiny window Qt's widget minimums are authoritative. There is no
    # persistent-width mutation regardless of any temporary contraction.
    result = [0] * len(sizes)
    result[0], result[1] = first, second
    result[preview_index] = max(0, total - first - second)
    return result
