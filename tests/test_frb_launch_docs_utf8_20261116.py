"""Published Excel-exported FRB Launch pages must share UTF-8, not mixed CP932."""
from pathlib import Path
import re

DOCS = Path(__file__).resolve().parents[1] / 'docs'
PAGES = (
    'FRB_Launch.htm',
    'FRB_Launch.files/sheet001.htm',
    'FRB_Launch.files/sheet002.htm',
    'FRB_Launch.files/tabstrip.htm',
)


def test_excel_pages_use_utf8_bytes_and_matching_meta_charset():
    for name in PAGES:
        page = (DOCS / name).read_bytes().decode('utf-8', errors='strict')
        assert re.search(r'charset\s*=\s*utf-8', page, flags=re.I), name
        assert not re.search(r'charset\s*=\s*shift_jis', page, flags=re.I), name
        assert '\ufffd' not in page, name


def test_japanese_text_survived_excel_export_transcoding():
    sheet = (DOCS / 'FRB_Launch.files/sheet001.htm').read_text(encoding='utf-8')
    assert '機能マップ' in sheet
    assert 'キーボードだけで' in sheet
    css = (DOCS / 'FRB_Launch.files/stylesheet.css').read_bytes().decode('utf-8')
    assert css.startswith('@charset "UTF-8";')
    assert '\ufffd' not in css


def test_original_excel_workbook_file_links_still_resolve():
    for file in (
        'FRB_Launch.files/sheet001.htm',
        'FRB_Launch.files/sheet002.htm',
        'FRB_Launch.files/tabstrip.htm',
        'FRB_Launch.files/stylesheet.css',
        'FRB_Launch.files/filelist.xml',
    ):
        assert (DOCS / file).is_file(), file


def test_normalizer_handles_cp932_and_repeated_runs_without_byte_changes():
    from scripts.normalize_frb_launch_excel_html import normalize_html, normalize_css
    html_cp932 = ('<meta http-equiv=Content-Type content="text/html; charset=shift_jis">'
                  '<p>機能マップ</p>').encode('cp932')
    normalized = normalize_html(html_cp932)
    assert '機能マップ' in normalized.decode('utf-8')
    assert 'content="text/html; charset=utf-8"' in normalized.decode('utf-8')
    assert normalize_html(normalized) == normalized
    css_cp932 = 'body{font-family:"ＭＳ Ｐゴシック";}'.encode('cp932')
    css_utf8 = normalize_css(css_cp932)
    assert 'ＭＳ Ｐゴシック' in css_utf8.decode('utf-8')
    assert normalize_css(css_utf8) == css_utf8
