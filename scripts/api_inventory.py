#!/usr/bin/env python3
"""Static command presence inventory; not an API parity or execution guarantee."""
from pathlib import Path
import re
ROOT=Path(__file__).resolve().parents[1]
sources={
 'Host':['packages/frameviz-server/src/host.rs','packages/frameviz-server/src/websocket.rs'],
 'Core':['packages/frameviz-core/src/core.ts'],
 'Python':['packages/frameviz-py/frameviz/viz.py','packages/frameviz-py/frameviz/client.py'],
 'C++':['packages/frameviz-cpp/src/viz.cpp','packages/frameviz-cpp/src/client.cpp'],
}
commands=set(re.findall(r'^ {12}"([a-z][a-z0-9_]+)"\s*=>', (ROOT/sources['Host'][0]).read_text(),re.M))
commands.update(['present_view','get_resource_counts','register_viewer','get_viewer_by_name','list_viewers','upload_buffer_chunk'])
texts={key:'\n'.join((ROOT/name).read_text() for name in names) for key,names in sources.items()}
rows=['# Static API inventory','','This table records command-name literals in the implementation. Presence does not prove equivalent signatures, rendering, compatibility, or test coverage. Use the versioned API contract and actual acceptance receipts.','','| Command | Host | Core | Python | C++ |','|---|---|---|---|---|']
for command in sorted(commands):rows.append('| `'+command+'` | '+' | '.join('present' if re.search(r'[\"\x27]'+re.escape(command)+r'[\"\x27]',text) else 'not directly referenced' for text in texts.values())+' |')
(ROOT/'docs/API_SUPPORT.md').write_text('\n'.join(rows)+'\n');print('command names:',len(commands))
