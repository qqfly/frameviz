"""Independent-project identity and version boundaries with synthetic inputs."""
import hashlib,importlib.util,json,os,pathlib,socket,subprocess,time
import pytest
ROOT=pathlib.Path(__file__).resolve().parents[2]

def test_project_license_and_source_assets():
 assert 'Copyright (c) 2026 qqfly' in (ROOT/'LICENSE').read_text()
 assert 'MIT' in (ROOT/'LICENSE').read_text()
 m=json.loads((ROOT/'artwork/asset-manifest.json').read_text())
 for name,digest in m['files'].items():assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
 assert json.loads((ROOT/'version.json').read_text())['project_id']=='qqfly.frameviz'

def test_python_state_root_override(tmp_path,monkeypatch):
 from frameviz.discovery import get_discovery_path
 monkeypatch.delenv('FRAMEVIZ_DISCOVERY_PATH',raising=False);monkeypatch.setenv('FRAMEVIZ_HOME',str(tmp_path))
 assert get_discovery_path()==tmp_path/'host.json'

@pytest.fixture
def host(tmp_path,monkeypatch):
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 env=dict(os.environ,HOME=str(tmp_path),FRAMEVIZ_HOME=str(tmp_path/'state'),FRAMEVIZ_LOG_DIR=str(tmp_path/'logs'))
 env.pop('FRAMEVIZ_DISCOVERY_PATH',None)
 monkeypatch.setenv('FRAMEVIZ_DISCOVERY_PATH',str(tmp_path/'unconfigured-client.json'));monkeypatch.delenv('FRAMEVIZ_AUTH_TOKEN',raising=False)
 with (tmp_path/'host.log').open('w') as log:
  proc=subprocess.Popen([str(ROOT/'packages/frameviz-server/target/debug/frameviz-server'),str(port)],env=env,stdout=log,stderr=log)
  try:
   for _ in range(100):
    if (tmp_path/'state/host.json').exists():break
    if proc.poll() is not None:raise RuntimeError('Host exited')
    time.sleep(.03)
   yield f'ws://127.0.0.1:{port}',json.loads((tmp_path/'state/host.json').read_text())['token']
  finally:proc.terminate();proc.wait(timeout=10)

@pytest.mark.parametrize('version',[None,'0.3.4','99.0.0'])
def test_missing_and_old_versions_are_rejected_without_scene_creation(host,version):
 from websockets.sync.client import connect
 from frameviz.client import FrameVizClient
 url,token=host
 with connect(url) as ws:
  ws.send(json.dumps({'type':'auth','token':token}));assert json.loads(ws.recv())['ok']
  cmd={'type':'cmd','id':'version-test','name':'create_scene','args':{}}
  if version is not None:cmd['protocol_version']=version
  ws.send(json.dumps(cmd));reply=json.loads(ws.recv());assert not reply['ok'] and reply['error']['code']=='ERR_PROTOCOL_VERSION'
 client=FrameVizClient(url,token=token);client.connect()
 try:assert client.send_command('list_scenes')=={'scenes':[]}
 finally:client.close()

def test_unauthenticated_sdk_connect_fails_immediately(host):
 from frameviz.client import FrameVizClient
 url,_=host;client=FrameVizClient(url,timeout=1)
 with pytest.raises(Exception,match='Authentication token required'):client.connect()


def test_default_state_does_not_use_a_legacy_directory(tmp_path,monkeypatch):
 from frameviz.discovery import get_discovery_path
 monkeypatch.delenv('FRAMEVIZ_DISCOVERY_PATH',raising=False);monkeypatch.delenv('FRAMEVIZ_HOME',raising=False);monkeypatch.setenv('HOME',str(tmp_path))
 if os.name!='nt':assert get_discovery_path()==tmp_path/'.local/share/qqfly/frameviz/host.json'

def test_autostart_does_not_select_an_unrelated_path_command(tmp_path,monkeypatch):
 import frameviz.host as host
 binary=tmp_path/'frameviz';binary.write_text('#!/bin/sh\nexit 0\n');binary.chmod(0o755)
 monkeypatch.setenv('PATH',str(tmp_path));monkeypatch.delenv('FRAMEVIZ_HOST_PATH',raising=False)
 monkeypatch.setattr(host,'_get_repo_root',lambda:None)
 monkeypatch.setattr(host,'_get_tauri_app_candidates',lambda root:[])
 assert host.find_host_executable() is None


def test_no_unconfigured_application_name_launch(monkeypatch):
 import frameviz.viz as viz
 monkeypatch.setattr(viz.sys,'platform','darwin');monkeypatch.delenv('FRAMEVIZ_TAURI_APP',raising=False)
 monkeypatch.setattr(viz,'_get_repo_root',lambda:None)
 monkeypatch.setattr(viz,'_get_tauri_app_candidates',lambda root:[])
 monkeypatch.setattr(viz,'_launch_macos_app',lambda *args:pytest.fail('Unexpected global app-name launch'))
 assert not viz._try_open_tauri()

def test_unauthenticated_relay_is_disabled():
 result=subprocess.run(['node',str(ROOT/'packages/frameviz-web-viewer/bridge.mjs')],capture_output=True,text=True)
 assert result.returncode==2 and 'authenticated Rust Host' in result.stderr


def test_rust_default_namespace_preserves_a_legacy_record(tmp_path):
 legacy=tmp_path/'.frameviz/host.json';legacy.parent.mkdir();legacy.write_text('synthetic legacy sentinel')
 with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
 env=dict(os.environ,HOME=str(tmp_path),FRAMEVIZ_LOG_DIR=str(tmp_path/'logs'))
 for name in ['FRAMEVIZ_HOME','FRAMEVIZ_DISCOVERY_PATH']:env.pop(name,None)
 with (tmp_path/'namespace.log').open('w') as log:
  proc=subprocess.Popen([str(ROOT/'packages/frameviz-server/target/debug/frameviz-server'),str(port)],env=env,stdout=log,stderr=log)
  try:
   expected=tmp_path/'.local/share/qqfly/frameviz/host.json'
   for _ in range(100):
    if expected.exists():break
    time.sleep(.03)
   assert expected.is_file() and legacy.read_text()=='synthetic legacy sentinel'
  finally:proc.terminate();proc.wait(timeout=10)


def test_repo_detection_requires_standalone_identity(tmp_path):
 from frameviz._internal import _looks_like_repo_root
 (tmp_path/'pnpm-workspace.yaml').write_text('packages: []')
 (tmp_path/'packages/frameviz-host-tauri').mkdir(parents=True)
 assert not _looks_like_repo_root(tmp_path)
 for manifest in [ {'protocol_version':'0.5.0'}, {'project_id':'other.frameviz','protocol_version':'0.5.0'}, {'project_id':'qqfly.frameviz','protocol_version':'0.3.4'} ]:
  (tmp_path/'version.json').write_text(json.dumps(manifest))
  assert not _looks_like_repo_root(tmp_path)
 (tmp_path/'version.json').write_text(json.dumps({'project_id':'qqfly.frameviz','protocol_version':'0.5.0'}))
 assert _looks_like_repo_root(tmp_path)
