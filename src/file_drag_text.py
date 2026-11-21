"""Opt-in, bounded text payload for Files List outbound drag.

Never mix file URLs and text in the same payload: native drop targets may
choose either interpretation, which would silently change existing workflows.
The normal file drag remains the default and needs no decoding at all.
"""
from pathlib import Path

# Intentionally conservative: only recognizable text file formats. This is
# not an automatic binary detector and never reads arbitrary large files.
TEXT_DRAG_SUFFIXES = frozenset({
    '.txt', '.md', '.markdown', '.log', '.csv', '.tsv', '.json', '.jsonl',
    '.xml', '.yaml', '.yml', '.ini', '.cfg', '.conf', '.properties',
    '.py', '.js', '.mjs', '.cjs', '.ts', '.tsx', '.jsx', '.html', '.htm',
    '.css', '.scss', '.sql', '.bat', '.cmd', '.ps1', '.sh', '.c', '.h',
    '.cpp', '.hpp', '.java', '.cs', '.go', '.rs', '.toml', '.env',
})
MAX_TEXT_DRAG_BYTES = 1024 * 1024  # 1 MiB; larger files keep the existing file drag.


def text_for_drag(path):
    """Return file contents or None (unsupported/large/binary/unreadable).

    Content is read ONLY after the user explicitly enables text drag.  BOMs
    distinguish UTF-8/UTF-16; otherwise try UTF-8 then Japanese CP932.
    Neither a file path nor its contents are logged.
    """
    candidate = Path(path)
    if candidate.suffix.lower() not in TEXT_DRAG_SUFFIXES:
        return None
    try:
        if candidate.stat().st_size > MAX_TEXT_DRAG_BYTES:
            return None
        with candidate.open('rb') as stream:
            data = stream.read(MAX_TEXT_DRAG_BYTES + 1)
    except (OSError, ValueError):
        return None
    if len(data) > MAX_TEXT_DRAG_BYTES:
        return None
    if data.startswith((b'\xff\xfe', b'\xfe\xff')):
        try:
            return data.decode('utf-16')
        except UnicodeError:
            return None
    if b'\x00' in data:
        return None
    for encoding in ('utf-8-sig', 'cp932'):
        try:
            result = data.decode(encoding)
        except UnicodeError:
            continue
        # Avoid interpreting control-heavy binary as a text file when CP932
        # happens to decode it; tabs/newlines/form feeds are normal text.
        if any(ord(ch) < 32 and ch not in '\t\n\r\f' for ch in result):
            return None
        return result
    return None
