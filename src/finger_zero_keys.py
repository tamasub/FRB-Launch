"""Physical-key policy for FRB Launch's 小指Zero shortcuts.

Only the TEN-KEY pad is eligible.  Ordinary top-row 0/1 and the separate
Insert/End keys must retain their original meaning.  Keep this module Qt-free
so that the hardware recognition policy can be regression-tested on Linux.
"""

# Qt::KeypadModifier and Windows VK_NUMPAD0/VK_NUMPAD1.
QT_KEYPAD_MODIFIER = 0x20000000
VK_NUMPAD0 = 0x60
VK_NUMPAD1 = 0x61
VK_INSERT = 0x2D
VK_END = 0x23
VK_APPS = 0x5D

# Values of Qt.Key (numeric so this module has no PySide6 dependency).
QT_KEY_0 = 0x30
QT_KEY_1 = 0x31
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


def finger_zero_action(key, modifiers, native_vk=0, *, in_dialog=False):
    """Return 'enter', 'tab', 'slash', or None for the physical key.

    The caller is responsible for Launcher ownership and text/IME focus guards.
    Qt's KeypadModifier is present on the keypad (even though it is not a
    user-held Ctrl/Alt/Shift shortcut). No other modifier is accepted.

    With NumLock OFF, Qt typically reports Insert/End + KeypadModifier.
    Do not guess from the bare Insert/End key: ordinary navigation keys must
    remain usable if Windows/Qt does not identify the keypad conclusively.
    """
    key = _qt_enum_int(key)
    mods = _qt_enum_int(modifiers)
    vk = _qt_enum_int(native_vk or 0)
    if mods & ~QT_KEYPAD_MODIFIER:
        return None
    keypad = bool(mods & QT_KEYPAD_MODIFIER)
    if key == QT_KEY_MENU or vk == VK_APPS:
        return 'slash'
    if ((key == QT_KEY_0 and (keypad or vk == VK_NUMPAD0))
            or (key == QT_KEY_INSERT and keypad)):
        return 'enter'
    if in_dialog and (
            (key == QT_KEY_1 and (keypad or vk == VK_NUMPAD1))
            or (key == QT_KEY_END and keypad)):
        return 'tab'
    return None
