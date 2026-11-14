"""Restore local PRIVATE_REVIEW Feed URLs in update-test System AND UserConfig.

The active Launch 0.9.3 reads System, the patched Launch 0.9.2+ reads UserConfig.
Preparing both removes the post-update URL regression without changing any
installed EXE, application data, backup journal or version.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
from uuid import uuid4


def local_feed_sources(release_dir: Path):
    updater = release_dir / 'updater_feed.json'
    product = release_dir / 'product_feed.json'
    for file, kind in ((updater, 'frb-updater-feed-v1'), (product, 'frb-product-feed-v1')):
        if not file.is_file():
            raise FileNotFoundError('Feedファイルが見つかりません: ' + str(file))
        parsed = json.loads(file.read_text(encoding='utf-8-sig'))
        if parsed.get('schema') != kind:
            raise ValueError('Feedのschemaが一致しません: ' + str(file))
    return {'schema':'frb-update-sources-v1',
            'updater_feed_url':updater.resolve().as_uri(),
            'product_feed_url':product.resolve().as_uri(),
            'allow_local_for_test':True}


def repair_files(install_root: Path, release_dir: Path, *, dry_run=False):
    root=Path(install_root)
    if root.name.casefold()!='frblaunch' or root.parent.name.casefold()!='frb_update_test':
        raise ValueError('安全制約：FRB_Update_Test/FRBLaunch のみ変更できます')
    if root.is_symlink():
        raise ValueError('シンボリックリンクのテスト環境は変更しません')
    sources = local_feed_sources(Path(release_dir))
    files=(root/'defs'/'update'/'update_sources.json',root/'UserConfig'/'update_sources.json')
    staged=[]
    for path in files:
        if path.is_symlink() or path.parent.is_symlink():
            raise ValueError('設定ファイルのシンボリックリンクは変更しません: '+str(path))
        if path.exists():
            old=json.loads(path.read_text(encoding='utf-8-sig'))
            if old.get('schema')!='frb-update-sources-v1':
                raise ValueError('既存sources schemaが不正: '+str(path))
            # Respect an active user's explicit non-test URLs.
            urls=[old.get('updater_feed_url'),old.get('product_feed_url')]
            if path.parts[-2].casefold()=='userconfig' and all(urls) and old!=sources:
                raise ValueError('既存UserConfigを上書きしません。明示的に内容を確認してください: '+str(path))
            new=dict(old)
            new.update(sources)
            if old==new:
                print('[UNCHANGED]', path)
                continue
        else:
            new=sources
        staged.append((path,new))
        print('[PLAN]',path)
    if dry_run:
        print('[DRY-RUN] 変更しません')
        return
    # Check and parse all files before writing either one.
    for path,obj in staged:
        path.parent.mkdir(parents=True,exist_ok=True)
        if path.exists():
            backup=path.with_name(path.name+'.before_feed_repair_'+datetime.now().strftime('%Y%m%d_%H%M%S')+'_'+uuid4().hex[:6]+'.bak')
            with backup.open('xb') as out:
                out.write(path.read_bytes());out.flush();os.fsync(out.fileno())
            print('[BACKUP]',backup)
        tmp=path.with_name(path.name+'.'+uuid4().hex+'.tmp')
        try:
            with tmp.open('xb') as out:
                out.write((json.dumps(obj,ensure_ascii=False,indent=2)+'\n').encode('utf-8'))
                out.flush();os.fsync(out.fileno())
            os.replace(tmp,path)
        finally:
            tmp.unlink(missing_ok=True)
        print('[OK]',path)


def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--install-root',type=Path,default=Path(r'F:\FRB_Update_Test\FRBLaunch'))
    parser.add_argument('--release-dir',type=Path,default=Path(r'F:\FRB_Apps\FRB_Release_Output'))
    parser.add_argument('--dry-run',action='store_true')
    a=parser.parse_args(argv)
    repair_files(a.install_root,a.release_dir,dry_run=a.dry_run)

if __name__=='__main__':main()
