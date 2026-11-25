"""Count actual filesystem enumerations and menu creations, not flaky timing."""
import os
from test_slash_exp_navigation_20261118 import nav, make_launcher, Panel, Item, Event


def test_large_physical_root_only_scans_explicitly_opened_level(nav, tmp_path, monkeypatch, caplog):
    mod, key = nav
    for index in range(120):
        folder = tmp_path / f'folder_{index:03d}'
        folder.mkdir()
        (folder / 'child.txt').write_text('test')
    for index in range(150):
        (tmp_path / f'file_{index:03d}.txt').write_text('test')
    scans = []
    real_scan = os.scandir
    def scan(path):
        scans.append(os.fspath(path))
        return real_scan(path)
    monkeypatch.setattr(mod.os, 'scandir', scan)
    launcher, calls = make_launcher()
    source = mod.physical_folder_source(launcher, str(tmp_path))
    menu = mod.SlashExpMenu(launcher, Panel([]), source_item=source)
    with caplog.at_level('INFO', logger='frb.launch.diagnostics'):
        menu.populate()
    assert scans == [str(tmp_path)]
    assert len(menu._action_items) == 271  # no truncation, including self row
    assert len(menu._branch_actions) == 120
    assert not menu._submenus
    assert 'KEYBOARD_EX_PERF phase=populate rows=271 branches=120 created=0' in caplog.text
    menu.popup(mod.QPoint(0, 0))
    menu.keyPressEvent(Event(key.Key_Down))
    menu.keyPressEvent(Event(key.Key_Down))
    assert not menu._submenus and scans == [str(tmp_path)]
    target = next(a for a,i in menu._action_items.items() if i.text() == 'folder_090')
    menu._set_scroll_current_action(target)
    menu.keyPressEvent(Event(key.Key_Right))
    assert scans == [str(tmp_path), str(tmp_path / 'folder_090')]
    assert set(menu._submenus) == {target}
    child = menu._submenus[target]
    assert [i.text() for i in child._action_items.values()] == ['（カレントフォルダー）', 'child.txt']
    child.keyPressEvent(Event(key.Key_Left))
    assert menu._selected()[0] is target
    menu.keyPressEvent(Event(key.Key_Right))
    assert menu._submenus[target] is child  # reuse within the current / session
    assert len(scans) == 2 and calls == []


def test_empty_folder_is_discovered_only_when_opened(nav, tmp_path, monkeypatch):
    mod, key = nav
    folder = tmp_path / 'empty'; folder.mkdir()
    scans = []
    actual = os.scandir
    def scan(path):
        scans.append(os.fspath(path)); return actual(path)
    monkeypatch.setattr(mod.os, 'scandir', scan)
    launcher, calls = make_launcher()
    menu = mod.SlashExpMenu(launcher, Panel([]), source_item=mod.physical_folder_source(launcher, str(tmp_path)))
    menu.populate(); menu.popup(mod.QPoint(0, 0))
    action = next(a for a,i in menu._action_items.items() if i.text() == 'empty')
    assert action in menu._branch_actions and action not in menu._submenus
    assert scans == [str(tmp_path)]
    menu.setActiveAction(action)
    menu.keyPressEvent(Event(key.Key_Right))
    child = menu._submenus[action]
    assert scans == [str(tmp_path), str(folder)]
    assert [i.text() for i in child._action_items.values()] == ['（カレントフォルダー）']
    assert not child._branch_actions and calls == []


def test_linked_virtual_child_does_not_scan_until_right(nav, tmp_path, monkeypatch):
    mod, key = nav
    root = tmp_path / 'link'; root.mkdir()
    (root / 'inside.txt').write_text('test')
    launcher, calls = make_launcher()
    from types import SimpleNamespace
    launcher.expander = lambda: SimpleNamespace(expand=lambda path: path)
    node = {'kind':'page','title':'Page','node_id':'page', 'children': [
        {'kind':'linked_directory','title':'Link','node_id':'link','children':[],
         'row':{'launch_browse_target':str(root)}}]}
    parent = Item('Page', {'virtual':node})
    panel = Panel([parent]); scans = []
    actual = os.scandir
    def scan(path):
        scans.append(os.fspath(path)); return actual(path)
    monkeypatch.setattr(mod.os, 'scandir', scan)
    menu = mod.SlashExpMenu(launcher,panel,source_item=parent)
    menu.populate(); menu.popup(mod.QPoint(0,0))
    assert scans == [] and panel.loaded == [] and not menu._submenus
    target = next(a for a,i in menu._action_items.items() if i.text() == 'Link')
    menu.setActiveAction(target); menu.keyPressEvent(Event(key.Key_Right))
    assert scans == [str(root)]
    assert [i.text() for i in menu._submenus[target]._action_items.values()] == ['（カレントフォルダー）','inside.txt']
    assert calls == []
