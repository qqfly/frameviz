#!/usr/bin/env python3
"""Generate a lock/metadata inventory; not a binary or vulnerability audit."""
import argparse,importlib.metadata,json,re,tomllib,urllib.parse
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('--output',type=Path,default=ROOT/'dependency-inventory.json');a=p.parse_args()
components={};unknown=[]
previous={}
if a.output.exists():
 for c in json.loads(a.output.read_text()).get('components',[]):
  if c.get('licenses'):previous[c['purl']]=c['licenses'][0].get('expression') or c['licenses'][0].get('license',{}).get('name')
def add(kind,name,version,license=None,scope='required'):
 key=(kind,name,version);purl=f'pkg:{kind}/{urllib.parse.quote(name,safe="/")}@{version}'
 item={'type':'library','name':name,'version':version,'purl':purl,'scope':scope}
 if isinstance(license,dict):license=license.get('type')
 if not license:license=previous.get(purl)
 if isinstance(license,str) and license:
  item['licenses']=[{'license':{'name':license}}] if '/' in license else [{'expression':license}]
 else:unknown.append({'ecosystem':kind,'name':name,'version':version})
 components[key]=item
# Read local package metadata only to resolve the versions selected by the lockfile.
cache={}
node=ROOT/'node_modules/.pnpm'
if node.is_dir():
 for group in node.iterdir():
  nm=group/'node_modules'
  if not nm.is_dir():continue
  for pkg in nm.iterdir():
   candidates=list(pkg.glob('*/package.json')) if pkg.name.startswith('@') else [pkg/'package.json']
   for path in candidates:
    if path.is_file():
     try:
      data=json.loads(path.read_text());cache[(data['name'],data['version'])]=data.get('license')
     except (ValueError,KeyError):pass
text=(ROOT/'pnpm-lock.yaml').read_text().split('packages:\n',1)[1].split('\nsnapshots:\n',1)[0]
for line in text.splitlines():
 if re.match(r'^  \S.*:$',line):
  value=line.strip()[:-1].strip("'");name,sep,version=value.rpartition('@')
  if sep:add('npm',name,version,cache.get((name,version)),scope='optional')
# Crate license declarations come from the cached exact source, never guessed from names.
registry=Path.home()/'.cargo/registry/src'
for lock in ROOT.glob('packages/**/Cargo.lock'):
 for dep in tomllib.loads(lock.read_text()).get('package',[]):
  if 'source' not in dep:continue
  name,version=dep['name'],dep['version'];license=None
  for path in registry.glob(f'*/{name}-{version}/Cargo.toml'):
   license=tomllib.loads(path.read_text()).get('package',{}).get('license');break
  add('cargo',name,version,license)
for name in ['numpy','websocket-client','pytest','pytest-asyncio','pytest-cov','build','playwright','websockets']:
 try:
  data=importlib.metadata.metadata(name);version=importlib.metadata.version(name)
  license=data.get('License-Expression') or data.get('License')
  if license and ('\n' in license or len(license)>100):license=None
  add('pypi',name,version,license,'required' if name in ['numpy','websocket-client'] else 'optional')
 except importlib.metadata.PackageNotFoundError:unknown.append({'ecosystem':'pypi','name':name,'version':'not installed'})
for name,version,license in [('nlohmann-json','3.11.3','MIT'),('cpp-httplib','0.15.3','MIT'),('IXWebSocket','11.4.5','BSD-3-Clause')]:add('generic',name,version,license)
result={'bomFormat':'CycloneDX','specVersion':'1.5','version':1,'metadata':{'component':{'type':'application','name':'FrameViz','version':json.loads((ROOT/'version.json').read_text())['protocol_version']},'properties':[{'name':'inventory:scope','value':'Source lockfiles and current Python environment; npm optional includes development dependencies. Not exact binary linkage, a vulnerability scan, or a cross-platform redistribution approval.'}]},'components':sorted(components.values(),key=lambda x:x['purl'])}
a.output.write_text(json.dumps(result,indent=2)+'\n')
# Only surviving unknown components; a shared crate may appear in two locks.
unknown=sorted({(v['ecosystem'],v['name'],v['version']) for v in unknown})
print(json.dumps({'components':len(components),'license_metadata_unresolved':[dict(zip(['ecosystem','name','version'],v)) for v in unknown]},indent=2))
