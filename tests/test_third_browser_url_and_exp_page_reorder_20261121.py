"""FRB Launch 2026-11-21: browser URL COPY and Exp Page Move contracts."""
import ast
import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))
from browser_url_drag import browser_url_drag_data
from launch_menu_registration import (RegistrationError, mime_sources,
                                      normalize_sources, records_for_sources)
from launch_json_move import (PAGE_MOVE_MIME, MOVE_MIME, encode_page_source,
                              decode_page_source, page_root_identity,
                              page_root_reorder_placement)
from launch_page_registration import page_reorder_plan, commit_page_reorder
from launch_virtual_tree import virtual_exp_roots


class Url:
    def __init__(self, value):
        self.value = value
    def isLocalFile(self):
        return False
    def toString(self):
        return self.value


class BrowserMime:
    def __init__(self, payload):
        self._payload = payload
    def hasUrls(self):
        return True
    def urls(self):
        return [Url(self._payload['url'])]
    def hasFormat(self, key):
        return key in ('text/x-moz-url', 'text/html')
    def formats(self):
        return ['text/x-moz-url', 'text/html']
    def data(self, key):
        if key == 'text/x-moz-url':
            return self._payload['moz_url']
        if key == 'text/html':
            return self._payload['html'].encode('utf8')
        return b''
    def hasText(self):
        return True
    def text(self):
        return self._payload['url']


def test_browser_drop_creates_one_valid_url_record_with_page_title():
    payload = browser_url_drag_data('https://example.org/news?q=1&x=2', '今週の研究まとめ')
    rows = records_for_sources(normalize_sources(mime_sources(BrowserMime(payload))))
    assert len(rows) == 1
    assert rows[0]['title'] == '今週の研究まとめ'
    assert rows[0]['launch_actions'][0]['launch_target'] == 'https://example.org/news?q=1&x=2'
    assert rows[0]['item_kind'] == 'command'
    assert rows[0]['icon_key'] == 'globe'


def test_browser_payload_html_escaping_and_url_validation():
    data = browser_url_drag_data('https://example.jp/?q=a&v=1', 'FRB <研究> & ニュース')
    assert '&amp;' in data['html'] and '&lt;研究&gt;' in data['html']
    assert data['moz_url'].decode('utf-16-le').splitlines()[1] == 'FRB <研究> & ニュース'
    for bad in ('', 'file:///tmp/x', 'javascript:alert(1)',
                'https://example.jp/a\nb', 'not-a-url', 'https://ex ample.jp'):
        assert browser_url_drag_data(bad, 'untrusted') is None


def test_page_drag_mime_never_conflates_item_move():
    assert PAGE_MOVE_MIME != MOVE_MIME
    assert decode_page_source(encode_page_source('work')) == 'work'
    assert decode_page_source(b'{}') is None
    assert decode_page_source(b'{"version":1,"page_id":42}') is None
    assert decode_page_source(b'not json') is None


def template_doc():
    return json.loads((ROOT/'defaults/frb_launch_data.template.json').read_text(encoding='utf8'))


def test_real_exp_pages_and_promoted_system_bookmarks_have_page_identity():
    doc = template_doc()
    roots = virtual_exp_roots(doc['pages'], doc['items'])
    assert len(roots) >= 3
    keys = [page_root_identity(node) for node in roots]
    assert keys == [node['page_id'] for node in roots]
    assert 'system' in keys  # bookmark alias is a real authored System Page
    bookmark = next(node for node in roots if node['page_id'] == 'system')
    assert bookmark['node_id'].startswith('item:system:')
    assert page_root_identity({**bookmark, 'runtime_catalog': 'browser_bookmarks'}) is None
    assert page_root_identity({**bookmark, 'row': {'item_kind': 'category'}}) is None
    assert page_root_identity({**bookmark, 'node_id': 'page:system'}) is None


def test_categories_and_files_cannot_be_page_reorder_sources():
    doc = template_doc()
    roots = virtual_exp_roots(doc['pages'], doc['items'])
    parent = next(node for node in roots if node['children'])
    child = parent['children'][0]
    assert page_root_identity(child) is None
    assert page_root_identity({'path': 'C:/', 'pc': False}) is None
    assert page_root_identity({'source': 'launch_json', 'kind': 'page',
                               'page_id': 'work', 'item_id': '',
                               'node_id': 'page:other'}) is None


def test_page_reorder_positions_and_blank_end():
    assert page_root_reorder_placement('work', 'windows', fraction=0.1) == {
        'position': 'before', 'anchor_page_id': 'windows'}
    assert page_root_reorder_placement('work', 'windows', fraction=0.9) == {
        'position': 'after', 'anchor_page_id': 'windows'}
    assert page_root_reorder_placement('work', None) == {'position': 'end'}
    assert page_root_reorder_placement('', None) is None


def test_page_reorder_plan_updates_only_pages_and_is_noop_on_self(tmp_path):
    p = tmp_path / 'launch.json'
    original = (ROOT/'defaults/frb_launch_data.template.json').read_bytes()
    p.write_bytes(original)
    plan = page_reorder_plan(p, 'system', {'position': 'before', 'anchor_page_id': 'work'})
    assert plan is not None
    assert plan['ordered_pages'][0] == 'system'
    op = plan['request']['operations'][0]
    assert op['section_id'] == 'pages' and op['operation'] == 'update'
    assert all(target['changes'][0]['path'] == 'sort_order' for target in op['targets'])
    assert plan['count'] == len(op['targets'])
    assert p.read_bytes() == original  # absolutely no direct mutation
    assert page_reorder_plan(p, 'work', {'position': 'after', 'anchor_page_id': 'work'}) is None


def test_page_reorder_plan_rejects_cross_domain_and_invalid_ids(tmp_path):
    p = tmp_path / 'launch.json'
    p.write_bytes((ROOT/'defaults/frb_launch_data.template.json').read_bytes())
    for source, target in (
        ('missing', {'position': 'end'}),
        ('work', {'position': 'before', 'anchor_page_id': 'missing'}),
        ('work', {'position': 'other', 'anchor_page_id': 'windows'}),
        ('work', {'position': 'before', 'anchor_id': 'windows'})):
        with pytest.raises(RegistrationError):
            page_reorder_plan(p, source, target)


def test_page_reorder_commit_uses_studio_twice_with_same_sha(monkeypatch, tmp_path):
    p = tmp_path / 'launch.json'
    p.write_bytes((ROOT/'defaults/frb_launch_data.template.json').read_bytes())
    before = p.read_bytes()
    calls = []
    def fake_cli(root, trusted, request, mode, timeout):
        calls.append((mode, request['base_sha256'], request['request_id'], trusted))
        return {'status': 'PREVIEW' if mode == 'dry_run' else 'COMMITTED',
                'saved': mode == 'commit',
                'summary': {'changed_existing': len(request['operations'][0]['targets'])}}
    monkeypatch.setattr('launch_page_registration._invoke_delete_cli', fake_cli)
    out = commit_page_reorder(p, tmp_path, 'system',
                              {'position': 'before', 'anchor_page_id': 'work'})
    assert out['status'] == 'COMMITTED'
    assert [c[0] for c in calls] == ['dry_run', 'commit']
    assert calls[0][1:3] == calls[1][1:3]
    assert calls[0][3]['documents']['approved_launch_config']['section_ids'] == ['pages']
    assert p.read_bytes() == before


def test_exp_tree_and_launcher_wiring_do_not_touch_item_move_contract():
    pane = (ROOT/'src/remote_files_explorer.py').read_text(encoding='utf8')
    app = (ROOT/'src/app.py').read_text(encoding='utf8')
    browser = (ROOT/'src/launch_web_view.py').read_text(encoding='utf8')
    ast.parse(pane)
    ast.parse(app)
    ast.parse(browser)
    assert 'PAGE_MOVE_MIME' in pane
    assert '_active_page_root_drag = page_source' in pane
    assert 'self._active_page_root_drag = None' in pane
    assert 'sender is not self.tree' in pane
    assert 'launcher.launch_page_reorder_drop(' in pane
    assert 'commit_page_reorder(' in app
    assert 'launcher.launch_json_move_drop(event.mimeData(), placement,' in pane
    assert 'QToolButton#launchWebUrlDrag' in browser
    assert "payload.setHtml(source['html'])" in browser
    assert 'Qt.DropAction.CopyAction' in browser


def _extract_method(module, class_name, method, globals_dict):
    """Run real GUI adapter Python methods without loading Qt on Linux CI."""
    source = (ROOT/'src'/module).read_text(encoding='utf8')
    tree = ast.parse(source)
    cls = next(c for c in tree.body if isinstance(c, ast.ClassDef) and c.name == class_name)
    func = next(c for c in cls.body if isinstance(c, (ast.FunctionDef, ast.AsyncFunctionDef))
                and c.name == method)
    env = dict(globals_dict)
    exec(compile(ast.Module(body=[func], type_ignores=[]), module, 'exec'), env)
    return env[method]


def test_exp_start_drag_of_page_uses_unique_mime_and_cleans_drag_state():
    from types import SimpleNamespace
    class StubMime:
        def __init__(self):
            self.data = {}
        def setData(self, key, value):
            self.data[key] = value
    seen = []
    class StubDrag:
        def __init__(self, widget):
            self.widget = widget
        def setMimeData(self, mime):
            self.mime = mime
        def exec(self, *_):
            assert self.widget._active_page_root_drag == 'work'
            seen.append(self.mime.data)
    item = SimpleNamespace(data=lambda _: {'virtual': {
        'kind': 'page', 'page_id': 'work', 'source': 'launch_json',
        'node_id': 'page:work', 'item_id': ''}})
    panel = SimpleNamespace(
        model=SimpleNamespace(itemFromIndex=lambda _: item),
        page_root_identity=lambda _: 'work')
    tree = SimpleNamespace(
        _active_page_root_drag=None,
        parentWidget=lambda: panel,
        currentIndex=lambda: SimpleNamespace(isValid=lambda: True))
    start = _extract_method('remote_files_explorer.py', 'FilesExpWheelTree', 'startDrag', {
        'Qt': SimpleNamespace(DropAction=SimpleNamespace(MoveAction=2)),
        'QMimeData': StubMime, 'QDrag': StubDrag,
        '_DATA_ROLE': 257, 'PAGE_MOVE_MIME': PAGE_MOVE_MIME,
        'encode_page_source': encode_page_source})
    start(tree, None)
    assert decode_page_source(seen[0][PAGE_MOVE_MIME]) == 'work'
    assert tree._active_page_root_drag is None


def test_page_move_target_rejects_physical_files_and_checks_drag_identity():
    from types import SimpleNamespace
    target = virtual_exp_roots(template_doc()['pages'], template_doc()['items'])[1]
    root_item = SimpleNamespace(data=lambda _: {'virtual': target}, parent=lambda: None)
    class FakeIndex:
        def __init__(self, is_valid):
            self._valid = is_valid
        def isValid(self):
            return self._valid
    class Mime:
        def hasFormat(self, fmt):
            return fmt == PAGE_MOVE_MIME
        def data(self, fmt):
            return encode_page_source('work')
    panel = SimpleNamespace(
        _launcher=object(),
        model=SimpleNamespace(itemFromIndex=lambda _: root_item),
        tree=SimpleNamespace(_active_page_root_drag='work',
                             indexAt=lambda _: FakeIndex(True),
                             visualRect=lambda _: SimpleNamespace(top=lambda: 0, height=lambda: 20)))
    panel.page_root_identity = lambda item: page_root_identity(item.data(257)['virtual'])
    move = _extract_method('remote_files_explorer.py', 'RemoteFilesExplorer',
                           'page_move_target_at', {
                               'PAGE_MOVE_MIME': PAGE_MOVE_MIME,
                               'decode_page_source': decode_page_source,
                               'page_root_reorder_placement': page_root_reorder_placement})
    assert move(panel, SimpleNamespace(y=lambda: 1), Mime(), panel.tree)['position'] == 'before'
    assert move(panel, SimpleNamespace(y=lambda: 19), Mime(), panel.tree)['position'] == 'after'
    assert move(panel, SimpleNamespace(y=lambda: 1), Mime(), object()) is None
    panel.page_root_identity = lambda _: None  # physical Files target
    assert move(panel, SimpleNamespace(y=lambda: 1), Mime(), panel.tree) is None
    panel.tree._active_page_root_drag = None
    assert move(panel, SimpleNamespace(y=lambda: 1), Mime(), panel.tree) is None


def test_browser_handle_mouse_drag_exports_copy_url_with_title():
    from types import SimpleNamespace
    captures = []
    class FakePoint:
        def __init__(self, x): self.x = x
        def __sub__(self, other): return FakePoint(self.x - other.x)
        def manhattanLength(self): return abs(self.x)
    class StubMime:
        def __init__(self): self.values = {}
        def setUrls(self, urls): self.values['urls'] = urls
        def setText(self, value): self.values['text'] = value
        def setHtml(self, value): self.values['html'] = value
        def setData(self, fmt, value): self.values[fmt] = value
    class StubDrag:
        def __init__(self, owner): self.owner = owner
        def setMimeData(self, mime): self.mime = mime
        def exec(self, *_): captures.append(self.mime.values)
    class StubButton:
        def mouseMoveEvent(self, _): pass
    class FakeEvent:
        def buttons(self): return 1
        def position(self): return SimpleNamespace(toPoint=lambda: FakePoint(20))
    method = _extract_method('launch_web_view.py', '_WebUrlDragButton',
                             'mouseMoveEvent', {
        'QApplication': SimpleNamespace(startDragDistance=lambda: 4),
        'Qt': SimpleNamespace(MouseButton=SimpleNamespace(LeftButton=1),
                              DropAction=SimpleNamespace(CopyAction=1)),
        'QMimeData': StubMime, 'QUrl': lambda url: url, 'QDrag': StubDrag,
        'QToolButton': StubButton, 'browser_url_drag_data': browser_url_drag_data})
    # The real class uses super().mouseMoveEvent only before the drag begins;
    # a threshold-exceeding gesture follows only the tested Qt branch.
    owner = SimpleNamespace(_pressed_at=FakePoint(0),
                            _url_and_title=lambda: ('https://example.com/frb', 'FRB記事'))
    method(owner, FakeEvent())
    assert len(captures) == 1
    assert captures[0]['urls'] == ['https://example.com/frb']
    assert captures[0]['text'] == 'https://example.com/frb'
    assert 'FRB記事' in captures[0]['html']
    assert 'FRB記事' in captures[0]['text/x-moz-url'].decode('utf-16-le')
    assert owner._pressed_at is None
