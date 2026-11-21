# FRB Launch / Exp Keyboard Ex — Japanese IME permanent fix (2026-11-20)

## Base
`launch_app_20261120_233708.zip` (user supplied, latest version).

## Evidence and decision
The first Windows diagnostic trace showed that native Qt.Popup kept `active=Launcher` despite search-editor focus, and no `InputMethod preedit/commit` events arrived. The Windows A/B Tool trial showed `active=SlashExpMenu` plus native `preedit_len=1,2,3`, `commit_len=3` on the search editor. The user confirmed Japanese input worked in the trial.

**Decision:** use an activated `Qt.Tool` for every Exp Keyboard Ex column in the normal runtime; the experiment flag is removed. The existing native IME event forwarding to the embedded `SlashSearchEdit` remains in place. Do not synthesize Japanese text as key events.

## Changes
- `src/slash_exp_navigation.py`
  - `SlashExpMenu` always uses `Qt.Tool | FramelessWindowHint | WindowStaysOnTopHint`; calls `activateWindow()` when focusing for IME.
  - Restores Popup-style click-away dismissal with a root-session-only QObject event filter. Clicks within any Slash column/search widget don't close; clicks outside do, and the target still gets its click.
  - On application deactivation, closes the root after a short deferred check, but does not close while an IME composition is active.
  - On root hide, closes visible child Tool columns and unregisters the temporary filter and app-state callback, so no stale input handler survives the session.
  - No change to breadcrumb navigation, menu width, theme, icon spacing, rounded borders or folder-enter focus logic.
- `diagnose_exp_keyboard_ime_tool_trial.bat`: legacy filename retained for existing shortcuts; now **trace-only**; normal Launch is already Tool mode. Existing `diagnose_exp_keyboard_ime.bat` still works.
- `tests/test_slash_ime_production_tool_20261120.py`: production activated Tool, slash toggling, click inside/outside, external deactivation and active IME composition guards.
- `tests/test_slash_ime_tool_window_trial_20261120.py`: updated contract from experimental flag to permanent behavior.
- `tests/test_slash_exp_navigation_20261118.py`: minimal Qt stubs updated for production Tool lifecycle testing.

## Verification
- Python syntax check PASS.
- Focused behavioral tests: 55 PASS.
- Broad slash/ExpandedView regression: 115 PASS, 11 FAIL. The **same 11 fail with the unchanged base ZIP**: known obsolete palette/geometry expectations and unrelated pre-existing source assumptions. No new failure.
- This environment lacks PySide6 + Windows Japanese IME; therefore native GUI behavior of the **permanent** path still needs user acceptance testing. The exact `Qt.Tool` activation/IME path was validated by the user in the earlier Windows A/B trial.

## Windows acceptance checklist
1. Fully exit Launch, including tray icon. Use normal `_run_windows.bat` (no special diagnostic BAT).
2. `/` -> select search -> Japanese composition/conversion/commit works.
3. `/` closes; arrows traverse columns; Enter on folder moves focus to Files List first row.
4. Click a row/search inside any menu column: menu remains; click Launch outside the menu: closes; switch to another Windows app: closes.
5. Verify IME candidate selection is not prematurely dismissed.

**Rollback:** Restore `src/slash_exp_navigation.py` from the base ZIP. No data or config migrations.
