"""Per-update, two-way progress UI startup handshake.

The Updater advertises a visible UI before the Launch process is allowed to
quit. Launch alone creates the activation marker after observing UI readiness.
Without the marker the worker MUST NOT write product files, even if Launch
is closed in the meantime. Paths are unique for each click.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from uuid import uuid4

ACTIVATION_TIMEOUT_SECONDS = 45
# The 0.9.5 Launch writes .go non-atomically. A worker may observe an empty
# file between creation and closing. Tolerate that tiny window, not forever.
PARTIAL_MARKER_GRACE_SECONDS = 1.5


def publish_state(path: Path, status: str, message: str = '') -> None:
    path = Path(path)
    if status not in ('ready', 'error'):
        raise ValueError('不正な進捗画面状態です')
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps({'status': status, 'message': message,
                                'pid': os.getpid()}, ensure_ascii=False) + '\n', 'utf-8')
    os.replace(temp, path)


def activation_path(ready_path: Path) -> Path:
    return Path(str(ready_path) + '.go')


def activate(ready_path: Path) -> None:
    """Publish the approval only after its complete bytes are on disk.

    Write-then-rename prevents another process from seeing an empty or
    partially written .go file. Each ready file is a unique per-click path.
    """
    go = activation_path(ready_path)
    temp = go.with_name(go.name + '.' + uuid4().hex + '.tmp')
    try:
        temp.write_text('start\n', encoding='ascii')
        os.replace(temp, go)
    finally:
        temp.unlink(missing_ok=True)


def wait_for_activation(ready_path: Path, timeout: float = ACTIVATION_TIMEOUT_SECONDS) -> None:
    """Worker does no updating until Launch has explicitly released the gate."""
    go = activation_path(ready_path)
    deadline = time.monotonic() + timeout
    invalid_since = None
    while time.monotonic() < deadline:
        if go.is_file():
            try:
                approved = go.read_text(encoding='ascii').strip() == 'start'
            except (OSError, UnicodeError):
                # A legacy sender may still have the file open for writing.
                approved = False
            if approved:
                go.unlink(missing_ok=True)
                return
            now = time.monotonic()
            if invalid_since is None:
                invalid_since = now
            if now - invalid_since >= PARTIAL_MARKER_GRACE_SECONDS:
                raise RuntimeError('Updater起動許可データが不正です')
        else:
            invalid_since = None
        time.sleep(.1)
    raise TimeoutError('Launchからの更新開始許可を受信できませんでした。Systemは変更していません。')
