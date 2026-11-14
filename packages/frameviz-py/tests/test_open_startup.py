"""User-facing startup decisions and error boundaries, without a real desktop."""
import json
import os
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import frameviz.viz as implementation
import frameviz.host as host
import frameviz._internal as internal
from frameviz.exceptions import ProtocolError, ConnectionError


@pytest.fixture
def context(monkeypatch,tmp_path):
    for key in ['FRAMEVIZ_HOST_PATH','FRAMEVIZ_TAURI_APP','FRAMEVIZ_BROWSER','FRAMEVIZ_HOST']:
        monkeypatch.delenv(key,raising=False)
    monkeypatch.setenv('FRAMEVIZ_DISCOVERY_PATH',str(tmp_path/'host.json'))
    monkeypatch.setattr(host,'_desktop_available',lambda:True)
    monkeypatch.setattr(host,'_is_port_open',lambda *a,**k:False)
    client=MagicMock()
    client.url='ws://127.0.0.1:9527'
    client.send_command.side_effect=lambda name,args: {'scene_id':'s'} if name=='create_scene' else {'view_id':'v'}
    monkeypatch.setattr(implementation,'FrameVizClient',lambda **kwargs:client)
    monkeypatch.setattr(implementation,'_wait_for_viewer',lambda *a,**k:True)
    monkeypatch.setattr(implementation,'_try_open_tauri_window',lambda *a,**k:False)
    monkeypatch.setattr(implementation,'_try_open_tauri',lambda *a,**k:False)
    monkeypatch.setattr(implementation,'_maybe_auto_start_ws',lambda *a,**k:pytest.fail('Legacy fallback unexpectedly called'))
    monkeypatch.setattr(host,'start_host',lambda *a,**k:'ws://127.0.0.1:9527')
    return client,tmp_path/'host.json'


def test_running_host_does_not_start_another(context,monkeypatch):
    client,_=context
    monkeypatch.setattr(host,'start_host',lambda *a,**k:pytest.fail('Started a second Host'))
    viz=implementation.open(window_mode=0)
    assert viz.scene_id=='s'


def test_incompatible_handshake_is_not_retried_or_replaced(context,monkeypatch):
    client,_=context
    client.connect.side_effect=ProtocolError('Upgrade the FrameViz runtime',code='ERR_PROTOCOL_VERSION')
    monkeypatch.setattr(host,'start_host',lambda *a,**k:pytest.fail('Incompatible Host replaced'))
    with pytest.raises(ProtocolError,match='Upgrade'):implementation.open(window_mode=0)
    assert client.connect.call_count==1


def test_auth_failure_does_not_start_a_runtime(context,monkeypatch):
    client,_=context
    client.connect.side_effect=ProtocolError('Authentication failed',code='AUTH_FAILED')
    monkeypatch.setattr(host,'start_host',lambda *a,**k:pytest.fail('Auth failure replaced Host'))
    with pytest.raises(ProtocolError,match='Authentication failed'):implementation.open(window_mode=0)


def test_viewer_address_is_read_after_cold_start(context,monkeypatch):
    client,discovery=context
    client.connect.side_effect=[ConnectionError('not running'),None]
    def start(*args,**kwargs):
        discovery.write_text(json.dumps({'viewer_url':'http://127.0.0.1:18182/','ws_url':client.url,'token':'temporary-test-token'}))
        return client.url
    monkeypatch.setattr(host,'start_host',start)
    opened=[]
    monkeypatch.setattr(implementation.webbrowser,'open',lambda url:opened.append(url) or True)
    implementation.open(window_mode=1)
    assert opened and opened[0].startswith('http://127.0.0.1:18182/')
    assert '#token=temporary-test-token' in opened[0]


def test_no_runtime_error_contains_platform_installation_guidance(monkeypatch,tmp_path):
    monkeypatch.setattr(host,'find_host_executable',lambda *a,**k:None)
    monkeypatch.setattr(host,'_maybe_auto_start_ws',lambda *a,**k:(False,'not installed',None))
    monkeypatch.setenv('FRAMEVIZ_DISCOVERY_PATH',str(tmp_path/'none.json'))
    monkeypatch.setattr(host.sys,'platform','linux')
    with pytest.raises(RuntimeError,match='apt install|INSTALLATION.md'):host.start_host(timeout=.1)


@pytest.mark.parametrize('missing_override', [False, True])
def test_windows_runtime_errors_explain_installed_app_path(monkeypatch, tmp_path, missing_override):
    monkeypatch.setattr(host.sys, 'platform', 'win32')
    monkeypatch.setattr(host, '_get_repo_root', lambda: None)
    monkeypatch.setattr(host, '_standalone_candidates', lambda _: [])
    monkeypatch.setenv('FRAMEVIZ_DISCOVERY_PATH', str(tmp_path / 'host.json'))
    for key in ('FRAMEVIZ_HOST_PATH', 'FRAMEVIZ_TAURI_APP', 'FRAMEVIZ_WS_SERVER_CMD'):
        monkeypatch.delenv(key, raising=False)
    if missing_override:
        monkeypatch.setenv('FRAMEVIZ_TAURI_APP', str(tmp_path / 'missing.exe'))
    with pytest.raises(RuntimeError) as error:
        host.start_host(timeout=.1)
    message = str(error.value)
    assert "$env:FRAMEVIZ_TAURI_APP" in message
    assert 'frameviz.exe' in message and '#windows-x64-trial' in message
    if missing_override:
        assert 'missing.exe' in message


def test_source_and_installed_runtime_search_respects_explicit_host_path(tmp_path,monkeypatch):
    binary=tmp_path/'frameviz-server';binary.write_text('#!/bin/sh\nexit 0\n');binary.chmod(0o755)
    monkeypatch.setenv('FRAMEVIZ_HOST_PATH',str(binary))
    monkeypatch.setenv('FRAMEVIZ_TAURI_APP',str(tmp_path/'not-selected'))
    assert host.find_host_executable()==binary


def test_headless_default_prints_link_without_launching_a_window(context,monkeypatch,capsys):
    client,discovery=context
    discovery.write_text(json.dumps({'viewer_url':'http://127.0.0.1:18182/','ws_url':client.url,'token':'temporary-test-token'}))
    monkeypatch.setattr(host,'_desktop_available',lambda:False)
    monkeypatch.setattr(implementation.webbrowser,'open',lambda *a:pytest.fail('Desktop browser launched'))
    implementation.open()
    assert '#token=temporary-test-token' in capsys.readouterr().out


def test_disabled_autostart_does_not_start_next_to_an_unknown_default_service(context,monkeypatch):
    monkeypatch.setenv('FRAMEVIZ_AUTO_START_WS','0')
    monkeypatch.setattr(host,'_is_port_open',lambda *a,**k:True)
    monkeypatch.setattr(host,'start_host',lambda *a,**k:pytest.fail('Auto-start was disabled'))
    with pytest.raises(RuntimeError,match='disabled'):implementation.open(window_mode=0)


@pytest.mark.parametrize('record',[{}, {'viewer_url':'http://127.0.0.1:18182/','ws_url':'ws://127.0.0.1:17171','token':'another-test-token'}])
def test_browser_never_guesses_a_viewer_for_an_unmatched_runtime(context,monkeypatch,record):
    _,discovery=context;discovery.write_text(json.dumps(record))
    monkeypatch.setattr(implementation.webbrowser,'open',lambda *a:pytest.fail('Unmatched Viewer opened'))
    with pytest.raises(RuntimeError,match='Viewer'):implementation.open(window_mode=1)


def test_failed_page_open_cleans_up_the_scene_and_view_it_created(context,monkeypatch):
    client,discovery=context
    discovery.write_text(json.dumps({'viewer_url':'http://127.0.0.1:18182/','ws_url':client.url,'token':'temporary-test-token'}))
    def failed(*a,**k):raise RuntimeError('Synthetic page opening failure')
    monkeypatch.setattr(implementation,'_open_browser',failed)
    with pytest.raises(RuntimeError,match='Synthetic'):implementation.open(window_mode=1)
    names=[call.args[0] for call in client.send_command.call_args_list]
    assert 'destroy_view' in names and 'destroy_scene' in names
    client.close.assert_called()


def test_runtime_exit_explains_the_actual_startup_error(tmp_path,monkeypatch):
    # This is a diagnostic-formatting unit check. An OS scheduler delaying a
    # fresh shell must not turn it into a test of a 200 ms process-start budget.
    # Real runtime process failures are covered by test_standalone_viewer.py.
    binary=tmp_path/'broken-runtime'
    binary.write_text('#!/bin/sh\necho "Synthetic runtime startup failure" >&2\nexit 7\n');binary.chmod(0o755)
    monkeypatch.setenv('FRAMEVIZ_HOST_PATH',str(binary))
    monkeypatch.setenv('FRAMEVIZ_DISCOVERY_PATH',str(tmp_path/'host.json'))
    logfile=tmp_path/'startup.log';logfile.write_text('Synthetic runtime startup failure\n')
    monkeypatch.setattr(host,'_started_host_log_path',logfile)
    exited=MagicMock();exited.poll.return_value=7
    monkeypatch.setattr(host,'_launch_executable',lambda *a,**k:exited)
    with pytest.raises(RuntimeError,match='Synthetic runtime startup failure'):host.start_host(timeout=.2)


def test_public_open_exposes_manual_callback_mode(context,monkeypatch):
    client,_=context
    options=[]
    def factory(**kwargs):
        options.append(kwargs)
        return client
    monkeypatch.setattr(implementation,'FrameVizClient',factory)
    implementation.open(window_mode=0,auto_events=False)
    assert options[0]['auto_events'] is False


def test_explicit_environment_endpoint_is_not_replaced_by_discovery(context, monkeypatch):
    _, discovery = context
    discovery.write_text(json.dumps({
        "ws_url": "ws://127.0.0.1:18355", "port": 18355, "pid": os.getpid(), "version": "0.5.0",
    }))
    monkeypatch.setattr(internal, "_resolve_discovery_port", lambda _: 18355)
    monkeypatch.setenv("FRAMEVIZ_HOST", "ws://127.0.0.1:9527")
    assert implementation._resolve_connection_url(None) == "ws://127.0.0.1:9527"
