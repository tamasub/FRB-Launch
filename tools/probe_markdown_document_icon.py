r"""Read-only Windows .md document icon probe (optional PNG preview).

Run from the Launch folder:
    .venv\Scripts\python.exe tools\probe_markdown_document_icon.py
    .venv\Scripts\python.exe tools\probe_markdown_document_icon.py --file "F:\\Notes\\memo.md" --png
"""
import argparse
import os
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))


def main():
    parser = argparse.ArgumentParser(description='Windowsの.md関連付けアイコンを表示専用で診断')
    parser.add_argument('--file', default='', help='実在する.mdのパス（任意）')
    parser.add_argument('--png', action='store_true', help='比較用PNGを作業フォルダーに保存する')
    args = parser.parse_args()
    if os.name != 'nt':
        print('SKIP: Windows専用です（変更なし）')
        return 0

    from windows_file_association_icon import (
        _query_association_string, _ASSOCSTR_DEFAULTICON,
        _ASSOCSTR_EXECUTABLE, _split_icon_reference, _resource_icon,
        _shell_icon, file_type_icon,
    )
    print('=== FRB Launch .md icon probe (read-only) ===')
    default = _query_association_string('.md', _ASSOCSTR_DEFAULTICON)
    executable = _query_association_string('.md', _ASSOCSTR_EXECUTABLE)
    print('Windows .md DefaultIcon :', default or '(not registered)')
    print('Windows .md executable  :', executable or '(not registered)')
    print('Parsed icon resource    :', _split_icon_reference(default) if default else None)
    print('Real .md path           :', args.file or '(not supplied)')
    print('No registry or configuration writes; no editor launches.')

    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    attempts = {
        'registered_document': (lambda: _resource_icon(default, 16) if default else None),
        'real_file': (lambda: _shell_icon(args.file, False, 16) if args.file else None),
        'associated_app': (lambda: _shell_icon(executable, False, 16) if executable else None),
        'extension_fallback': (lambda: _shell_icon('.md', True, 16)),
        'Launch_effective': (lambda: file_type_icon('.md', file_path=args.file)),
    }
    for label, callback in attempts.items():
        try:
            icon = callback()
            valid = bool(icon is not None and not icon.isNull())
            print(f'{label:22}: {"OK" if valid else "unavailable"}')
            if valid and args.png:
                path = Path.cwd() / f'FRBLaunch_md_icon_{label}.png'
                ok = icon.pixmap(64, 64).save(str(path), 'PNG')
                print('  PNG:', path if ok else '(save failed)')
        except Exception as exc:
            print(f'{label:22}: ERROR ({type(exc).__name__}: {exc})')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
