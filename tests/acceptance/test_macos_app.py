"""Native packaged-App startup; requires an explicit App and a logged-in Mac desktop."""
import json,os,pathlib,socket,subprocess,sys,time
import pytest
ROOT=pathlib.Path(__file__).resolve().parents[2]
pytestmark=pytest.mark.skipif(sys.platform!='darwin',reason='macOS desktop required')
@pytest.fixture(scope='module')
def observer(tmp_path_factory):
 directory=tmp_path_factory.mktemp('frameviz-observer');binary=directory/'window_observer'
 subprocess.run(['clang','-fobjc-arc','-mmacosx-version-min=11.0','-framework','Foundation','-framework','CoreGraphics',str(ROOT/'tests/acceptance/native/window_observer.m'),'-o',str(binary)],check=True)
 return binary
@pytest.mark.parametrize('headless',[False,True])
def test_packaged_app_startup_visibility(tmp_path,observer,headless):
 executable=os.environ.get('FRAMEVIZ_APP_EXECUTABLE')
 if not executable:pytest.skip('Set FRAMEVIZ_APP_EXECUTABLE to an explicit packaged App executable')
 exe=pathlib.Path(executable).resolve();assert exe.is_file()
 def port():
  with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
 ws=port();cp=port()
 while cp==ws:cp=port()
 env=dict(os.environ,HOME=str(tmp_path),CFFIXED_USER_HOME=str(tmp_path),FRAMEVIZ_HOME=str(tmp_path/'state'),FRAMEVIZ_DISCOVERY_PATH=str(tmp_path/'state/host.json'),FRAMEVIZ_LOG_DIR=str(tmp_path/'logs'),FRAMEVIZ_TAURI_CONTROL_PORT=str(cp),PATH='/usr/bin:/bin:/usr/sbin:/sbin')
 env.pop('FRAMEVIZ_DEV_SERVER_URL',None);env.pop('FRAMEVIZ_USE_RUST_WS',None)
 with (tmp_path/'app.log').open('w') as log:
  p=subprocess.Popen([str(exe),'--ws-port',str(ws)]+(['--headless'] if headless else []),env=env,cwd=tmp_path,stdout=log,stderr=log)
  try:
   ready=False
   for _ in range(160):
    assert p.poll() is None
    try:
     with socket.create_connection(('127.0.0.1',cp),timeout=.3) as sock:sock.sendall(b'{"action":"ping"}\n');ready=json.loads(sock.makefile().readline())['ok']
    except (OSError,ValueError):pass
    if ready and (tmp_path/'state/host.json').exists():break
    time.sleep(.05)
   assert ready
   visible=[]
   for _ in range(20):
    visible=json.loads(subprocess.check_output([str(observer),str(p.pid)],text=True))
    if visible and not headless:break
    time.sleep(.1)
   assert bool(visible)==(not headless)
  finally:p.terminate();p.wait(timeout=10)
