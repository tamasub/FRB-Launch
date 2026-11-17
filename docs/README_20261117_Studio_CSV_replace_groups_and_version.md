# FRB Studio CSV `replace_groups` + Studio version metadata (2026-11-17)

## Scope

- Source baseline: `FRBStudio_App20261117_102114.zip` and `launch_app_20261117_101424.zip`
- Studio `CsvGridImporter` supports both `replace_all` (unchanged) and `replace_groups` (new).
- The Launch maintenance `launch_choices_view` declares `mode: "replace_groups"` and `groupField: "group_id"` in both the Launch-owned ViewDef and the Studio source mirror.
- Studio version is defined in **Studio/defs/app_version.json**, with `app_name: "FRB Studio"` and `app_version: "0.9.0"` initially.
- Launch version/update dialog reads the Studio version file. Only if unavailable does it display the installed release manifest value marked `（配布記録）`.

## CSV contract

`toolbar.csvImport` declares `mode`, `groupField`, `columns`, `requiredField`, `idField`, `idPrefix`, `orderField`, and defaults. Runtime never hardcodes a business group name.

`replace_groups` requires a nonblank group value for every CSV data row, and the group column must be present. A CSV referencing groups `sales` and `se` replaces only those two groups; all other groups retain their original rows, IDs, order and data. Each replaced group is inserted at its first original position; previously absent groups are appended.

CSV inputs are fully parsed and validated **before** replacing any rows. The confirmation dialog previews counts for each affected group (up to 15 displayed, with a remainder count), plus total deleted/added counts. Cancel leaves the original array unchanged; parent Studio Save is still required to persist. If rendering fails, the in-memory array is restored. Generated `choice_id` values skip IDs held by untouched groups. Unlike `replace_all`, `replace_groups` will reject CSV without a group column; Google Contacts CSV therefore needs to be augmented with `group_id` before group import.

## Version ownership

To bump Studio's reported version, change **Studio/defs/app_version.json**. This file is within Studio's `defs/` folder, which the existing portable/update packager includes in the System payload. The runtime version display prefers a Launch-configured Studio root, then a portable `Studio/` folder, then the independent sibling `FRB_Studio/`. Installed `release.json` remains the authoritative record for package update decisions; the Studio metadata is for display and need not change update semantics.

Launch's own `src/app_version.py` is **not** modified by this patch; its source-baseline `APP_VERSION` remains `0.9.3`. Change that file under the existing release process when intentionally advancing the Launch version.

## Regression tests

- Studio (Node): `node --test tests/qa/static/related_grid_csv_import_20261016.test.mjs tests/qa/static/related_grid_csv_replace_groups_20261117.test.mjs`
- Launch (Python): `python -m pytest tests/test_studio_version_info_20261117.py -q`
- Real attached 41-row CSV: selective `sales` (5) and `se` (4) replacement left 32 untouched emoji rows and retained unique IDs.

Windows GUI/actual save/relaunch were not exercised in this Linux validation environment.
