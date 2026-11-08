#!/usr/bin/env python3
"""Freeze distributable source files, excluding caches and local configuration."""
from pathlib import Path
import hashlib,json,os
ROOT=Path(__file__).resolve().parents[1]
DENIED={'.git','.cache','.local','.venv','.validation','node_modules','target','build','dist','dist-acceptance','__pycache__','.pytest_cache','release-local','release-final','test_reports','logs','.frameviz','WixTools','gen'}
EXT={'.py','.rs','.ts','.js','.mjs','.cjs','.vue','.cpp','.hpp','.h','.c','.m','.cmake','.in','.toml','.json','.yaml','.yml','.html','.css','.sh','.md','.txt','.lock','.command','.svg','.png','.ico','.icns','.stl','.dae','.pcd'}
def allowed(path):
 return (not any(p in DENIED or (p.startswith('.') and p not in {'.github','.gitignore','.clang-format','.style.yapf'}) for p in path.parts)
  and not path.name.startswith('.env') and (path.suffix in EXT or path.name in {'LICENSE','NOTICE','CMakeLists.txt','.gitignore','.clang-format','.style.yapf'}))
def source_files(root=ROOT):
 for directory,dirs,files in os.walk(root,followlinks=False):
  dirs[:]=sorted(d for d in dirs if d not in DENIED and not (Path(directory)/d).is_symlink() and (not d.startswith('.') or d=='.github') and not d.endswith('.egg-info'))
  for name in sorted(files):
   p=Path(directory)/name;rel=p.relative_to(root)
   if p.is_file() and not p.is_symlink() and name!='source-manifest.json' and allowed(rel):yield rel,p
if __name__=='__main__':
 m={str(rel):hashlib.sha256(path.read_bytes()).hexdigest() for rel,path in source_files()}
 (ROOT/'source-manifest.json').write_text(json.dumps({'format':2,'project':'FrameViz','version':json.loads((ROOT/'version.json').read_text())['protocol_version'],'files':m},indent=2)+'\n');print('source files:',len(m))
