"""Run as a normal user in a clean Linux container after installing the wheel.

The checkout is deliberately absent. No runtime path/port/token is configured.
"""
import contextlib
import io
import json
import os
from pathlib import Path
import sys
from urllib.request import urlopen

import frameviz as fv
from frameviz import host
from frameviz.client import PROTOCOL_VERSION
from frameviz.discovery import get_discovery_path, read_discovery_file

assert sys.platform.startswith('linux')
assert os.geteuid() != 0
assert not any(key.startswith('FRAMEVIZ_') for key in os.environ)
assert not os.environ.get('DISPLAY') and not os.environ.get('WAYLAND_DISPLAY')

with contextlib.redirect_stdout(io.StringIO()) as links:
    viz = fv.open()
try:
    process = host._started_host_proc
    info = read_discovery_file()
    assert process is not None and info['pid'] == process.pid
    assert info['version'] == PROTOCOL_VERSION
    assert not (get_discovery_path().stat().st_mode & 0o077)
    handle = viz.add_box()
    assert viz.is_object_alive(handle)
    assert viz.get_transform(handle)['pos'] == [0, 0, 0]
    assert info['viewer_url'] in links.getvalue()
    with urlopen(info['viewer_url'], timeout=3) as response:
        assert b'<script' in response.read()
finally:
    viz.close()
    host.stop_host()
assert process.poll() == 0
assert not get_discovery_path().exists()
print(json.dumps({'result': 'passed', 'user': 'unprivileged', 'runtime': str(host.find_host_executable(prefer_browser=True)),
                  'python': sys.version.split()[0], 'protocol': PROTOCOL_VERSION,
                  'sdk': str(Path(fv.__file__).resolve()), 'checks': ['automatic startup', 'authenticated RPC', 'embedded Viewer', 'owned shutdown']}))
