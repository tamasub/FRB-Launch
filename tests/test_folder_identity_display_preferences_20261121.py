"""ID-keyed Files List width/order/sort, migration, and Keyboard Ex parity.

Qt-free coverage. Windows desktop resizing must still be smoke-tested in Launch.
"""
import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from folder_identity_preferences import (folder_identity_token,
                                         path_fallback_token)
from folder_header_preferences import (apply_header_layout, capture_header_layout,
                                       header_layout_key, load_header_layout,
                                       save_header_layout)
from folder_sort_preferences import (DEFAULT_SORT, directory_sort_key,
                                     legacy_directory_sort_key,
                                     load_directory_sort, save_directory_sort,
                                     transfer_directory_sort)
from folder_popup_sort import sort_physical_popup_records
from middle_folder_filter import SORT_LABELS


class Settings:
    def __init__(self):
        self.data = {}

    def value(self, key, default=None):
        return self.data.get(key, default)

    def setValue(self, key, value):
        self.data[key] = value

    def remove(self, key):
        self.data.pop(key, None)

    def sync(self):
        pass


class FakeHeader:
    def __init__(self, widths=(300, 156, 98, 150, 60)):
        self.widths = list(widths)
        self.visual = [0, 1, 2, 3, 4]

    def sectionSize(self, logical):
        return self.widths[logical]

    def logicalIndex(self, visual):
        return self.visual[visual]

    def visualIndex(self, logical):
        return self.visual.index(logical)

    def resizeSection(self, logical, width):
        self.widths[logical] = width

    def moveSection(self, old_visual, new_visual):
        self.visual.insert(new_visual, self.visual.pop(old_visual))


def test_id_survives_folder_rename_and_move_and_is_not_a_path_hash(tmp_path):
    folder = tmp_path / 'old'
    folder.mkdir()
    before = folder_identity_token(folder)
    assert before.startswith('id-')
    assert before != path_fallback_token(folder)
    assert directory_sort_key(folder).endswith(before)
    renamed = folder.rename(tmp_path / 'renamed')
    assert folder_identity_token(renamed) == before
    new_parent = tmp_path / 'other'
    new_parent.mkdir()
    moved = renamed.rename(new_parent / 'moved')
    assert folder_identity_token(moved) == before
    assert header_layout_key(moved).endswith(before)


def test_id_keyed_sort_and_header_move_as_one_folder_preference(tmp_path):
    settings = Settings()
    folder = tmp_path / 'foo'
    folder.mkdir()
    other = tmp_path / 'bar'; other.mkdir()
    original_header = FakeHeader()
    baseline = capture_header_layout(original_header)
    customized = {'widths': [520, 156, 98, 150], 'order': [1, 0, 2, 3, 4]}
    assert save_header_layout(settings, header_layout_key(folder), customized, baseline)
    save_directory_sort(settings, folder, 'date_desc', SORT_LABELS)
    assert load_header_layout(settings, header_layout_key(other), baseline) == baseline
    assert load_directory_sort(settings, other, SORT_LABELS) == DEFAULT_SORT
    moved = folder.rename(tmp_path / 'renamed')
    assert load_header_layout(settings, header_layout_key(moved), baseline) == customized
    assert load_directory_sort(settings, moved, SORT_LABELS) == 'date_desc'
    assert all('id-' in key for key in settings.data)


def test_header_restore_preserves_spacer_width_and_column_order():
    target = FakeHeader(widths=(300, 156, 98, 150, 444))
    wanted = {'widths': [700, 210, 98, 150], 'order': [3, 1, 0, 2, 4]}
    assert apply_header_layout(target, wanted)
    assert capture_header_layout(target) == wanted
    assert target.sectionSize(4) == 444  # never hard-code stretch width
    assert apply_header_layout(target, {'widths': [300, 156, 98, 150],
                                         'order': [0, 1, 2, 3, 4]})
    assert target.visual == [0, 1, 2, 3, 4]


def test_header_only_custom_values_saved_and_default_removes_override(tmp_path):
    settings = Settings()
    folder = tmp_path / 'folder'; folder.mkdir()
    key = header_layout_key(folder)
    baseline = capture_header_layout(FakeHeader())
    assert save_header_layout(settings, key, baseline, baseline)
    assert settings.data == {}
    special = {'widths': [450, 156, 98, 150], 'order': [0, 2, 1, 3, 4]}
    save_header_layout(settings, key, special, baseline)
    assert json.loads(settings.data[key]) == special
    assert load_header_layout(settings, key, baseline) == special
    save_header_layout(settings, key, baseline, baseline)
    assert settings.data == {}


def test_header_rejects_corrupted_settings_and_does_not_touch_ui(tmp_path):
    settings = Settings()
    folder = tmp_path / 'folder'; folder.mkdir()
    baseline = capture_header_layout(FakeHeader())
    key = header_layout_key(folder)
    for bad in ('not json', '{"widths":[0,1,2,3],"order":[0,1,2,3,4]}',
                '{"widths":[300,156,98,150],"order":[0,0,2,3,4]}'):
        settings.setValue(key, bad)
        assert load_header_layout(settings, key, baseline) == baseline
    assert not apply_header_layout(FakeHeader(), {'widths': [], 'order': []})


def test_existing_path_sort_lazily_migrates_to_identity(tmp_path):
    settings = Settings()
    folder = tmp_path / 'folder'; folder.mkdir()
    old = legacy_directory_sort_key(folder)
    settings.setValue(old, 'size_desc')
    assert load_directory_sort(settings, folder, SORT_LABELS) == 'size_desc'
    assert old not in settings.data
    assert settings.data[directory_sort_key(folder)] == 'size_desc'
    destination = folder.rename(tmp_path / 'new-name')
    assert load_directory_sort(settings, destination, SORT_LABELS) == 'size_desc'


def test_folder_rename_transfer_legacy_path_state(tmp_path):
    settings = Settings()
    folder = tmp_path / 'original'; folder.mkdir()
    save_directory_sort(settings, folder, 'date_asc', SORT_LABELS)
    new = folder.rename(tmp_path / 'new')
    # New ID-based preference already follows, no transfer needed.
    assert load_directory_sort(settings, new, SORT_LABELS) == 'date_asc'
    assert transfer_directory_sort(settings, folder, new, SORT_LABELS)
    assert load_directory_sort(settings, new, SORT_LABELS) == 'date_asc'


def test_id_unavailable_falls_back_to_normalized_path(monkeypatch):
    import folder_identity_preferences as mod
    monkeypatch.setattr(mod.os, 'stat', lambda path: (_ for _ in ()).throw(OSError('offline')))
    assert mod.folder_identity_token('F:/FRB/Test') == mod.folder_identity_token(r'f:\frb\test')
    assert mod.folder_identity_token('F:/FRB/Test').startswith('path-')
    assert mod.folder_identity_token(None) is None


def test_physically_different_folders_have_different_keys(tmp_path):
    a = tmp_path / 'A'; b = tmp_path / 'B'
    a.mkdir(); b.mkdir()
    assert folder_identity_token(a) != folder_identity_token(b)


def test_keyboard_popup_order_uses_same_sort_as_list(tmp_path):
    directory = tmp_path / 'directory'; directory.mkdir()
    zdir = directory / 'z_directory'; zdir.mkdir()
    adir = directory / 'a_directory'; adir.mkdir()
    zfile = directory / 'z.txt'; zfile.write_text('a')
    afile = directory / 'a.txt'; afile.write_text('b')
    os.utime(zfile, (100, 100)); os.utime(afile, (200, 200))
    records = [(True, str(zdir), 'z_directory', 'dir Z'),
               (True, str(adir), 'a_directory', 'dir A'),
               (False, str(zfile), 'z.txt', 'file Z'),
               (False, str(afile), 'a.txt', 'file A')]
    assert sort_physical_popup_records(records, 'name') == [
        'dir A', 'dir Z', 'file A', 'file Z']
    assert sort_physical_popup_records(records, 'name_desc') == [
        'dir Z', 'dir A', 'file Z', 'file A']
    # Files List always groups folders first; file dates still sort reliably.
    assert sort_physical_popup_records(records, 'date_desc')[-2:] == [
        'file A', 'file Z']


def test_identity_lookup_uses_only_one_stat_for_opened_folder(tmp_path, monkeypatch):
    import folder_identity_preferences as mod
    folder = tmp_path / 'one'; folder.mkdir()
    original = mod.os.stat
    calls = []
    def measure(path, *args, **kwargs):
        calls.append(path)
        return original(path, *args, **kwargs)
    monkeypatch.setattr(mod.os, 'stat', measure)
    assert mod.folder_identity_token(folder).startswith('id-')
    assert calls == [folder]


def test_actual_expanded_view_restore_and_save_methods_use_cached_identity(tmp_path):
    """Exercise the real methods via AST without importing the whole Qt UI."""
    import ast
    import textwrap
    from folder_header_preferences import (apply_header_layout,
        capture_header_layout, header_layout_key, load_header_layout,
        save_header_layout)
    source = (Path(__file__).resolve().parents[1] / 'src' / 'expanded_view.py').read_text('utf-8')
    classes = [node for node in ast.parse(source).body if isinstance(node, ast.ClassDef)]
    found = {}
    for cls in classes:
        for method in cls.body:
            if isinstance(method, ast.FunctionDef) and method.name in (
                    '_save_middle_header_state', '_restore_middle_header_for_directory'):
                found[method.name] = method
    assert len(found) == 2
    class FakeTimer:
        @staticmethod
        def singleShot(_duration, callback):
            callback()

    namespace = dict(QTimer=FakeTimer, apply_header_layout=apply_header_layout,
                     capture_header_layout=capture_header_layout,
                     header_layout_key=header_layout_key,
                     load_header_layout=load_header_layout,
                     save_header_layout=save_header_layout)
    for name, method in found.items():
        exec(textwrap.dedent(ast.get_source_segment(source, method)), namespace)
    header = FakeHeader()
    settings = Settings()
    folder = tmp_path / 'folder'; folder.mkdir()
    other = tmp_path / 'other'; other.mkdir()
    obj = SimpleNamespace(_middle_header_restoring=False,
        _middle_header_virtual=False, _middle_header_mouse_down=False,
        _preview_maximized=False,
        _middle_header_baseline=capture_header_layout(header),
        _middle_header_layout_directory=None, _middle_header_layout_key=None,
        _middle_header_last_saved_layout=None,
        middle=SimpleNamespace(tree=SimpleNamespace(header=lambda: header)),
        launcher=SimpleNamespace(settings=settings))
    namespace['_restore_middle_header_for_directory'](obj, folder)
    assert obj._middle_header_layout_key == header_layout_key(folder)
    header.resizeSection(0, 490)
    namespace['_save_middle_header_state'](obj, 'resize', 0)
    assert settings.data == {}  # Qt automatic resize must NOT save
    obj._middle_header_mouse_down = True
    namespace['_save_middle_header_state'](obj, 'resize', 0)
    assert header_layout_key(folder) in settings.data
    # Merely resizing the *stretch* spacer never adds/updates a preference.
    before = dict(settings.data)
    header.resizeSection(4, 300)
    namespace['_save_middle_header_state'](obj, 'resize', 4)
    assert settings.data == before
    # Reordering the spacer itself must still persist visual order.
    header.moveSection(4, 2)
    namespace['_save_middle_header_state'](obj, 'move', 4)
    assert json.loads(settings.data[header_layout_key(folder)])['order'] == [0, 1, 4, 2, 3]
    namespace['_restore_middle_header_for_directory'](obj, other)
    assert header.sectionSize(0) == 300
    namespace['_restore_middle_header_for_directory'](obj, folder)
    assert header.sectionSize(0) == 490
    assert header.visual == [0, 1, 4, 2, 3]
    assert len(settings.data) == 1
