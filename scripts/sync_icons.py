#!/usr/bin/env python3
"""Copy the maintainer-approved original icon set without modifying image bytes."""
from pathlib import Path
import argparse,hashlib,json,shutil
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');a=p.parse_args()
m=json.loads((ROOT/'artwork/icon-source.json').read_text());pairs=[]
for name,want in m['files'].items():
 source=ROOT/'artwork/icons'/name
 if source.is_symlink() or not source.resolve().is_relative_to((ROOT/'artwork/icons').resolve()) or hashlib.sha256(source.read_bytes()).hexdigest()!=want:raise ValueError('Original icon source changed: '+name)
 pairs.append((source,ROOT/'packages/frameviz-host-tauri/src-tauri/icons/tauri'/name))
for project in ['packages/frameviz-host-tauri','examples/apps/simple_slider','examples/apps/urdf_robot','templates/frameviz-template-external-app']:
 pairs.append((ROOT/'artwork/icons/icon.png',ROOT/project/'src-tauri/icons/icon.png'))
for source,target in pairs:
 if a.check:
  if not target.is_file() or target.is_symlink() or target.read_bytes()!=source.read_bytes():raise ValueError('Icon mismatch: '+str(target.relative_to(ROOT)))
 else:
  target.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(source,target)
print('Original icon set verified' if a.check else 'Original icon set synchronized')
