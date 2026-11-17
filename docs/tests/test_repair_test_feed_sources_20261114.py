import json
import sys
from pathlib import Path
import pytest
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
from repair_update_test_feed_sources import repair_files


def test_repair_feed_writes_two_distinct_layers_and_preserves_existing_fields(tmp_path):
    root=tmp_path/'FRB_Update_Test'/'FRBLaunch'
    rel=tmp_path/'rel'
    rel.mkdir()
    (rel/'updater_feed.json').write_text(json.dumps({'schema':'frb-updater-feed-v1','version':'0.9.3'}))
    (rel/'product_feed.json').write_text(json.dumps({'schema':'frb-product-feed-v1','version':'0.9.3'}))
    system=root/'defs/update/update_sources.json'
    system.parent.mkdir(parents=True)
    system.write_text(json.dumps({'schema':'frb-update-sources-v1','updater_feed_url':'','product_feed_url':'','allow_local_for_test':False,'custom':'kept'}))
    repair_files(root,rel,dry_run=True)
    assert not (root/'UserConfig/update_sources.json').exists()
    repair_files(root,rel)
    assert json.loads(system.read_text())['custom']=='kept'
    user=json.loads((root/'UserConfig/update_sources.json').read_text())
    assert user['product_feed_url']==(rel/'product_feed.json').resolve().as_uri()
    assert user['allow_local_for_test'] is True
    repair_files(root,rel)
    assert len(list(system.parent.glob('*.bak')))==1


def test_only_test_install_root_allowed(tmp_path):
    with pytest.raises(ValueError):
        repair_files(tmp_path/'FRB_Apps'/'FRBLaunch',tmp_path)
