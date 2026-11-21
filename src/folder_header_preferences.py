"""Folder-specific Files List column geometry (Qt-free storage helpers).

Only widths of data columns 0..3 and visual column order are persisted;
column 4 is a stretch spacer whose width is controlled by the viewport.
Keyboard Ex reads the actual List Name width and never stores its own copy.
"""

import json

from folder_identity_preferences import folder_identity_token

PREFIX = 'expanded_middle_columns_by_folder_v1/'
DATA_COLUMNS = 4
TOTAL_COLUMNS = 5


def header_layout_key(directory):
    token = folder_identity_token(directory)
    return PREFIX + token if token else None


def capture_header_layout(header):
    return {'widths': [int(header.sectionSize(i)) for i in range(DATA_COLUMNS)],
            'order': [int(header.logicalIndex(i)) for i in range(TOTAL_COLUMNS)]}


def validated_header_layout(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (ValueError, TypeError):
            return None
    if not isinstance(value, dict):
        return None
    widths = value.get('widths')
    order = value.get('order')
    if not (isinstance(widths, list) and len(widths) == DATA_COLUMNS and
            all(type(width) is int and 34 <= width <= 10000 for width in widths)):
        return None
    if not (isinstance(order, list) and len(order) == TOTAL_COLUMNS and
            all(type(x) is int for x in order) and
            sorted(order) == list(range(TOTAL_COLUMNS))):
        return None
    return {'widths': list(widths), 'order': list(order)}


def load_header_layout(settings, key, baseline):
    if not key:
        return baseline
    layout = validated_header_layout(settings.value(key, None))
    return layout if layout is not None else baseline


def save_header_layout(settings, key, layout, baseline):
    """No per-folder record if unchanged from the user's baseline layout."""
    if not key:
        return False
    candidate = validated_header_layout(layout)
    if candidate is None:
        return False
    if candidate == baseline:
        settings.remove(key)
    else:
        settings.setValue(key, json.dumps(candidate, ensure_ascii=False,
                                          separators=(',', ':')))
    return True


def apply_header_layout(header, layout):
    """Apply only user-resizable columns and order; preserve the spacer."""
    checked = validated_header_layout(layout)
    if checked is None:
        return False
    for logical, width in enumerate(checked['widths']):
        if header.sectionSize(logical) != width:
            header.resizeSection(logical, width)
    for visual, logical in enumerate(checked['order']):
        current = header.visualIndex(logical)
        if current != visual:
            header.moveSection(current, visual)
    return True
