"""Studio third-column contract: physical .md / managed .json only.

The live Windows cross-process HWND attachment needs manual GUI validation;
these tests intentionally make no claim of verifying WebView2/save on Linux.
"""
import json
from pathlib import Path

from studio_preview_route import studio_preview_target, studio_start_command


def environment(tmp_path):
    studio = tmp_path / 'FRB Studio'
    executable = studio / 'NativeShell' / '_publish' / 'FRBStudio.NativeShell.exe'
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b'fixture')
    (studio / 'defs' / 'rules').mkdir(parents=True)
    (studio / 'defs' / 'rules' / 'my_view.json').write_text('{}', encoding='utf-8')
    folder = tmp_path / 'work with space'
    folder.mkdir()
    md = folder / 'メモ FRB.md'
    md.write_text('# FRB\n', encoding='utf-8')
    good_json = folder / '作業データ.json'
    good_json.write_text(json.dumps({'view_def': 'rules/my_view.json', 'items': []}), encoding='utf-8')
    return studio, executable, md, good_json


def test_md_file_list_leaf_is_eligible(tmp_path):
    studio, executable, md, _ = environment(tmp_path)
    result = studio_preview_target({'_browse_file': str(md)}, studio)
    assert result == (str(md), str(executable), str(studio))
    command, cwd = studio_start_command(result)
    assert command == [str(executable), '--open-md=' + str(md)]
    assert cwd == str(studio)


def test_indexed_studio_managed_json_is_eligible(tmp_path):
    studio, executable, _, document = environment(tmp_path)
    target = studio_preview_target({'_indexed_file': str(document)}, studio)
    assert target == (str(document), str(executable), str(studio))
    assert studio_start_command(target)[0][1] == '--open-json=' + str(document)


def test_json_without_viewdef_does_not_steal_normal_open(tmp_path):
    studio, _, _, doc = environment(tmp_path)
    doc.write_text('{"memo":"unchanged"}', encoding='utf-8')
    assert studio_preview_target({'_browse_file': str(doc)}, studio) is None


def test_non_file_and_virtual_launch_row_do_not_intercept(tmp_path):
    studio, _, md, _ = environment(tmp_path)
    assert studio_preview_target({'_browse_file': str(md), '_launch_virtual_node': {'kind':'file'}}, studio) is None
    assert studio_preview_target({'launch_actions': [{'launch_action_type': 'Run'}]}, studio) is None
    assert studio_preview_target({'_browse_file': str(md.parent)}, studio) is None


def test_missing_studio_executable_preserves_original_doubleclick(tmp_path):
    studio, executable, md, _ = environment(tmp_path)
    executable.unlink()
    assert studio_preview_target({'_browse_file': str(md)}, studio) is None


def test_non_markdown_files_are_not_previewed(tmp_path):
    studio, _, md, _ = environment(tmp_path)
    html = md.with_suffix('.html')
    html.write_text('<p>safe</p>', encoding='utf-8')
    assert studio_preview_target({'_browse_file': str(html)}, studio) is None


def test_only_physical_path_used_not_title_or_url(tmp_path):
    studio, _, md, _ = environment(tmp_path)
    assert studio_preview_target({'title': str(md)}, studio) is None
    assert studio_preview_target({'launch_target': str(md)}, studio) is None


def test_does_not_modify_document_bytes(tmp_path):
    studio, _, md, doc = environment(tmp_path)
    before_md, before_json = md.read_bytes(), doc.read_bytes()
    studio_preview_target({'_browse_file': str(md)}, studio)
    studio_preview_target({'_browse_file': str(doc)}, studio)
    assert (md.read_bytes(), doc.read_bytes()) == (before_md, before_json)


def test_ui_integration_has_explicit_undock_and_quit_guard():
    src = Path(__file__).resolve().parents[1] / 'src'
    view = (src / 'expanded_view.py').read_text(encoding='utf-8')
    panel = (src / 'studio_preview_panel.py').read_text(encoding='utf-8')
    app = (src / 'app.py').read_text(encoding='utf-8')
    assert 'return self.show_studio_preview(target)' in view
    assert 'self.close_studio_preview' in view
    assert 'panel.hide()' in view  # × now hides without undocking; exit still undocks
    assert 'self.studio_preview.undock()' in view
    assert 'release_studio_preview()' in app
    assert 'terminate(' not in panel and '.kill(' not in panel
    assert 'window.close(' not in panel


def test_external_process_child_inside_launch_does_not_trigger_outside_click():
    import ctypes
    from ctypes import wintypes
    from desktop_double_click import DesktopDoubleClick

    class Win32:
        def __init__(self, parents):
            self.parents = parents
        def WindowFromPoint(self, _point):
            return 90
        def GetWindowThreadProcessId(self, handle, pointer):
            ctypes.cast(pointer, ctypes.POINTER(wintypes.DWORD)).contents.value = (
                200 if handle == 90 else 100)
            return 1
        def GetParent(self, hwnd):
            return self.parents.get(hwnd, 0)

    detector = DesktopDoubleClick.__new__(DesktopDoubleClick)
    detector.process_id = 100
    detector.user = Win32({90: 80, 80: 70})
    assert detector._outside_own_process(object()) is False  # C# child -> Qt parent
    detector.user = Win32({})
    assert detector._outside_own_process(object()) is True   # external browser
