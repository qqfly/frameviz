#!/usr/bin/env python3
"""List local regeneration candidates without deleting data or shared caches."""
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('group',choices=['all','cpp','py','cache']);a=p.parse_args()
groups={
 'cpp':['.cache/cpp-release','packages/frameviz-cpp/build','examples/cpp/build'],
 'py':['packages/frameviz-py/build','packages/frameviz-py/dist','packages/frameviz-py/frameviz.egg-info'],
 'cache':['packages/frameviz-core/dist','packages/frameviz-protocol/dist','packages/frameviz-web-viewer/dist','packages/frameviz-vue/dist'],
}
paths=sorted({name for key,names in groups.items() if a.group in ['all',key] for name in names})
print(json.dumps({'mode':'inspection-only','project':str(ROOT),'candidates':[{'path':name,'exists':(ROOT/name).exists(),'symlink':(ROOT/name).is_symlink()} for name in paths], 'next_step':'Check contents and active processes before manual deletion. Shared caches, evidence, runtime state, installed apps and environments are never cleaned here.'},indent=2))
