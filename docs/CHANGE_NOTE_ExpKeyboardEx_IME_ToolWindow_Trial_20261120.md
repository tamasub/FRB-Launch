# Exp Keyboard Ex — Windows Japanese IME Qt.Tool comparison (trial only)

## Evidence

Observed trace supplied by user (2026-11-20 23:21 JST):
- Existing CascadeMenu: `active=RemoteFolderCascade`, native `InputMethod preedit_len=1,2,3` followed by `commit_len=3`.
- Exp Keyboard Ex: `focus=SlashSearchEdit`, `popup=SlashExpMenu`, but `active=Launcher`; repeated `KeyPress key=0` / `key=65` without `InputMethod` or `InputMethodQuery`.

Therefore the text editor focus works but the native IME connection is not behaving like the working CascadeMenu. Qt.Popup versus active Qt.Tool is a **hypothesis**, not yet a verified root cause.

## Controlled trial

**Normal Launch behavior is unchanged.** Only the new diagnostic BAT sets `FRB_SLASH_IME_TOOL_WINDOW=1`; that makes SlashExpMenu an activated `Qt.Tool` (same window style as working CascadeMenu) instead of a `Qt.Popup`.

1. Apply this delta onto the previous `FRBLaunch_ExpKeyboardEx_IMETrace_TopMargin_20261120_diff.zip` version.
2. Completely exit all FRB Launch instances including tray.
3. Run `diagnose_exp_keyboard_ime_tool_trial.bat` from the launch root.
4. Open `/`, focus the search field, switch to Japanese IME, type Hiragana, convert and confirm.
5. Check `/` toggle, Right/Left, Enter, click outside and normal folder navigation. Since Qt.Tool is not a native grabbing popup, outside-click dismissal **may differ in this trial**.
6. Exit Launch, and attach `%TEMP%\FRBLaunch\exp_keyboard_ime_tool_trial.log`.

An `InputMethod`/`commit_len` sequence for `slash.edit` would support the hypothesis. If no such event arrives, compare active window and focus snapshots and revert the trial by starting normally.

## Files
- `src/slash_exp_navigation.py` — opt-in Qt.Tool window flag and activateWindow()
- `diagnose_exp_keyboard_ime_tool_trial.bat` — separate test launcher/log
- `tests/test_slash_ime_tool_window_trial_20261120.py` — static guard tests

## Limits
- Not an IME fix verified on Windows: this runtime has no PySide6 and no Windows IME.
- No change to palette, border, geometry, search logic, or normal Qt.Popup path.
