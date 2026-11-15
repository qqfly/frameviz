"""Exercise the actual Rust process; use only an isolated discovery file."""
import json, os, socket, subprocess, tempfile, time, pathlib
from frameviz.client import FrameVizClient
from websockets.sync.client import connect
ROOT = pathlib.Path(__file__).resolve().parents[2]
def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0)); return sock.getsockname()[1]
def run():
    with tempfile.TemporaryDirectory(prefix='frameviz-acceptance-') as tmp:
        port = free_port(); url = f'ws://127.0.0.1:{port}'
        env = dict(os.environ, FRAMEVIZ_DISCOVERY_PATH=f'{tmp}/host.json', FRAMEVIZ_LOG_DIR=f'{tmp}/logs')
        with open(f'{tmp}/host.log','w') as log:
            host = subprocess.Popen([str(ROOT/'packages/frameviz-server/target/debug/frameviz-server'),str(port)], env=env, stdout=log, stderr=log)
            try:
                for _ in range(100):
                    if pathlib.Path(f'{tmp}/host.json').exists(): break
                    time.sleep(.05)
                info = json.loads(pathlib.Path(f'{tmp}/host.json').read_text())
                client = FrameVizClient(url, token=info['token']); client.connect()
                scene = client.send_command('create_scene', {})['scene_id']
                view = client.send_command('create_view', {'scene_id':scene})['view_id']
                with connect(url+f'?type=viewer&view_id={view}', origin='http://localhost:8080') as viewer:
                    try:
                        viewer.recv(timeout=.2)
                        raise AssertionError('Unauthenticated snapshot leaked')
                    except TimeoutError: pass
                    viewer.send(json.dumps({'type':'auth','token':info['token']}))
                    assert json.loads(viewer.recv(timeout=2))['ok']
                    assert json.loads(viewer.recv(timeout=2))['type']=='init'
                    assert json.loads(viewer.recv(timeout=2))['type']=='scene_snapshot'
                    result = client.send_command('add_primitive',{'scene_id':scene,'type':'box'})
                    msg=json.loads(viewer.recv(timeout=2)); assert msg['type']=='sync' and msg['result']==result
                    try:
                        viewer.recv(timeout=.2); raise AssertionError('Duplicate command delivery')
                    except TimeoutError: pass
                    viewer.send(json.dumps({'protocol_version':'0.5.0','type':'cmd','id':'attack','name':'destroy_scene','args':{'scene_id':scene}}))
                    denied=json.loads(viewer.recv(timeout=2)); assert not denied['ok']
                try:
                    with connect(url,origin='https://untrusted.example'): raise AssertionError('Origin was accepted')
                except Exception as error:
                    assert '403' in str(error),str(error)
                client.close()
                print('PASS: authenticated SDK, no pre-auth disclosure, committed sync once, viewer privilege denial, Origin denial')
            finally:
                host.terminate(); host.wait(timeout=10)
if __name__=='__main__': run()
