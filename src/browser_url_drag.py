"""Small, Qt-independent contract for dragging the third-column Browser URL.

The source exports a COPYable web bookmark, never an internal JSON Move.
It can be dropped into the existing Studio-owned Page/category registration
path in Files Exp or Files List.  The browser continues to own its session.
"""

from html import escape
from urllib.parse import urlsplit


def browser_url_drag_data(url, title=''):
    """Return a one-URL payload with page-title metadata, or None if unsafe."""
    address = str(url or '').strip()
    try:
        parsed = urlsplit(address)
    except (TypeError, ValueError):
        return None
    if (parsed.scheme.lower() not in ('http', 'https') or not parsed.netloc or
            any(c.isspace() or ord(c) < 32 for c in address)):
        return None
    caption = ''.join(' ' if ord(c) < 32 else c for c in str(title or '')).strip()[:160]
    if not caption:
        caption = address
    html = f'<a href="{escape(address, quote=True)}">{escape(caption)}</a>'
    return {'url': address, 'title': caption, 'html': html,
            'moz_url': (address + '\n' + caption).encode('utf-16-le')}
