"""FRB Launch right-hand keys: keypad 0, Menu and Ctrl+arrow navigation.

Keypad 1 has been retired from Tab duty: both number-row and keypad 1 retain
native numeric/editing behavior. Keep this policy Qt-free for unit tests.
"""

# Qt key/modifier values and Windows native virtual-key codes.
QT_KEYPAD_MODIFIER = 0x20000000
VK_NUMPAD0 = 0x60
VK_NUMPAD1 = 0x61
VK_INSERT = 0x2D
VK_END = 0x23
VK_APPS = 0x5D

# Values of Qt.Key (numeric so this module has no PySide6 dependency).
QT_KEY_0 = 0x30
QT_KEY_1 = 0x31
QT_KEY_LEFT = 0x01000012
QT_KEY_RIGHT = 0x01000014
QT_CONTROL_MODIFIER = 0x04000000
QT_KEY_INSERT = 0x01000006
QT_KEY_END = 0x01000011
QT_KEY_MENU = 0x01000055


def _qt_enum_int(value):
    """Normalize Python ints and PySide6 Qt enum/flag values alike.

    In PySide6, Qt.KeyboardModifier/KeyboardModifiers may reject int(flag)
    even though flag.value is an integer.  Handle both forms without
    depending on PySide6 for unit testing.
    """
    return int(getattr(value, 'value', value))


def finger_zero_action(key, modifiers, native_vk=0, *, in_dialog=False, in_files=False):
    """Map keypad 0, plain Menu, and Ctrl+Left/Right in Launch only.

    'tab' and 'backtab' are reserved for Ctrl+Right and Ctrl+Left, including
    dialog fields and the Files focus ring. The former keypad-1 Tab shortcut
    is retired in EVERY context; keypad 1/End keep their native behavior.

    This remains Qt-free. The UI bridge enforces Launch ownership, ensures
    key-up/auto-repeat cannot cause duplicate focus navigation, and dispatches
    the returned action through native Qt focus routing.
    """
    key = _qt_enum_int(key)
    mods = _qt_enum_int(modifiers)
    vk = _qt_enum_int(native_vk or 0)
    held = mods & ~QT_KEYPAD_MODIFIER
    if held == QT_CONTROL_MODIFIER:
        if key == QT_KEY_RIGHT:
            return 'tab'
        if key == QT_KEY_LEFT:
            return 'backtab'
        return None
    if held:
        return None
    keypad = bool(mods & QT_KEYPAD_MODIFIER)
    if key == QT_KEY_MENU or vk == VK_APPS:
        return 'slash'
    if ((key == QT_KEY_0 and (keypad or vk == VK_NUMPAD0))
            or (key == QT_KEY_INSERT and keypad)):
        return 'enter'
    return None
