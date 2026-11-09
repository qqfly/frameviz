"""Packaged App lifecycle, isolated state and PID-scoped public OS APIs."""
import contextlib,json,os,pathlib,socket,subprocess,sys,time
import pytest
ROOT=pathlib.Path(__file__).resolve().parents[2]
pytestmark=pytest.mark.skipif(sys.platform!='darwin',reason='macOS desktop required')
@pytest.fixture(scope='module')
def observer(tmp_path_factory):
 directory=tmp_path_factory.mktemp('frameviz-observer');binary=directory/'window_observer'
 subprocess.run(['clang','-fobjc-arc','-mmacosx-version-min=11.0','-framework','Foundation','-framework','CoreGraphics','-framework','ApplicationServices',str(ROOT/'tests/acceptance/native/window_observer.m'),'-o',str(binary)],check=True)
 return binary

def ping(port):
 with socket.create_connection(('127.0.0.1',port),timeout=.3) as sock:
  sock.sendall(b'{"action":"ping"}\n');return json.loads(sock.makefile().readline())['ok']

@pytest.fixture
def launch(observer):
 executable=os.environ.get('FRAMEVIZ_APP_EXECUTABLE')
 if not executable:pytest.skip('Set FRAMEVIZ_APP_EXECUTABLE to an explicit packaged App executable')
 exe=pathlib.Path(executable).resolve();assert exe.is_file()
 def port():
  with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]
 @contextlib.contextmanager
 def run(directory,headless=False):
  ws=port();cp=port()
  while cp==ws:cp=port()
  env=dict(os.environ,HOME=str(directory),CFFIXED_USER_HOME=str(directory),FRAMEVIZ_HOME=str(directory/'state'),FRAMEVIZ_DISCOVERY_PATH=str(directory/'state/host.json'),FRAMEVIZ_LOG_DIR=str(directory/'logs'),FRAMEVIZ_TAURI_CONTROL_PORT=str(cp),PATH='/usr/bin:/bin:/usr/sbin:/sbin')
  for name in ['FRAMEVIZ_DEV_SERVER_URL','FRAMEVIZ_USE_RUST_WS']:env.pop(name,None)
  with (directory/f'app-{time.time_ns()}.log').open('w') as log:
   process=subprocess.Popen([str(exe),'--ws-port',str(ws)]+(['--headless'] if headless else []),env=env,cwd=directory,stdout=log,stderr=log)
   try:
    ready=False
    for _ in range(160):
     assert process.poll() is None,'App exited during startup'
     try:ready=ping(cp)
     except (OSError,ValueError):pass
     if ready and (directory/'state/host.json').exists():break
     time.sleep(.05)
    assert ready
    yield process,cp
   finally:
    if process.poll() is None:process.terminate()
    process.wait(timeout=10)
 return run

def expect_visible(observer,process,expected):
 windows=[]
 for _ in range(20):
  windows=json.loads(subprocess.check_output([str(observer),str(process.pid)],text=True))
  if windows and expected:break
  time.sleep(.1)
 assert bool(windows)==expected

@pytest.mark.parametrize('headless',[False,True])
def test_packaged_app_startup_visibility(tmp_path,observer,launch,headless):
 with launch(tmp_path,headless) as (process,_):expect_visible(observer,process,not headless)

def test_welcome_only_on_first_manual_launch(tmp_path,observer,launch):
 with launch(tmp_path) as (process,_):expect_visible(observer,process,True)
 with launch(tmp_path) as (process,cp):
  expect_visible(observer,process,False)
  assert process.poll() is None and ping(cp)

def test_headless_does_not_consume_first_manual_welcome(tmp_path,observer,launch):
 with launch(tmp_path,True) as (process,_):expect_visible(observer,process,False)
 with launch(tmp_path) as (process,_):expect_visible(observer,process,True)

def test_closing_welcome_keeps_host_available(tmp_path,observer,launch):
 with launch(tmp_path) as (process,cp):
  expect_visible(observer,process,True)
  result=json.loads(subprocess.check_output([str(observer),str(process.pid),'--close'],text=True))
  if not result['available']:pytest.skip('PID-scoped native close needs existing Accessibility permission')
  assert result['closed'],result
  expect_visible(observer,process,False)
  assert process.poll() is None and ping(cp),'Closing welcome stopped the Host'

def test_help_menu_can_reopen_welcome(tmp_path,observer,launch):
 with launch(tmp_path) as (process,cp):
  expect_visible(observer,process,True)
  closed=json.loads(subprocess.check_output([str(observer),str(process.pid),'--close'],text=True))
  if not closed['available']:pytest.skip('PID-scoped native menu needs existing Accessibility permission')
  assert closed['closed'],closed
  result=json.loads(subprocess.check_output([str(observer),str(process.pid),'--guide'],text=True))
  assert result['opened'],result
  expect_visible(observer,process,True)
  assert process.poll() is None and ping(cp)
