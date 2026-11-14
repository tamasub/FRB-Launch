"""Generate a verified updater executable feed, after Windows build."""
import argparse,json,sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'src'))
from frb_update.contracts import sha256_file,version_tuple
p=argparse.ArgumentParser()
p.add_argument('--exe',type=Path,required=True)
p.add_argument('--version',required=True)
p.add_argument('--url',required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args();version_tuple(a.version)
if not a.exe.is_file():p.error('EXE not found')
a.output.parent.mkdir(parents=True,exist_ok=True)
a.output.write_text(json.dumps({'schema':'frb-updater-feed-v1','version':a.version,
  'url':a.url,'size':a.exe.stat().st_size,'sha256':sha256_file(a.exe)},ensure_ascii=False,indent=2)+'\n','utf-8')
print(a.output)
