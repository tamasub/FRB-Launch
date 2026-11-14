"""App-neutral Updater bootstrapping: check -> fetch -> validate -> install -> start.

Versioned updater paths avoid touching a running executable. This module is
shared by host apps, not copied into a second Updater implementation.
"""
from __future__ import annotations
import json
import os
import subprocess
import tempfile
from pathlib import Path
from .contracts import UpdateError, download, read_feed, sha256_file, safe_relative, version_tuple

UPDATER_FEED_SCHEMA = 'frb-updater-feed-v1'
PRODUCT_FEED_SCHEMA = 'frb-product-feed-v1'

def check_feeds(updater_feed: str, product_feed: str, *, allow_local=False):
    if not updater_feed or not product_feed:
        raise UpdateError('Updater／製品の更新先URLが未設定です')
    updater = read_feed(updater_feed, UPDATER_FEED_SCHEMA, allow_local=allow_local)
    product = read_feed(product_feed, PRODUCT_FEED_SCHEMA, allow_local=allow_local)
    return updater, product

def ensure_updater(install_root: Path, feed: dict, *, allow_local=False) -> Path:
    root = Path(install_root).resolve()
    version = feed['version']
    version_tuple(version)
    directory = root / 'updater' / 'versions' / version
    binary = directory / 'FRBUpdater.exe'
    if binary.is_file() and sha256_file(binary).lower() == feed['sha256'].lower():
        return binary
    directory.mkdir(parents=True,exist_ok=True)
    download(feed['url'], binary, digest=feed['sha256'],size=feed['size'],allow_local=allow_local)
    return binary

def prepare_request(product: dict, work_dir: Path, *, allow_local=False) -> Path:
    # Only validated allowlisted feed fields are sent to the Updater.
    url = product['archive_url']
    from .contracts import check_source
    check_source(url, allow_local=allow_local)
    request = {'schema': 'frb-update-request-v1', 'version': product['version'],
               'archive_url':url, 'sha256': product['sha256'], 'size':product['size'],
               'allow_local': bool(allow_local), 'components':product['components']}
    directory = Path(work_dir)
    directory.mkdir(parents=True,exist_ok=True)
    target = directory / 'pending_update.json'
    tmp = directory / 'pending_update.json.tmp'
    tmp.write_text(json.dumps(request,ensure_ascii=False,indent=2)+'\n','utf-8')
    os.replace(tmp,target)
    return target

def start_updater(binary: Path, *, request: Path, install_root: Path, host_pid: int,
                  host_binary: str = 'FRBLaunch.exe', allow_local: bool = False):
    """Launch installed Updater. Caller must close its own UI after this returns."""
    if Path(host_binary).name != host_binary or not host_binary.lower().endswith('.exe'):
        raise UpdateError('起動対象EXE名が不正です')
    cmd = [str(binary), 'apply', '--request', str(request), '--install-root',str(install_root),
           '--wait-pid',str(host_pid),'--host-exe',host_binary]
    if allow_local: cmd.append('--allow-local-for-test')
    flags = getattr(subprocess,'CREATE_NEW_PROCESS_GROUP',0)
    return subprocess.Popen(cmd,cwd=str(Path(binary).parent),stdin=subprocess.DEVNULL,
                            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,
                            close_fds=True, creationflags=flags)
