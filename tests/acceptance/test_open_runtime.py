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
        assert info['viewer_url'] and info['version']=='0.4.0'
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
        path=get_discovery_path();info=read_discovery_file();info['version']='0.5.0'
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
