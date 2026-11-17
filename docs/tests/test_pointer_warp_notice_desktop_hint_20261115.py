"""Initial usage hint in the existing pointer-warp notice (source-only regression)."""
import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTICE = ROOT / 'src' / 'pointer_warp_notice.py'
APP = ROOT / 'src' / 'app.py'
POLICY = ROOT / 'src' / 'pointer_warp_policy.py'


def test_desktop_double_click_hint_is_dark_green_bold_rich_text():
    source = NOTICE.read_text(encoding='utf-8')
    ast.parse(source)
    assert 'FRB Launchは、デスクトップの空白部分を' in source
    assert 'ダブルクリックすると表示' in source
    assert '<span style="color:#145c3d; font-weight:700;">' in source
    assert "intro.setTextFormat(Qt.TextFormat.RichText)" in source
    assert 'intro.setWordWrap(True)' in source
    assert 'layout.addWidget(intro)' in source
    assert 'pointerWarpNoticeIntro' in source


def test_existing_notice_and_controls_are_unchanged():
    source = NOTICE.read_text(encoding='utf-8')
    assert 'マウスポインター自動移動は現在OFFです。' in source
    assert '使いたい場合は、設定 → マウスポインター自動移動 → ON。' in source
    for action in ('今後表示しない', 'あとで', '設定を開く'):
        assert action in source
    assert 'QTimer.singleShot(1500, window.maybe_show_pointer_warp_notice)' in APP.read_text(encoding='utf-8')
    assert "NOTICE_DISMISSED_KEY = 'pointer_warp_notice_dont_show_again'" in POLICY.read_text(encoding='utf-8')
