# FRB Launch – Exp Keyboard Ex: Menu key / operation popup anchor

Date: 2026-11-20
Base ZIP: `launch_app_20261120_235012.zip`

## Purpose

1. Place the operation context menu opened with Right close to the **visible**
   folder/file caption, with a comfortable 28px trailing gap. Do not make a
   wide List row or a fixed-width exploration column dictate its horizontal
   position. Keep existing folder-to-folder cascade placement unchanged.
2. In **Exp Keyboard Ex** and **Files List**, route the physical Windows Menu
   (Application) key through the **already-approved Right-arrow path**. On a
   terminal item, that path opens Copy/Paste/etc.; on a navigable folder
   branch, Right still explores the branch. Do not run a distinct right-click
   handler or change the current Exp/List item.
3. Windows can dispatch either `Key_Menu` or a keyboard-generated
   `QContextMenuEvent`; handle both. Preserve ordinary *mouse* right-click
   behavior and Japanese IME composition.

## Changed files

- `src/slash_exp_navigation.py`
  - Context command columns anchor near the rendered caption (both regular
    and scroll view); folder browsing children still use existing placement.
  - Menu-key KeyPress and keyboard ContextMenu fallback call the same Right
    dispatch, including the inline search/scroll viewport event paths.
- `src/app.py`
  - Files List Menu key aliases the existing Right dispatcher.
  - The Files List operation popup position is computed from the Name
    column's actual visible caption, with hit-test-safe fallback.
- `src/expanded_view.py`
  - Keyboard-origin ContextMenu events on Files List reuse the exact existing
    `Launcher.expanded_tree_key()` Right route.
- `tests/test_slash_exp_navigation_20261118.py`
  - Update one expected popup-position test to the newly agreed caption anchor.
- `tests/test_slash_menu_key_and_operations_anchor_20261120.py`
  - Add Menu/Right parity, no unintended navigation, Japanese IME protection,
    caption positioning, scroll viewport and native ContextMenu tests.

## Verification

- Python syntax / compile: PASS.
- Focused tests (new + Slash navigation): 56 PASS.
- Broad Slash/Files context suite: 129 PASS; 7 older failures.
- All 7 broad failures also occur on the original ZIP. No additional failures.
- Windows 11 actual GUI interaction: not tested here.

## Windows manual acceptance

1. Open Files List item `src` (or another short caption), press Right, verify
   Copy/Paste operation menu starts just to the right of the visible caption.
2. Press the physical keyboard Menu key on that same List terminal item;
   verify the **same** operation menu appears without jumping to Files Exp.
3. From `/` Keyboard Ex, select a terminal file, press Right then Menu on a
   separate attempt; the same action column should appear. Folder branches
   should keep existing Right navigation.
4. Confirm `/`, Left/Right, Enter, IME conversion, click-away and normal mouse
   right-click still work.
