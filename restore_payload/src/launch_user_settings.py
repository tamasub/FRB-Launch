"""One-time copy of machine-specific configuration to AppData (no re-sync)."""
import os
from pathlib import Path

def ensure_user_settings(source: Path, destination: Path) -> Path:
    source,destination=Path(source),Path(destination)
    if destination.is_file():return destination
    if destination.exists():raise RuntimeError('ユーザー設定の保存先がファイルではありません: '+str(destination))
    content=source.read_bytes()
    # Preserve all JSON bytes. Exclusive creation ensures subsequent upgrades
    # never rewrite existing local machine paths or preferences.
    destination.parent.mkdir(parents=True,exist_ok=True)
    try:
        with destination.open('xb') as output:
            output.write(content)
            output.flush();os.fsync(output.fileno())
    except FileExistsError:
        pass
    return destination
