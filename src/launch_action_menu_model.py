"""Fixed v0.1 FRB Launch action catalog and physical Ctrl+Menu policy.

UI, shortcut bindings, and implementation are deliberately separate.  A later
JSON ViewDef can reorder these stable IDs without simulating key presses.
"""

from finger_zero_keys import QT_KEY_MENU, VK_APPS, _qt_enum_int

QT_CONTROL_MODIFIER = 0x04000000
QT_KEYPAD_MODIFIER = 0x20000000

# (stable action ID, visible label, existing keyboard entrance, Files-only)
LAUNCH_ACTIONS = (
    ('launch_search_history', 'Launch検索履歴を表示', '検索履歴を直接表示（Ctrl+Fは従来どおり検索欄へ移動）', False),
    ('breadcrumb_history', 'パンくず履歴を表示', 'Ctrl+G', True),
    ('folder_search_history', 'フォルダ検索履歴を表示', 'Ctrl+H', True),
    ('launch_settings', '設定を表示', 'Ctrl+I', False),
)


def is_ctrl_menu_key(key, modifiers, native_vk=0):
    """Recognize only Ctrl + the physical Windows Applications/Menu key.

    Preserve plain Menu (existing '/' action), Ctrl+other keys, and any
    Shift/Alt/Meta combination.  KeypadModifier is not a held shortcut key.
    """
    key = _qt_enum_int(key)
    mods = _qt_enum_int(modifiers)
    vk = _qt_enum_int(native_vk or 0)
    return (key == QT_KEY_MENU or vk == VK_APPS) and (mods & ~QT_KEYPAD_MODIFIER) == QT_CONTROL_MODIFIER


def action_is_available(action_id, files_mode):
    for identifier, _, _, files_only in LAUNCH_ACTIONS:
        if identifier == action_id:
            return not files_only or bool(files_mode)
    return False
