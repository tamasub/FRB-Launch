"""Regress guest/Launch Z-order after clicking the exposed third-column editor.

Win32 doubles model the confirmed failure: clicking an active Obsidian while
Chrome remains above the adjacent Obsidian/Launch pair. This is NOT a Windows
GUI validation. Studio's SetParent path is intentionally unchanged.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE / 'src'))
sys.path.insert(0, str(HERE / 'tests'))
from test_three_editor_workspace_click_20261121 import (
    ClickDesktop, GUEST, HOST, LAUNCH, CHROME, editor_overlay,
)
from obsidian_ime_overlay import (
    ObsidianImeOverlay, HWND_TOP, SWP_NOACTIVATE, WS_EX_TOPMOST,
)
from guest_window_overlay import GuestWindowOverlay, SakuraGuestOverlay


class OldRootRaiseDoesNotPassChrome(ClickDesktop):
    """A successful root-only HWND_TOP call does not change the blocked stack."""

    def SetWindowPos(self, hwnd, after, x, y, w, h, flags):
        if hwnd == LAUNCH and after == HWND_TOP:
            self.calls.append(('place', hwnd, after, x, y, w, h, flags))
            return True
        return super().SetWindowPos(hwnd, after, x, y, w, h, flags)


def test_click_recovers_when_root_only_top_was_ineffective():
    for cls in (ObsidianImeOverlay, GuestWindowOverlay, SakuraGuestOverlay):
        api = OldRootRaiseDoesNotPassChrome()
        overlay = cls(GUEST, HOST, user32=api)
        api.foreground = GUEST
        assert api.stack.index(CHROME) < api.stack.index(GUEST) < api.stack.index(LAUNCH)
        assert overlay.raise_workspace_from_guest_click(123, 456)
        assert api.stack.index(GUEST) < api.stack.index(LAUNCH) < api.stack.index(CHROME)
        assert api.foreground == GUEST
        assert not api.exstyles[GUEST] & WS_EX_TOPMOST
        assert not api.exstyles[LAUNCH] & WS_EX_TOPMOST
        # Guest first, Launch directly BELOW guest; not Launch alone to HWND_TOP.
        calls = [c for c in api.calls if c[0] == 'place']
        guest_top = max(i for i, c in enumerate(calls)
                        if c[1] == GUEST and c[2] == HWND_TOP)
        root_below = max(i for i, c in enumerate(calls)
                         if c[1] == LAUNCH and c[2] == GUEST)
        assert guest_top < root_below
        assert calls[root_below][-1] & SWP_NOACTIVATE
        assert not any(c[0] == 'foreground' for c in api.calls)


def test_foreground_transition_repairs_adjacent_pair_behind_chrome():
    api, overlay = editor_overlay(ObsidianImeOverlay)
    assert api.stack.index(CHROME) < api.stack.index(GUEST) < api.stack.index(LAUNCH)
    # The pre-fix sync saw GUEST immediately above Launch and did nothing.
    api.foreground = GUEST
    overlay.sync()
    assert api.stack.index(GUEST) < api.stack.index(LAUNCH) < api.stack.index(CHROME)
    before = len(api.calls)
    overlay.sync()
    assert len(api.calls) == before, 'No continuous window raising or flicker'


def test_switching_to_chrome_does_not_recover_background_pair():
    api, overlay = editor_overlay(SakuraGuestOverlay)
    before = list(api.calls)
    api.foreground = CHROME
    for _ in range(10):
        overlay.sync()
    assert api.calls == before
    assert api.stack.index(CHROME) < api.stack.index(GUEST)


def test_popup_remains_ahead_of_guest_on_activation_edge():
    popup = 900
    class PopupDesktop(ClickDesktop):
        def IsWindow(self, hwnd):
            return hwnd == popup or super().IsWindow(hwnd)
    api = PopupDesktop()
    overlay = ObsidianImeOverlay(GUEST, HOST, user32=api)
    api.stack.insert(api.stack.index(GUEST), popup)
    api.exstyles[popup] = 0
    overlay.sync(popup_hwnds=(popup,))
    api.foreground = GUEST
    overlay.sync(popup_hwnds=(popup,))
    assert api.stack.index(popup) < api.stack.index(GUEST) < api.stack.index(LAUNCH)
    assert api.stack.index(LAUNCH) < api.stack.index(CHROME)
