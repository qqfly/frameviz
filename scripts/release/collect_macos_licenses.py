#!/usr/bin/env python3
"""Collect normal Cargo dependency notices and MPL source for a macOS preview App."""
import argparse,hashlib,json,pathlib,re,shutil,urllib.request
ROOT=pathlib.Path(__file__).resolve().parents[2]
def collect(metadata,app):
 app=app.resolve()
 if app.suffix!='.app' or not app.is_dir() or app.is_symlink():raise ValueError('Use an explicit App bundle')
 resources=app/'Contents/Resources';resources.mkdir(parents=True,exist_ok=True)
 packages={p['id']:p for p in metadata['packages']};nodes={n['id']:n for n in metadata['resolve']['nodes']};todo=[metadata['resolve']['root']];seen=set();records=[];missing=[];cache={};mpl=[]
 while todo:
  key=todo.pop()
  if key in seen:continue
  seen.add(key);todo.extend(d['pkg'] for d in nodes[key]['deps'] if any(k['kind'] is None for k in d['dep_kinds']))
 for key in sorted(seen):
  p=packages[key];folder=pathlib.Path(p['manifest_path']).resolve().parent
  if p['source'] is None:
   if not folder.is_relative_to(ROOT.resolve()):raise ValueError('Unreviewed local dependency')
   continue
  destination=resources/'ThirdPartyLicenses'/f"{p['name']}-{p['version']}";destination.mkdir(parents=True,exist_ok=True)
  files=set()
  for pattern in ['LICENSE*','LICENCE*','COPYING*','NOTICE*','UNLICENSE*','license*']:files.update(q for q in folder.glob(pattern) if q.is_file())
  if p.get('license_file'):
   q=pathlib.Path(p['license_file']);files.add(q if q.is_absolute() else folder/q)
  for q in files:
   if not q.resolve().is_relative_to(folder):raise ValueError('License file escapes dependency source')
   if q.is_file():shutil.copy2(q,destination/q.name)
  record={'name':p['name'],'version':p['version'],'license':p.get('license'),'repository':p.get('repository'),'license_files':sorted(q.name for q in files if q.is_file())}
  if not record['license_files']:missing.append((p,folder,destination,record))
  if 'MPL-2.0' in (p.get('license') or ''):
   if any(q.is_symlink() for q in folder.rglob('*')):raise ValueError('Review symlink in dependency source before copying')
   target=resources/'ThirdPartySource/MPL-2.0'/f"{p['name']}-{p['version']}"
   shutil.copytree(folder,target,dirs_exist_ok=True,ignore=shutil.ignore_patterns('.git','target','build','__pycache__'));mpl.append(target.name)
  records.append(record)
 for p,folder,destination,record in missing:
  # Full MPL source preserves the original notices; the standardized text is shared.
  if p.get('license')=='MPL-2.0':
   matches=sorted(q for q in (resources/'ThirdPartyLicenses').rglob('*') if q.is_file() and q.stat().st_size>15000 and b'Mozilla Public License' in q.read_bytes())
   if matches:
    shutil.copy2(matches[0],destination/'MPL-2.0.txt');record['license_files']=['MPL-2.0.txt'];record['license_text_origin']='Canonical MPL-2.0 text; complete component source and notices also included';continue
  repo=p.get('repository') or '';match=re.fullmatch(r'https://github.com/([^/]+/[^/]+?)(?:\.git)?/?',repo)
  if not match:raise ValueError('License text unavailable; review upstream for '+p['name'])
  sha=json.loads((folder/'.cargo_vcs_info.json').read_text())['git']['sha1']
  if not re.fullmatch(r'[a-f0-9]{40}',sha):raise ValueError('Invalid upstream commit')
  repository=match.group(1);key=(repository,sha)
  if key not in cache:
   req=urllib.request.Request(f'https://api.github.com/repos/{repository}/contents?ref={sha}',headers={'Accept':'application/vnd.github+json','User-Agent':'FrameViz-license-collector'})
   with urllib.request.urlopen(req,timeout=30) as r:entries=json.load(r)
   values=[]
   for entry in entries:
    if entry['type']!='file' or not any(entry['name'].upper().startswith(x) for x in ['LICENSE','LICENCE','COPYING','NOTICE','UNLICENSE']):continue
    url=entry['download_url']
    if not url.startswith('https://raw.githubusercontent.com/'):raise ValueError('Unexpected license source')
    with urllib.request.urlopen(url,timeout=30) as r:data=r.read(2*1024**2+1)
    if len(data)>2*1024**2:raise ValueError('License text too large')
    values.append((entry['name'],data,url))
   cache[key]=values
  if not cache[key]:raise ValueError('No upstream license text for '+p['name'])
  record['upstream_license_sources']=[]
  for name,data,url in cache[key]:
   if pathlib.Path(name).name!=name:raise ValueError('Unsafe license filename')
   (destination/name).write_bytes(data);record['upstream_license_sources'].append({'url':url,'sha256':hashlib.sha256(data).hexdigest()})
  record['license_files']=[name for name,_,_ in cache[key]];record['license_source_commit']=sha
 for name in ['LICENSE','NOTICE']:shutil.copy2(ROOT/name,resources/name)
 shutil.copytree(ROOT/'THIRD_PARTY_LICENSES',resources/'ThirdPartyLicenses/declared-sdk-components',dirs_exist_ok=True)
 result={'scope':'Cargo normal dependency graph filtered for the build target; excludes build/dev edges; system frameworks remain OS supplied. This is not a vulnerability scan or legal approval.','components':records,'source_included_for_mpl':mpl}
 (resources/'runtime-dependencies.json').write_text(json.dumps(result,indent=2)+'\n');return result
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--metadata',required=True,type=pathlib.Path);p.add_argument('--app',required=True,type=pathlib.Path);a=p.parse_args();r=collect(json.loads(a.metadata.read_text()),a.app);print(json.dumps({'runtime_components':len(r['components']),'mpl_sources':r['source_included_for_mpl']}))
