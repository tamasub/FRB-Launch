from pathlib import Path
import importlib.util
import os
import time
import pytest

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('launch_release_build', ROOT / 'scripts/launch_release_build.py')
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)


@pytest.fixture
def root(tmp_path):
    (tmp_path / 'src').mkdir()
    (tmp_path / m.SOURCE).write_bytes(b'\xef\xbb\xbf# version\r\nAPP_VERSION = "0.9.14"\r\nAPP_NAME = "FRB"\r\n')
    (tmp_path / '_build_windows.bat').write_text('fake build')
    return tmp_path


def fake_build(root):
    exe = root / m.EXE
    exe.parent.mkdir(parents=True, exist_ok=True)
    exe.write_bytes(b'MZ test ' + (root / m.SOURCE).read_bytes())
    m.record(root)
    return 0


@pytest.mark.parametrize('target', ['0.9.15', '0.10.0', '1.0.0', '0.9.14'])
def test_version_written_before_build_and_preserves_other_bytes(root, target):
    before = (root / m.SOURCE).read_bytes()
    def runner(path):
        assert (path / m.SOURCE).read_bytes() == before.replace(b'0.9.14', target.encode())
        return fake_build(path)
    m.build(root, '0.9.14', target, runner)
    assert m.verify(root, target)['version'] == target


def test_keep_rebuild_does_not_rewrite_source(root):
    original = (root / m.SOURCE).stat().st_mtime_ns
    m.build(root, '0.9.14', '0.9.14', fake_build)
    assert (root / m.SOURCE).stat().st_mtime_ns == original


def test_failure_invalidates_old_receipt_and_retry_same_version(root):
    fake_build(root)
    def fails(path):
        assert not (path / m.RECEIPT).exists()
        return 1
    with pytest.raises(RuntimeError):
        m.build(root, '0.9.14', '0.9.15', fails)
    assert not (root / m.RECEIPT).exists()
    assert m.source_version((root / m.SOURCE).read_bytes())[0] == '0.9.15'
    m.build(root, '0.9.15', '0.9.15', fake_build)
    assert m.verify(root, '0.9.15')['version'] == '0.9.15'


def test_success_without_fresh_receipt_is_rejected(root):
    fake_build(root)
    with pytest.raises(FileNotFoundError):
        m.build(root, '0.9.14', '0.9.15', lambda _: 0)
    assert not (root / m.RECEIPT).exists()


@pytest.mark.parametrize('target,expected', [('0.9.13','0.9.14'), ('0.9.15','0.9.12'), ('bad','0.9.14')])
def test_invalid_or_stale_selection_does_not_touch_source(root, target, expected):
    before = (root / m.SOURCE).read_bytes()
    with pytest.raises(ValueError):
        m.build(root, expected, target, lambda _: pytest.fail('must not build'))
    assert (root / m.SOURCE).read_bytes() == before


@pytest.mark.parametrize('changed', [m.SOURCE, m.EXE])
def test_tampering_breaks_receipt(root, changed):
    fake_build(root)
    file = root / changed
    file.write_bytes(file.read_bytes() + b'\n# changed')
    with pytest.raises(ValueError):
        m.verify(root, '0.9.14')


def test_old_exe_cannot_be_recorded(root):
    fake_build(root)
    m.invalidate(root)
    os.utime(root / m.EXE, ns=(1,1))
    with pytest.raises(ValueError):
        m.record(root)
    assert not (root / m.RECEIPT).exists()


def test_ambiguous_version_rejected(root):
    p = root / m.SOURCE
    p.write_bytes(p.read_bytes() + b"APP_VERSION = '9.9.9'\n")
    with pytest.raises(ValueError):
        m.build(root, '0.9.14', '0.9.15', lambda _: pytest.fail('must not build'))


def test_bat_launches_original_build_and_gui_only_suppresses_interaction(monkeypatch, root):
    def fake_run(command, **kwargs):
        assert command[1:] == ['/d', '/c', '_build_windows.bat']
        assert kwargs['cwd'] == root
        assert kwargs['env']['FRB_GUI_BUILD'] == '1'
        assert kwargs['stdin'] == m.subprocess.DEVNULL
        return type('Result', (), {'returncode': 0})()
    monkeypatch.setattr(m.subprocess, 'run', fake_run)
    assert m.run_existing_bat(root) == 0
    bat = (ROOT / '_build_windows.bat').read_text()
    assert bat.index('del /f /q') < bat.index('checkpython')
    assert 'time.sleep(1)' in bat and 'timeout /t' not in bat
    assert bat.index('scripts\\launch_release_build.py record') > bat.index('portable_studio_ready.txt')
    assert bat.count('if not "%FRB_GUI_BUILD%"=="1" if not "%FRB_ENV_REFRESH%"=="1" pause') == 2


def test_gui_contract_versions_independent_and_publish_explicit():
    p = ROOT / '_★release_FRBLaunch_GUI.ps1'
    gui = p.read_text(encoding='utf-8-sig')
    assert 'NextVersion $script:LaunchBaseline $launchKind' in gui
    assert 'NextVersion $script:LatestRemote $kind' in gui
    assert '$script:launchKind.SelectedIndex=0' in gui
    assert '$script:launchKind.SelectedIndex=3' in gui
    assert "BeginJob 'BUILD'" in gui and "BeginJob 'PREPARE'" in gui
    assert 'Get-LaunchBuildReceipt $true' in gui
    assert '$plan.launch_version -cne $job.LaunchVersion' in gui
    assert '$script:PreparedBuildHash -cne $receipt.exe_sha256' in gui
    assert "' -PublishOnly -GuiApprovedTag " in gui
    assert "if ($answer -eq [System.Windows.Forms.DialogResult]::Yes) { BeginJob 'PUBLISH' }" in gui
    assert p.read_bytes().startswith(b'\xef\xbb\xbf')
    assert p.read_bytes().count(b'\r\n') == p.read_bytes().count(b'\n')
