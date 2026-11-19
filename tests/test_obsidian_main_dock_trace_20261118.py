"""Safe diagnostic contract, Linux-friendly; no real Windows HWND is touched."""
import json
from pathlib import Path
from types import SimpleNamespace

import obsidian_dock_trace as report
from obsidian_dock_bridge import cli_eval


def test_trace_is_structured_and_omits_original_window_title(tmp_path, monkeypatch):
    monkeypatch.setattr(report, 'log_path', lambda: tmp_path / report.LOG_NAME)
    private_title = '非公開の研究ノート - Obsidian'
    report.trace('CAPTION_MATCH', expected_hash=report.fingerprint(private_title),
                 expected_length=len(private_title))
    result = (tmp_path / report.LOG_NAME).read_text(encoding='utf-8')
    item = json.loads(result)
    assert item['event'] == 'CAPTION_MATCH'
    assert item['expected_hash'] == report.fingerprint(private_title)
    assert private_title not in result


def test_cli_trace_never_logs_code_vault_or_raw_stdout(tmp_path, monkeypatch):
    monkeypatch.setattr(report, 'log_path', lambda: tmp_path / report.LOG_NAME)
    secret_path = 'C:/Private Vault/Confidential Project.md'
    secret_code = "console.log('" + secret_path + "')"
    def runner(*args, **kwargs):
        assert 'vault=private-vault-id' in args[0]
        return SimpleNamespace(returncode=0, stdout='noise\n=> FRB_MAIN_TITLE:Main%20Vault\n',
                               stderr='ignored diagnostic mentioning ' + secret_path)
    assert cli_eval('private-vault-id', secret_code,
                    executable='C:/Obsidian.com', runner=runner,
                    stage='main_probe') == 'FRB_MAIN_TITLE:Main%20Vault'
    entry = (tmp_path / report.LOG_NAME).read_text(encoding='utf-8')
    obj = json.loads(entry)
    assert obj['event'] == 'CLI_RESULT' and obj['stage'] == 'main_probe'
    assert obj['returncode'] == 0 and obj['reason'] == 'main_title'
    assert obj['stdout_line_count'] == 2
    assert obj['protocol_tags'] == [[], ['FRB_MAIN_TITLE']]
    assert secret_path not in entry and secret_code not in entry
    assert 'private-vault-id' not in entry and 'Main%20Vault' not in entry


def test_cli_failure_logs_reason_without_raw_stdout(tmp_path, monkeypatch):
    monkeypatch.setattr(report, 'log_path', lambda: tmp_path / report.LOG_NAME)
    def runner(*args, **kwargs):
        return SimpleNamespace(returncode=1,
                               stdout='file=C:/something-private.md\n',
                               stderr='permission failed')
    assert cli_eval('test', 'secret', executable='C:/Obsidian.com',
                    runner=runner, stage='bind') == 'FRB_CLI_FAILED'
    entry = (tmp_path / report.LOG_NAME).read_text(encoding='utf-8')
    assert json.loads(entry)['reason'] == 'nonzero_returncode'
    assert 'something-private' not in entry and 'permission failed' not in entry


def test_trace_rollover_bounds_growth(tmp_path, monkeypatch):
    monkeypatch.setattr(report, 'log_path', lambda: tmp_path / report.LOG_NAME)
    monkeypatch.setattr(report, 'MAX_BYTES', 20)
    report.trace('START')
    report.trace('NEXT')
    assert (tmp_path / (report.LOG_NAME + '.old')).is_file()
    assert json.loads((tmp_path / report.LOG_NAME).read_text(encoding='utf-8'))['event'] == 'NEXT'


def test_non_windows_trace_windows_is_read_only_and_noop(tmp_path, monkeypatch):
    import os
    if os.name != 'nt':
        monkeypatch.setattr(report, 'log_path', lambda: tmp_path / report.LOG_NAME)
        report.trace_windows('noop', expected_caption='private')
        assert not (tmp_path / report.LOG_NAME).exists()


def test_contract_avoids_guessing_or_popout_after_probe_failure():
    source = (Path(__file__).resolve().parents[1] / 'src' / 'studio_preview_panel.py').read_text(encoding='utf-8')
    main = source.split('    def _on_obsidian_main_probe_completed(', 1)[1].split('    def _reset_obsidian_cli(', 1)[0]
    assert "main_window_matches_caption(caption, windows)" in main
    assert 'trace_windows(\'caption_match\', expected_caption=caption)' in main
    assert 'paneType=window' not in main
    assert 'os.startfile' not in main
