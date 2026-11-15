"""High-level open against an actual runtime in a disposable user home.

Executable path overrides, ports and tokens are not configured. The SDK here is
the source checkout; clean wheel/native installer checks are separate tasks.
Linux exercises the default headless route; macOS keeps windows manual here.
"""
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import time

import pytest
import frameviz as fv
import frameviz.host as host
import frameviz.viz as implementation
from frameviz.discovery import get_discovery_path, read_discovery_file
from frameviz.exceptions import ProtocolError
from test_standalone_viewer import BINARY, free_port


@pytest.fixture
def local_user(tmp_path,monkeypatch):
    for key in list(os.environ):
        if key.startswith('FRAMEVIZ_'):monkeypatch.delenv(key)
    monkeypatch.setenv('HOME',str(tmp_path))
    monkeypatch.setenv('CFFIXED_USER_HOME',str(tmp_path))
    monkeypatch.delenv('DISPLAY',raising=False)
    monkeypatch.delenv('WAYLAND_DISPLAY',raising=False)
    monkeypatch.setattr(host,'_get_repo_root',lambda:None)
    monkeypatch.setattr(implementation,'_get_repo_root',lambda:None)
    binary=tmp_path/'.local/bin/frameviz-server';binary.parent.mkdir(parents=True)
    shutil.copy2(BINARY,binary)
    monkeypatch.setattr(host, '_get_tauri_app_candidates', lambda _: [])
    monkeypatch.setattr(host, '_get_tauri_exec_candidates', lambda _: [])
    monkeypatch.setattr(host, '_get_appimage_candidates', lambda _: [])
    monkeypatch.setattr(host, '_standalone_candidates', lambda _: [binary])
    # Do not invoke an OS browser or a native UI during this backend test.
    monkeypatch.setattr(implementation,'_try_open_tauri',lambda *a,**k:pytest.fail('Native UI launched in a backend test'))
    try:yield tmp_path,binary
    finally:host.stop_host()


def open_backend():
    return fv.open(**({'window_mode':0} if sys.platform=='darwin' else {}),timeout=3)


def test_installed_standalone_cold_start_without_runtime_path_or_token(local_user,capsys):
    viz=open_backend()
    try:
        info=read_discovery_file();process=host._started_host_proc
        assert process is not None and process.pid==info['pid']
        handle=viz.add_box()
        assert viz.is_object_alive(handle)
        assert info['viewer_url'] and info['version']=='0.5.0'
        if sys.platform.startswith('linux'):
            output=capsys.readouterr().out
            assert info['viewer_url'] in output and '#token='+info['token'] in output
    finally:viz.close()
    host.stop_host()
    assert process.poll() is not None
    assert not get_discovery_path().exists()


def test_repeated_open_reuses_the_same_owned_runtime(local_user):
    first=open_backend();second=None
    try:
        pid=read_discovery_file()['pid'];second=open_backend()
        assert read_discovery_file()['pid']==pid
        assert first.scene_id!=second.scene_id
    finally:
        if second:second.close()
        first.close()


def test_live_incompatible_record_is_not_replaced(local_user):
    first=open_backend()
    try:
        path=get_discovery_path();info=read_discovery_file();info['version']='0.6.0'
        record=json.dumps(info);path.write_text(record)
        with pytest.raises(ProtocolError,match='Upgrade.*SDK'):open_backend()
        assert path.read_text()==record
        assert host._started_host_proc.pid==info['pid'] and host._started_host_proc.poll() is None
    finally:first.close()


def test_manually_started_runtime_is_reused_and_not_stopped(local_user,monkeypatch):
    _,binary=local_user
    process=subprocess.Popen([str(binary),str(free_port())],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
    try:
        deadline=time.monotonic()+5
        while time.monotonic()<deadline:
            info=read_discovery_file()
            if info and info.get('pid')==process.pid:break
            assert process.poll() is None
            time.sleep(.025)
        else:pytest.fail('Manual runtime not ready')
        monkeypatch.setattr(host,'find_host_executable',lambda *a,**k:pytest.fail('Second runtime launched'))
        viz=open_backend();viz.close();host.stop_host()
        assert process.poll() is None
        assert read_discovery_file()['pid']==process.pid
    finally:
        if process.poll() is None:process.send_signal(signal.SIGTERM)
        process.wait(timeout=5)


_SHARED_RUNTIME_USER = r"""
import json
from pathlib import Path
import sys
import frameviz as fv
from frameviz.discovery import read_discovery_file
from frameviz import host

role = sys.argv[1]
viz = fv.open(window_mode=0)
info = read_discovery_file()
if role == 'owner':
    assert host._started_host_proc is not None and host._started_host_proc.pid == info['pid']
else:
    assert host._started_host_proc is None
handle = viz.add_box()
ready = Path(f'{role}-ready.tmp')
ready.write_text(json.dumps({
    'pid': info['pid'], 'scene': viz.scene_id, 'sdk': fv.__file__,
}))
ready.rename(ready.with_suffix('.json'))
if role == 'owner':
    assert input() == 'close'
    viz.close()
    Path('owner-closed').touch()
    assert input() == 'exit'
else:
    for phase, x in [('after-close', 1), ('after-exit', 2)]:
        assert input() == phase
        assert viz.is_object_alive(handle)
        viz.set_transform(handle, position=[x, 0, 0])
        pose = viz.get_transform(handle)['position']
        assert pose == [x, 0, 0], pose
        progress = Path(phase + '.tmp')
        progress.write_text(json.dumps(pose))
        progress.rename(phase)
    assert input() == 'close'
    viz.close()
"""


def exercise_shared_runtime(directory, python, env):
    """Run the same two-process witness against source and installed products."""
    env = dict(env, FRAMEVIZ_HOST=f'ws://127.0.0.1:{free_port()}')
    directory = Path(directory)
    processes = {}
    owned_pid = None

    def launch(role):
        log_path = directory / f'{role}.log'
        with log_path.open('w') as log:
            processes[role] = subprocess.Popen(
                [str(python), '-B', '-c', _SHARED_RUNTIME_USER, role], cwd=directory, env=env,
                stdin=subprocess.PIPE, stdout=log, stderr=log, text=True,
            )

    def record(role, name):
        path = directory / name
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            assert processes[role].poll() is None, (directory / f'{role}.log').read_text()
            if path.exists():
                return path
            time.sleep(.025)
        pytest.fail(f'{role} did not write {name}: {(directory / f"{role}.log").read_text()}')

    def send(role, action):
        processes[role].stdin.write(action + '\n')
        processes[role].stdin.flush()

    discovery = Path(env['FRAMEVIZ_DISCOVERY_PATH'])
    try:
        launch('owner')
        owner = json.loads(record('owner', 'owner-ready.json').read_text())
        owned_pid = owner['pid']
        launch('peer')
        peer = json.loads(record('peer', 'peer-ready.json').read_text())
        assert owner['pid'] == peer['pid'] and owner['scene'] != peer['scene']

        send('owner', 'close')
        record('owner', 'owner-closed')
        send('peer', 'after-close')
        assert json.loads(record('peer', 'after-close').read_text()) == [1, 0, 0]

        send('owner', 'exit')
        assert processes['owner'].wait(timeout=10) == 0
        send('peer', 'after-exit')
        assert json.loads(record('peer', 'after-exit').read_text()) == [2, 0, 0]
        assert json.loads(discovery.read_text())['pid'] == owned_pid

        send('peer', 'close')
        assert processes['peer'].wait(timeout=10) == 0
        deadline = time.monotonic() + 8
        while discovery.exists() and time.monotonic() < deadline:
            time.sleep(.025)
        assert not discovery.exists(), 'SDK-managed Host did not clear its discovery after the final client left'
        while host._pid_is_running(owned_pid) and time.monotonic() < deadline:
            time.sleep(.025)
        assert not host._pid_is_running(owned_pid), 'SDK-managed Host did not exit after the final client left'
    finally:
        for process in processes.values():
            if process.poll() is None:
                process.kill()
            process.wait(timeout=5)
            process.stdin.close()
        if owned_pid and discovery.exists() and json.loads(discovery.read_text())['pid'] == owned_pid:
            try:
                os.kill(owned_pid, signal.SIGTERM)
            except ProcessLookupError:
                pass


def test_automatically_started_host_survives_owner_close_and_exit(local_user):
    directory, binary = local_user
    env = dict(os.environ, FRAMEVIZ_HOST_PATH=str(binary),
               FRAMEVIZ_HOME=str(directory / 'state'),
               FRAMEVIZ_DISCOVERY_PATH=str(directory / 'state/host.json'),
               PYTHONPATH=str(Path(fv.__file__).resolve().parents[1]))
    exercise_shared_runtime(directory, sys.executable, env)
