"""Cross-component static contracts (Windows native GUI still needs acceptance)."""
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]


def test_shift_arrow_keeps_range_and_uses_existing_extended_selection():
    app = (ROOT/'src/app.py').read_text(encoding='utf-8')
    exp = (ROOT/'src/expanded_view.py').read_text(encoding='utf-8')
    assert 'event.modifiers() == Qt.KeyboardModifier.ShiftModifier' in app
    assert 'QItemSelectionModel.SelectionFlag.NoUpdate' in app
    assert 'selected_row.setSelected(True)' in app
    assert 'tree_widget.scrollToItem(target)' in app
    assert 'self.middle.tree.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)' in exp


def test_rail_position_refreshed_after_preview_layout_transition():
    exp = (ROOT/'src/expanded_view.py').read_text(encoding='utf-8')
    assert 'QTimer.singleShot(80, self.queue_rail_wheel_position)' in exp
    assert 'handle = self.files_splitter.handle(1)' in exp


def test_studio_popout_requires_private_owner_release_ack():
    panel = (ROOT/'src/studio_preview_panel.py').read_text(encoding='utf-8')
    assert '@FRB_LAUNCH_RELEASE@' in panel
    assert "if reply != 'OK':" in panel
    assert 'attached.detach(foreground=True, show_window=True)' in panel
    assert "self._process = None  # It is NO LONGER a Launch-owned session." in panel
    # The reciprocal NativeShell release contract has its own Studio test.


def test_obsidian_handoff_does_not_modify_vault_theme_and_monitor_only_hwnd():
    panel = (ROOT/'src/studio_preview_panel.py').read_text(encoding='utf-8')
    assert 'prefer_light_native_frame(hwnd)' in panel
    assert 'self._check_embedded_editor_health' in panel
    assert 'attached.u.IsWindow(int(attached.hwnd))' in panel
    assert 'self._restore_launch_focus_during_handoff' in panel
    assert 'SW_HIDE' in panel
