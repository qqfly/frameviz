#!/usr/bin/env python3
"""Export exact manifest-listed source; no Git history or machine state is used."""
import argparse,hashlib,json,pathlib,shutil,sys
ROOT=pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from update_source_manifest import allowed

def export(dest,prefix=None):
 if dest.exists():raise ValueError('Output must be new')
 manifest=json.loads((ROOT/'source-manifest.json').read_text())
 selected=[]
 for name,want in manifest['files'].items():
  rel=pathlib.PurePosixPath(name)
  if rel.is_absolute() or '..' in rel.parts or not allowed(rel):raise ValueError(f'Unsafe source path: {name}')
  if prefix and not pathlib.Path(rel).is_relative_to(prefix):continue
  p=ROOT/rel
  if p.is_symlink() or not p.resolve().is_relative_to(ROOT.resolve()) or not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=want:
   raise ValueError(f'Source changed or unsafe: {name}')
  selected.append((pathlib.Path(rel).relative_to(prefix) if prefix else pathlib.Path(rel),p,want))
 dest.mkdir(parents=True);files={}
 for rel,p,want in selected:
  q=dest/rel;q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q);files[str(rel)]=want
 # A subtree remains independently redistributable with the project notices.
 for name in ['LICENSE','NOTICE']:
  if name not in files:
   shutil.copy2(ROOT/name,dest/name);files[name]=hashlib.sha256((dest/name).read_bytes()).hexdigest()
 if prefix and (ROOT/'THIRD_PARTY_LICENSES').is_dir():
  shutil.copytree(ROOT/'THIRD_PARTY_LICENSES',dest/'THIRD_PARTY_LICENSES')
  for p in (dest/'THIRD_PARTY_LICENSES').rglob('*'):
   if p.is_file():files[str(p.relative_to(dest))]=hashlib.sha256(p.read_bytes()).hexdigest()
 (dest/'source-manifest.json').write_text(json.dumps({'format':2,'project':'FrameViz','version':manifest['version'],'files':files},indent=2)+'\n')
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('output',type=pathlib.Path);p.add_argument('--subtree',type=pathlib.Path);a=p.parse_args();export(a.output,a.subtree)
