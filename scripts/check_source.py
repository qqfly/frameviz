#!/usr/bin/env python3
"""Check source selection, local paths, license ownership, and approved assets."""
from pathlib import Path
import hashlib,json,re,os
from update_source_manifest import ROOT,source_files
errors=[];files=list(source_files())
for rel,p in files:
 if p.suffix.lower() in {'.png','.ico','.icns'}:continue
 try:text=p.read_text()
 except UnicodeError:errors.append(f'Unapproved binary {rel}');continue
 for pattern in [r'(?<![A-Za-z0-9])/(?:Users|home)/[a-zA-Z0-9_.-]+/',r'-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----',r'AKIA[A-Z0-9]{16}']:
  if re.search(pattern,text):errors.append(f'Private path or credential pattern in {rel}')
 for marker in filter(None,os.environ.get('FRAMEVIZ_PRIVATE_MARKERS','').split(',')):
  if marker.lower() in text.lower():errors.append(f'Forbidden organization marker in {rel}')
 if p.name=='Cargo.toml' and 'license = "MIT"' not in text:errors.append(f'Cargo license missing: {rel}')
 if p.name=='package.json' and json.loads(text).get('license')!='MIT':errors.append(f'Package license missing: {rel}')
 if 'Copyright (c) 2026 qqfly' not in (ROOT/'LICENSE').read_text():errors.append('Project copyright missing')
assets=json.loads((ROOT/'artwork/asset-manifest.json').read_text())
for name,want in assets['files'].items():
 p=ROOT/name
 if not p.is_file() or hashlib.sha256(p.read_bytes()).hexdigest()!=want:errors.append(f'Generated asset mismatch: {name}')
print(json.dumps({'source_files':len(files),'errors':sorted(set(errors))},indent=2));raise SystemExit(bool(errors))
