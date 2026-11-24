"""Strict update manifests, HTTPS downloads and version comparison (stdlib only)."""
from __future__ import annotations
import hashlib
import json
import re
import shutil
import urllib.parse
import urllib.request
from pathlib import Path, PurePosixPath

VERSION = re.compile(r'^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$')
SHA256 = re.compile(r'^[a-fA-F0-9]{64}$')
MAX_MANIFEST_SIZE = 128 * 1024
MAX_ARCHIVE_SIZE = 2 * 1024 * 1024 * 1024

class UpdateError(RuntimeError):
    pass

def version_tuple(value: str) -> tuple[int, int, int]:
    match = VERSION.fullmatch(str(value))
    if not match:
        raise UpdateError(f'バージョンは x.y.z 形式で指定: {value!r}')
    return tuple(map(int, match.groups()))

def safe_relative(value: str) -> Path:
    if not isinstance(value, str) or not value or '\\' in value or '\x00' in value:
        raise UpdateError('不正な配布ファイル名')
    p = PurePosixPath(value)
    if (p.is_absolute() or any(x in ('.', '..', '') for x in value.split('/'))
            or ':' in value or value.startswith('/') or value.endswith('/')):
        raise UpdateError(f'危険な配布ファイル名: {value!r}')
    if p.parts[0].casefold() in {'updater', 'userdata', 'userconfig', '.frb-update-work'}:
        raise UpdateError(f'更新禁止領域: {value}')
    if value.casefold() in {'config/frb_launch_data.json', 'state.ini'}:
        raise UpdateError(f'ユーザーデータは更新禁止: {value}')
    # Studio's source distribution contains actual user documents. Those
    # trees must never be touched by a product updater, even if the feed says so.
    if (value.casefold().startswith('studio/data/')
            and not value.casefold().startswith('studio/data/json/00_rules/')
            and value.casefold() != 'studio/data/json/config/launch_enums_v0_1.json'):
        raise UpdateError(f'Studioユーザーデータは更新禁止: {value}')
    return Path(*p.parts)

def check_source(url: str, *, allow_local: bool = False) -> str:
    parsed = urllib.parse.urlparse(str(url))
    if parsed.scheme == 'https' and parsed.netloc and not parsed.username and not parsed.password:
        return url
    if allow_local and parsed.scheme == 'file':
        return url
    if allow_local and not parsed.scheme and Path(url).is_file():
        return Path(url).resolve().as_uri()
    raise UpdateError('更新元はHTTPS必須です（ローカル試験のみ file:// を許可）')

def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open('rb') as reader:
        for chunk in iter(lambda: reader.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()

def _urlopen(url: str, *, allow_local=False):
    check_source(url, allow_local=allow_local)
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent':'FRB-Update/0.1'}),timeout=25)

def download(url: str, output: Path, *, digest: str, size: int, allow_local: bool = False,
             progress=None):
    if not SHA256.fullmatch(str(digest)):
        raise UpdateError('SHA-256が不正です')
    if not isinstance(size, int) or size < 1 or size > MAX_ARCHIVE_SIZE:
        raise UpdateError('配布サイズが不正です')
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = output.with_name(output.name + '.downloading')
    temp.unlink(missing_ok=True)
    actual = hashlib.sha256()
    count = 0
    try:
        with _urlopen(url, allow_local=allow_local) as stream, temp.open('xb') as fp:
            check_source(stream.geturl(),allow_local=allow_local)
            while chunk := stream.read(1024 * 1024):
                count += len(chunk)
                if count > size:
                    raise UpdateError('ダウンロードが公開サイズを超過しました')
                actual.update(chunk)
                fp.write(chunk)
                if progress is not None and (count == size or count % (8*1024*1024) < len(chunk)):
                    progress(count,size)
            fp.flush()
        if count != size or actual.hexdigest().lower() != digest.lower():
            raise UpdateError('サイズまたはSHA-256が一致しません')
        temp.replace(output)
    finally:
        temp.unlink(missing_ok=True)
    return output

def read_feed(url: str, schema: str, *, allow_local=False) -> dict:
    with _urlopen(url, allow_local=allow_local) as stream:
        check_source(stream.geturl(),allow_local=allow_local)
        contents = stream.read(MAX_MANIFEST_SIZE + 1)
    if len(contents) > MAX_MANIFEST_SIZE:
        raise UpdateError('更新情報が大きすぎます')
    try:
        payload = json.loads(contents.decode('utf-8-sig'))
    except (UnicodeDecodeError, ValueError) as exc:
        raise UpdateError('更新情報JSONを読み込めません') from exc
    if not isinstance(payload, dict) or payload.get('schema') != schema:
        raise UpdateError('更新情報スキーマが一致しません')
    version_tuple(payload.get('version'))
    if schema == 'frb-updater-feed-v1':
        field = 'url'
    else:
        field = 'archive_url'
        if payload.get('product') != 'FRBLaunchIntegrated':
            raise UpdateError('異なる製品のリリース情報です')
        components=payload.get('components')
        if not isinstance(components,dict) or set(components) != {'launch','studio'}:
            raise UpdateError('Launch／Studioのコンポーネント情報が不正です')
        for component_version in components.values():
            version_tuple(component_version)
    check_source(payload.get(field, ''), allow_local=allow_local)
    if not SHA256.fullmatch(str(payload.get('sha256', ''))):
        raise UpdateError('更新情報のSHA-256が不正です')
    if type(payload.get('size')) is not int or not 0 < payload['size'] <= MAX_ARCHIVE_SIZE:
        raise UpdateError('更新情報のファイルサイズが不正です')
    return payload

def _read_sources_file(path: Path) -> dict:
    try:
        raw = json.loads(Path(path).read_text('utf-8-sig'))
    except (OSError, ValueError) as exc:
        raise UpdateError('更新元設定を読み込めません: ' + str(path)) from exc
    if not isinstance(raw, dict) or raw.get('schema') != 'frb-update-sources-v1':
        raise UpdateError('更新元設定のスキーマが不正です: ' + str(path))
    for key in ('updater_feed_url', 'product_feed_url'):
        if not isinstance(raw.get(key), str):
            raise UpdateError('更新元設定のURL形式が不正です: ' + key)
    if type(raw.get('allow_local_for_test')) is not bool:
        raise UpdateError('更新元設定のローカル試験フラグが不正です')
    return raw


def read_sources(path: Path, *, user_path: Path | None = None) -> dict:
    """Read update endpoints, preferring user-owned persistence outside System.

    A legacy installation stores URLs in System/defs/update/update_sources.json,
    which gets replaced by an official package. On the first successful read,
    migrate *configured* URLs to UserConfig. This happens while Launch is
    running, before it starts the Updater. UserConfig is excluded from the
    updater's managed system inventory and is never overwritten by updates.
    """
    path = Path(path)
    if user_path is None:
        return _read_sources_file(path)
    user_path = Path(user_path)
    if user_path.is_symlink() or user_path.parent.is_symlink():
        raise UpdateError('更新元設定のUserConfigにシンボリックリンクは使えません')
    if user_path.exists():
        if not user_path.is_file():
            raise UpdateError('更新元設定の保存先がファイルではありません')
        return _read_sources_file(user_path)

    sources = _read_sources_file(path)
    if sources['updater_feed_url'] and sources['product_feed_url']:
        # Preserve the exact verified user configuration; do not silently
        # synthesize URLs for public distributions from a local test folder.
        user_path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(sources, ensure_ascii=False, indent=2) + '\n'
        tmp = user_path.with_name(user_path.name + '.migrating')
        try:
            tmp.write_text(payload, encoding='utf-8')
            tmp.replace(user_path)
        finally:
            tmp.unlink(missing_ok=True)
    return sources
