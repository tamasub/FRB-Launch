#!/usr/bin/env python3
"""Normalize the Excel-exported FRB Launch documentation for GitHub Pages.

Excel writes Shift_JIS/CP932 HTML. The GitHub Pages web view is easiest to
maintain when HTML and CSS bytes and declarations are all UTF-8.

Usage from the FRB Launch repository root:
    python scripts/normalize_frb_launch_excel_html.py

Repeat after each Excel HTML export (idempotent for already-normalized files).
"""
from __future__ import annotations

import re
from pathlib import Path

DOCS = Path(__file__).resolve().parents[1] / "docs"
HTML_FILES = (
    "FRB_Launch.htm",
    "FRB_Launch.files/sheet001.htm",
    "FRB_Launch.files/sheet002.htm",
    "FRB_Launch.files/tabstrip.htm",
)
CSS_FILE = "FRB_Launch.files/stylesheet.css"


def decode_markup(raw: bytes) -> str:
    """Accept current UTF-8 or original Windows Excel CP932 files."""
    try:
        return raw.decode("utf-8", errors="strict")
    except UnicodeDecodeError:
        return raw.decode("cp932", errors="strict")


def normalize_html(raw: bytes) -> bytes:
    markup = decode_markup(raw)
    markup, count = re.subn(
        r"charset\s*=\s*shift_jis",
        "charset=utf-8",
        markup,
        flags=re.IGNORECASE,
    )
    if not re.search(r"charset\s*=\s*['\"]?utf-8", markup, flags=re.IGNORECASE):
        raise ValueError("HTML charset not recognized; inspect the exported file")
    return markup.encode("utf-8")


def normalize_css(raw: bytes) -> bytes:
    css = decode_markup(raw)
    if not css.startswith('@charset "UTF-8";'):
        css = '@charset "UTF-8";\r\n' + css
    return css.encode("utf-8")


def main() -> None:
    for relative_path in HTML_FILES + (CSS_FILE,):
        file = DOCS / relative_path
        before = file.read_bytes()
        after = (normalize_css(before) if relative_path == CSS_FILE
                 else normalize_html(before))
        if before != after:
            file.write_bytes(after)
            print("converted:", file.relative_to(DOCS))
        else:
            print("already UTF-8:", file.relative_to(DOCS))


if __name__ == "__main__":
    main()
