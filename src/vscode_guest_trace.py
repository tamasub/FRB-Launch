"""Best-effort VS Code guest lifecycle trace: no document paths or bodies."""
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def trace(event, **fields):
    try:
        folder = Path(os.environ.get('LOCALAPPDATA') or Path.home()) / 'FRBLaunch'
        folder.mkdir(parents=True, exist_ok=True)
        record = {'time': datetime.now(timezone.utc).isoformat(), 'event': event}
        record.update(fields)
        with (folder / 'vscode_guest_trace.jsonl').open('a', encoding='utf-8') as f:
            f.write(json.dumps(record, ensure_ascii=False) + '\n')
    except (OSError, ValueError, TypeError):
        pass
