"""Pure origin protection plus static wiring checks; Windows GUI acceptance remains manual."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_history():
    spec = importlib.util.spec_from_file_location(
        'third_folder_history', ROOT / 'src/third_column_folder_history.py')
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.ThirdColumnFolderHistory()


def test_origin_history_independent_of_files_list_location():
    history = load_history()
    assert history.candidates() == ()
    assert history.remember('vscode', r'F:\FRB\A\01.md')
    assert history.candidates() == (r'F:\FRB\A',)
    assert history.remember('vscode', r'F:\FRB\B\02.md')
    assert history.candidates() == (r'F:\FRB\B', r'F:\FRB\A')
    assert history.remember('vscode', r'f:\frb\a\03.txt')
    assert len(history.candidates()) == 2
    assert history.candidates()[0].casefold() == r'f:\frb\a'
    assert history.remember('studio', r'F:\FRB\json\config.json')
    assert history.candidates() == (r'F:\FRB\json',)
    history.activate('vscode')
    assert len(history.candidates()) == 2
    history.clear_active()
    assert history.candidates() == ()
    assert not history.remember('browser', 'https://example.com/')
    assert history.candidates() == ()


def test_third_column_folder_action_is_only_explicit_list_navigation():
    source = (ROOT / 'src/expanded_view.py').read_text(encoding='utf-8')
    # File preview records origins but only explicit folder action navigates.
    remember = source[source.index('    def _remember_third_column_file('):
                      source.index('    def _open_third_column_folder(')]
    assert 'go_to_directory(' not in remember
    jump = source[source.index('    def _open_third_column_folder('):
                  source.index('    def show_third_column_file_folder(')]
    assert 'self.go_to_directory(folder)' in jump
    assert 'direct_anchor=True' not in jump
    assert 'panel.folder_button' in source
    assert 'show_third_column_file_folder' in source
    studio = (ROOT / 'src/studio_preview_panel.py').read_text(encoding='utf-8')
    assert 'self.folder_requested.emit' in studio
    assert 'self.folder_button' in studio
    assert 'QSize(25, 25)' in studio


def test_grigri_owns_clicks_above_exp_list_not_translucent():
    remote = (ROOT / 'src/launch_remote.py').read_text(encoding='utf-8')
    start = remote.index('class RoundRailWheelPad(')
    end = remote.index('class RemoteWheelButton(', start)
    wheel = remote[start:end]
    assert 'WA_TranslucentBackground, False' in wheel
    assert 'WA_TransparentForMouseEvents, False' in wheel
    expanded = (ROOT / 'src/expanded_view.py').read_text(encoding='utf-8')
    assert 'def _guard_rail_underlay_click(' in expanded
    assert 'if self._guard_rail_underlay_click(obj, event):' in expanded
    assert 'QEvent.Type.MouseButtonDblClick' in expanded
