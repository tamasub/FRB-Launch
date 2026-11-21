"""Files third-pane user width preferences, independent of actual splitter sizes.

Exp, List, third pane restore in that priority.  Only an explicit splitter
handle drag may write these preferences; layout calculations are read-only.
"""

# These are stable application identities, not window captions/document paths.
OWNERS = frozenset({'browser', 'studio', 'obsidian', 'vscode', 'sakura', 'options'})


def width_setting(owner):
    if owner not in OWNERS:
        raise ValueError('Unknown third-pane owner')
    return f'workspace_files_third_{owner}_desired_width_v2'


def list_setting(owner):
    if owner not in OWNERS:
        raise ValueError('Unknown third-pane owner')
    return f'workspace_files_third_{owner}_list_width_v2'


def _positive_width(value, default, minimum=100):
    try:
        result = int(value)
        if minimum <= result <= 10000:
            return result
    except (ValueError, TypeError, OverflowError):
        pass
    return max(minimum, int(default))


def preferred_third_width(settings, owner, default=500):
    """Migrate old Browser/Studio widths only when an app has no v2 setting."""
    current = settings.value(width_setting(owner), None)
    if current is not None and str(current).strip():
        return _positive_width(current, default)
    old_keys = (
        ('workspace_files_full_browser_width_v1',) if owner == 'browser'
        else ('workspace_files_studio_preview_width', 'workspace_files_preview_width')
    )
    for key in old_keys:
        value = settings.value(key, None)
        if value is not None and str(value).strip():
            return _positive_width(value, default)
    return _positive_width(None, default)


def preferred_list_width(settings, owner, default=360):
    return _positive_width(settings.value(list_setting(owner), None), default,
                           minimum=170)


def save_user_widths(settings, owner, list_width, third_width):
    """Call only at the end of a real mouse drag on pane 2/3 divider."""
    try:
        second, third = int(list_width), int(third_width)
    except (ValueError, TypeError, OverflowError):
        return False
    if not (170 <= second <= 10000 and 170 <= third <= 10000):
        return False
    settings.setValue(list_setting(owner), second)
    settings.setValue(width_setting(owner), third)
    settings.sync()
    return True


def prioritized_preview_sizes(total, count, third_index, *, exp_desired,
                              list_desired, third_desired,
                              first_min=190, list_min=170, third_min=100):
    """Prioritize Exp > List > third, never modifying desired widths.

    Any extra window width goes to List, NOT the third pane, so a preferred
    Browser width remains stable on a larger monitor.  Under constraint, the
    third pane yields first. Qt widget minima may enforce a harder limit.
    """
    total, count = max(0, int(total)), int(count)
    if count < 3 or not 2 <= third_index < count:
        raise ValueError('invalid third-pane index')
    first_min = max(0, int(first_min))
    list_min = max(0, int(list_min))
    third_min = max(0, int(third_min))
    # Even for a too-small window, allocate from the first column onward.
    if total < first_min + list_min + third_min:
        # A truly tiny viewport cannot satisfy widget minima.  Keep Exp
        # first, then give the remaining pixels to List before the preview.
        first = min(total, max(first_min, int(exp_desired)))
        result = [0] * count
        result[0], result[1] = first, max(0, total - first)
        return result
    first = min(max(first_min, int(exp_desired)),
                total - list_min - third_min)
    remain = max(0, total - first)
    second_target = max(list_min, int(list_desired))
    third_target = max(third_min, int(third_desired))
    third = min(third_target, max(0, remain - list_min))
    second = remain - third
    if second < second_target:
        rescue = min(max(0, third - third_min), second_target - second)
        third -= rescue
        second += rescue
    values = [0] * count
    values[0], values[1], values[third_index] = first, second, third
    return values
