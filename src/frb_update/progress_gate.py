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

ACTIVATION_TIMEOUT_SECONDS = 45


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
    """Launch invokes only after it observed the native window's ready state."""
    go = activation_path(ready_path)
    go.write_text('start\n', encoding='ascii')


def wait_for_activation(ready_path: Path, timeout: float = ACTIVATION_TIMEOUT_SECONDS) -> None:
    """Worker does no updating until Launch has explicitly released the gate."""
    go = activation_path(ready_path)
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if go.is_file():
            if go.read_text(encoding='ascii').strip() != 'start':
                raise RuntimeError('Updater起動許可データが不正です')
            go.unlink(missing_ok=True)
            return
        time.sleep(.1)
    raise TimeoutError('Launchからの更新開始許可を受信できませんでした。Systemは変更していません。')
