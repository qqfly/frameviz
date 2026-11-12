"""Actual wheel -> installed App -> WKWebView, with all SDK path overrides absent."""
import json
import os
import pathlib
import shutil
import socket
import subprocess
import sys
import time

import pytest
from test_macos_app import observer, ping
from test_open_runtime import exercise_shared_runtime

pytestmark = pytest.mark.skipif(sys.platform != 'darwin', reason='macOS desktop required')

PROGRAM = r'''
import json,os,pathlib,subprocess,sys
import frameviz as fv
import frameviz.viz as implementation
from frameviz.discovery import read_discovery_file
from frameviz.host import find_host_executable
from frameviz import host
home=pathlib.Path.home()
assert pathlib.Path(fv.__file__).resolve().is_relative_to(pathlib.Path(sys.prefix).resolve())
for key in ['FRAMEVIZ_TAURI_APP','FRAMEVIZ_HOST_PATH','FRAMEVIZ_WS_SERVER_CMD']:
    assert key not in os.environ,key
assert find_host_executable()==home/'Applications/FrameViz.app/Contents/MacOS/frameviz'
first=fv.open(title='Installed Python acceptance')
second=None
try:
    first.add_box(color=(.2,.7,.9))
    first.set_camera_pose((5,-7,5),(0,0,0))
    pose=first.get_camera_pose()
    assert all(abs(a-b)<1e-5 for a,b in zip(pose['eye'],[5,-7,5]))
    pid=read_discovery_file()['pid']
    windows=json.loads(subprocess.check_output([sys.argv[1],str(pid)],text=True))
    assert len(windows)==1,windows
    first.enable_keyboard_shortcuts(False)
    first.enable_keyboard_shortcuts(True)
    second=fv.open(title='Same installed Host')
    second.add_sphere()
    assert read_discovery_file()['pid']==pid
    candidates=[host._started_host_proc,*implementation._AUTO_TAURI_PROCS]
    owned={p.pid for p in candidates if p is not None and p.poll() is None}
    assert not owned or owned == {pid}, owned
    expected=int(sys.argv[2])
    assert len(owned)==expected,(len(owned),expected)
    assert not (home/'state/preferences.json').exists(),'SDK start consumed manual welcome'
    record={'passed':True,'pid':pid,'sdk_file':fv.__file__,'scene_windows_after_first_open':len(windows),'owned_hosts':len(owned),'same_host_for_two_views':True,'camera':pose,'path_override_used':False}
    (home/'result.json').write_text(json.dumps(record,indent=2)+'\n')
finally:
    if second:second.close()
    first.close()
'''


@pytest.fixture
def installed(tmp_path):
    bundle = os.environ.get('FRAMEVIZ_ACCEPTANCE_APP_BUNDLE')
    python = os.environ.get('FRAMEVIZ_ACCEPTANCE_PYTHON')
    if not bundle or not python:
        pytest.skip('Explicit packaged App and separately installed-wheel interpreter required')
    home = tmp_path / 'user'
    home.mkdir()
    app = home / 'Applications/FrameViz.app'
    shutil.copytree(pathlib.Path(bundle).resolve(), app)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        cp = sock.getsockname()[1]
    env = {k: v for k, v in os.environ.items() if not k.startswith('FRAMEVIZ_')}
    env.update(HOME=str(home), CFFIXED_USER_HOME=str(home), FRAMEVIZ_HOME=str(home / 'state'),
               FRAMEVIZ_DISCOVERY_PATH=str(home / 'state/host.json'),
               FRAMEVIZ_LOG_DIR=str(home / 'logs'), FRAMEVIZ_TAURI_CONTROL_PORT=str(cp),
               FRAMEVIZ_WS_SERVER_LOG=str(home / 'bootstrap.log'), PATH='/usr/bin:/bin:/usr/sbin:/sbin')
    return home, app, pathlib.Path(python).absolute(), env, cp


def test_python_cold_starts_installed_app_without_path_override(installed, observer):
    home, app, python, env, _ = installed
    result = subprocess.run([str(python), '-B', '-c', PROGRAM, str(observer), '1'],
                            env=env, cwd=home, text=True, capture_output=True, timeout=45)
    (home / 'python.log').write_text(result.stdout + result.stderr)
    assert result.returncode == 0, result.stdout + result.stderr
    record = json.loads((home / 'result.json').read_text())
    # Normal interpreter exit must clean up the host it started.
    for _ in range(100):
        try:
            os.kill(record['pid'], 0)
        except ProcessLookupError:
            break
        time.sleep(.05)
    else:
        pytest.fail('Python-owned App remained alive after interpreter exit')


def test_python_reuses_a_manually_started_app_and_leaves_it_running(installed, observer):
    home, app, python, env, cp = installed
    with (home / 'manual-app.log').open('w') as log:
        process = subprocess.Popen([str(app / 'Contents/MacOS/frameviz'), '--headless'],
                                   env=env, cwd=home, stdout=log, stderr=log)
        try:
            ready = False
            for _ in range(200):
                assert process.poll() is None
                try:
                    ready = ping(cp)
                except (OSError, ValueError):
                    pass
                if ready and (home / 'state/host.json').exists():
                    break
                time.sleep(.05)
            assert ready
            result = subprocess.run([str(python), '-B', '-c', PROGRAM, str(observer), '0'],
                                    env=env, cwd=home, text=True, capture_output=True, timeout=45)
            (home / 'python.log').write_text(result.stdout + result.stderr)
            assert result.returncode == 0, result.stdout + result.stderr
            assert json.loads((home / 'result.json').read_text())['pid'] == process.pid
            assert process.poll() is None and ping(cp)
        finally:
            if process.poll() is None:
                process.terminate()
            process.wait(timeout=10)


def test_installed_host_survives_starting_python_process_exit(installed):
    home, _, python, env, _ = installed
    exercise_shared_runtime(home, python, env)
    for role in ('owner', 'peer'):
        record = json.loads((home / f'{role}-ready.json').read_text())
        assert pathlib.Path(record['sdk']).resolve().is_relative_to(python.parent.parent.resolve())
