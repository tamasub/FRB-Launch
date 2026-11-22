"""Regression contract for 小指Zero 2026-11-22 (Qt-independent)."""
import sys
import unittest
from enum import Flag
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from finger_zero_keys import (
    QT_KEY_0, QT_KEY_1, QT_KEY_INSERT, QT_KEY_END, QT_KEY_MENU,
    QT_KEY_LEFT, QT_KEY_RIGHT, QT_CONTROL_MODIFIER,
    QT_KEYPAD_MODIFIER, VK_NUMPAD0, VK_NUMPAD1, VK_APPS,
    finger_zero_action,
)


class SimulatedQtKeyboardModifier(Flag):
    """Mimics PySide6 KeyboardModifier: has .value, rejects int(flag)."""
    NoModifier = 0
    ShiftModifier = 0x02000000
    ControlModifier = 0x04000000
    AltModifier = 0x08000000
    KeypadModifier = QT_KEYPAD_MODIFIER


class FingerZeroPolicyTests(unittest.TestCase):
    def test_pyside6_modifier_enum_value_works_without_int_cast(self):
        """Regression: actual Qt flags raised TypeError on int(modifiers)."""
        self.assertRaises(TypeError, int, SimulatedQtKeyboardModifier.NoModifier)
        self.assertEqual('slash', finger_zero_action(
            QT_KEY_MENU, SimulatedQtKeyboardModifier.NoModifier, VK_APPS))
        self.assertEqual('enter', finger_zero_action(
            QT_KEY_0, SimulatedQtKeyboardModifier.KeypadModifier,
            VK_NUMPAD0))
        self.assertEqual('tab', finger_zero_action(
            QT_KEY_RIGHT, SimulatedQtKeyboardModifier.ControlModifier,
            in_dialog=True))
        self.assertIsNone(finger_zero_action(
            QT_KEY_0,
            SimulatedQtKeyboardModifier.ControlModifier |
            SimulatedQtKeyboardModifier.KeypadModifier, VK_NUMPAD0))

    def test_key_enum_with_value_is_also_supported(self):
        """Qt.Key can also be a non-int-convertible enum."""
        class EnumLike:
            value = QT_KEY_0
        self.assertEqual('enter', finger_zero_action(
            EnumLike(), SimulatedQtKeyboardModifier.KeypadModifier,
            VK_NUMPAD0))

    def test_numpad_zero_enters_with_numlock_on(self):
        self.assertEqual('enter', finger_zero_action(
            QT_KEY_0, QT_KEYPAD_MODIFIER, VK_NUMPAD0))
        self.assertEqual('enter', finger_zero_action(QT_KEY_0, 0, VK_NUMPAD0))

    def test_numpad_zero_enters_with_numlock_off(self):
        self.assertEqual('enter', finger_zero_action(
            QT_KEY_INSERT, QT_KEYPAD_MODIFIER, 0x2D))

    def test_unrelated_insert_and_top_number_are_unmodified(self):
        self.assertIsNone(finger_zero_action(QT_KEY_INSERT, 0, 0x2D))
        self.assertIsNone(finger_zero_action(QT_KEY_0, 0, 0x30))

    def test_keypad_one_never_tabs_even_in_dialog_or_files(self):
        for key, mods, vk in (
            (QT_KEY_1, QT_KEYPAD_MODIFIER, VK_NUMPAD1),
            (QT_KEY_1, 0, VK_NUMPAD1),
            (QT_KEY_END, QT_KEYPAD_MODIFIER, 0x23),
        ):
            for in_dialog, in_files in ((False, False), (True, False),
                                        (False, True), (True, True)):
                self.assertIsNone(finger_zero_action(
                    key, mods, vk, in_dialog=in_dialog, in_files=in_files))

    def test_ctrl_right_tabs_and_ctrl_left_backtabs(self):
        for key, action in ((QT_KEY_RIGHT, 'tab'),
                            (QT_KEY_LEFT, 'backtab')):
            for in_dialog, in_files in ((False, False), (True, False),
                                        (False, True)):
                self.assertEqual(action, finger_zero_action(
                    key, QT_CONTROL_MODIFIER, in_dialog=in_dialog,
                    in_files=in_files))
                self.assertEqual(action, finger_zero_action(
                    key, QT_CONTROL_MODIFIER | QT_KEYPAD_MODIFIER))
            for mods in (0, SimulatedQtKeyboardModifier.ShiftModifier.value,
                         QT_CONTROL_MODIFIER | SimulatedQtKeyboardModifier.ShiftModifier.value,
                         QT_CONTROL_MODIFIER | SimulatedQtKeyboardModifier.AltModifier.value):
                self.assertIsNone(finger_zero_action(key, mods))

    def test_end_and_top_number_are_unmodified(self):
        self.assertIsNone(finger_zero_action(
            QT_KEY_END, 0, 0x23, in_dialog=True))
        self.assertIsNone(finger_zero_action(
            QT_KEY_1, 0, 0x31, in_dialog=True))
        self.assertIsNone(finger_zero_action(
            QT_KEY_1, 0, 0x31, in_files=True))

    def test_menu_key_invokes_slash_route(self):
        self.assertEqual('slash', finger_zero_action(QT_KEY_MENU, 0))
        self.assertEqual('slash', finger_zero_action(QT_KEY_MENU, 0, VK_APPS))

    def test_user_modifiers_do_not_trigger_actions(self):
        for modifier in (0x02000000, 0x04000000, 0x08000000):
            self.assertIsNone(finger_zero_action(
                QT_KEY_0, modifier | QT_KEYPAD_MODIFIER, VK_NUMPAD0))
            self.assertIsNone(finger_zero_action(QT_KEY_MENU, modifier, VK_APPS))


if __name__ == '__main__':
    unittest.main()
