"""Windows-only proof: rename a temporary .txt and resolve it from JSON data.

No .lnk files are written. Does not modify the user's Launch config or files.
"""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from shell_link_stream import make_link_data, resolve_link_data, ShellLinkError


def main():
    if os.name != 'nt':
        print('Windows専用の試験です')
        return 2
    try:
        with tempfile.TemporaryDirectory(prefix='FRBLaunch_shell_link_trial_') as tmp:
            before = Path(tmp) / '変更前_テスト.txt'
            after = Path(tmp) / '変更後_テスト.txt'
            before.write_text('Shell Link stream trial', encoding='utf-8')
            data = make_link_data(before)
            # Verify that only an in-memory string exists. It is JSON-safe.
            encoded = json.dumps({'launch_shell_link_data': data}, ensure_ascii=False)
            loaded = json.loads(encoded)['launch_shell_link_data']
            before.rename(after)
            resolved, updated = resolve_link_data(loaded)
            correct = os.path.samefile(resolved, after)
            no_lnk = not list(Path(tmp).glob('*.lnk'))
            print('変更前:', before.name)
            print('変更後:', after.name)
            print('解決先:', Path(resolved).name)
            print('JSON bytes:', len(encoded.encode('utf-8')))
            print('実体.lnkなし:', no_lnk)
            print('一致:', correct)
            if correct and no_lnk and updated:
                print('PASS: .lnkファイルなしで名前変更追跡成功')
                return 0
            print('FAIL: 追跡結果を確認してください')
            return 1
    except (ShellLinkError, OSError) as exc:
        print('FAIL:', exc)
        return 1


if __name__ == '__main__':
    sys.exit(main())
