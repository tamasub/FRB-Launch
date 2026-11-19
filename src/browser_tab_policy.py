"""Which existing embedded Web tab, if any, matches an incoming Launch URL.

Conservative: only reuse tabs currently displaying the requested URL.
An edited/form page that has navigated elsewhere must never be overwritten.
"""
from urllib.parse import urlsplit, urlunsplit


def comparable_url(value):
    """Normalize ordinary root-URL spelling, not query or fragment semantics."""
    if not isinstance(value, str) or not value.strip():
        return ''
    try:
        parsed = urlsplit(value.strip())
        if parsed.scheme.casefold() not in ('http', 'https') or not parsed.hostname:
            return ''
        scheme = parsed.scheme.casefold()
        netloc = parsed.netloc.casefold()
        # A bare host and its '/' URL denote the same loaded web page.
        path = parsed.path or '/'
        return urlunsplit((scheme, netloc, path, parsed.query, parsed.fragment))
    except ValueError:
        return ''


def matching_tab_index(urls, target):
    """Return the first matching current tab index, or None (not -1)."""
    sought = comparable_url(target)
    if not sought:
        return None
    for index, value in enumerate(urls):
        if comparable_url(value) == sought:
            return index
    return None


def empty_tab(url):
    """A new or truly blank tab may receive the first requested URL."""
    return not str(url or '').strip() or str(url).strip().casefold() == 'about:blank'
