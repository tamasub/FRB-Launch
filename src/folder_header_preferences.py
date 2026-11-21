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


# JSON-authored logical folders have no on-disk File ID. Their canonical
# Page/Item identities are stable across caption edits and UI reordering.
VIRTUAL_PREFIX = 'expanded_middle_columns_by_virtual_v1/'
VIRTUAL_BASELINE = {'widths': [300, 350, 145],
                    'order': [0, 1, 2, 3, 4]}


def virtual_header_layout_key(node):
    if not isinstance(node, dict):
        return None
    page_id = node.get('page_id')
    node_id = node.get('node_id')
    if not page_id or not node_id:
        return None
    import hashlib
    identity = json.dumps([str(page_id), str(node_id)],
                          ensure_ascii=False, separators=(',', ':'))
    return VIRTUAL_PREFIX + hashlib.sha256(identity.encode('utf-8')).hexdigest()


def validated_virtual_header_layout(value):
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (TypeError, ValueError):
            return None
    if not isinstance(value, dict):
        return None
    widths, order = value.get('widths'), value.get('order')
    if not (isinstance(widths, list) and len(widths) == 3 and
            all(type(x) is int and 34 <= x <= 10000 for x in widths)):
        return None
    if not (isinstance(order, list) and len(order) == TOTAL_COLUMNS and
            all(type(x) is int for x in order) and
            sorted(order) == list(range(TOTAL_COLUMNS))):
        return None
    return {'widths': list(widths), 'order': list(order)}


def capture_virtual_header_layout(header):
    # Column 3 is HIDDEN in JSON mode. Qt reports a zero section size for it,
    # so the physical 4-column capture format is intentionally not reused.
    return {'widths': [int(header.sectionSize(i)) for i in range(3)],
            'order': [int(header.logicalIndex(i)) for i in range(TOTAL_COLUMNS)]}


def load_virtual_header_layout(settings, key):
    found = validated_virtual_header_layout(settings.value(key, None)) if key else None
    return found if found is not None else VIRTUAL_BASELINE


def save_virtual_header_layout(settings, key, layout):
    if not key:
        return False
    found = validated_virtual_header_layout(layout)
    if found is None:
        return False
    if found == VIRTUAL_BASELINE:
        settings.remove(key)
    else:
        settings.setValue(key, json.dumps(found, ensure_ascii=False,
                                          separators=(',', ':')))
    return True


def apply_virtual_header_layout(header, layout):
    found = validated_virtual_header_layout(layout)
    if found is None:
        return False
    for logical, width in enumerate(found['widths']):
        if header.sectionSize(logical) != width:
            header.resizeSection(logical, width)
    for visual, logical in enumerate(found['order']):
        current = header.visualIndex(logical)
        if current != visual:
            header.moveSection(current, visual)
    return True
