"""Run the isolated app identity; never launch or replace the installed FrameViz app."""
import json, os, pathlib, plistlib, shutil, socket, subprocess, tempfile, time
from frameviz.client import FrameVizClient
from frameviz.viz import Viz
from host_smoke import free_port
ROOT=pathlib.Path(__file__).resolve().parents[2];OUT=pathlib.Path(os.environ.get('FRAMEVIZ_EVIDENCE',ROOT/'.validation/evidence'))
def control(port,payload):
    with socket.create_connection(('127.0.0.1',port),timeout=3) as conn:
        conn.sendall(json.dumps(payload).encode()+b'\n');return json.loads(conn.makefile().readline())
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    explicit=os.environ.get('FRAMEVIZ_NATIVE_APP_EXECUTABLE')
    if explicit:
        exe=pathlib.Path(explicit).resolve()
        if not exe.is_file():raise RuntimeError('Explicit native executable missing')
        app=next((parent for parent in exe.parents if parent.suffix=='.app'),None)
        if app is None:raise RuntimeError('Use an executable inside an explicit .app bundle')
        identity=plistlib.loads((app/'Contents/Info.plist').read_bytes())['CFBundleIdentifier']
    else:
        app=OUT/'native/FrameViz Standalone Validation.app';exe=app/'Contents/MacOS/frameviz';exe.parent.mkdir(parents=True,exist_ok=True)
        shutil.copy2(ROOT/'packages/frameviz-host-tauri/src-tauri/target/debug/frameviz',exe)
        identity='dev.qqfly.frameviz.validation'
        (app/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleIdentifier':identity,'CFBundleName':'FrameViz Standalone Validation','CFBundleExecutable':'frameviz','CFBundlePackageType':'APPL','CFBundleVersion':'0.4.0'}))
    with tempfile.TemporaryDirectory(prefix='frameviz-native-') as temp:
        tmp=pathlib.Path(temp);port=free_port();cp=free_port()
        env=dict(os.environ,HOME=str(tmp),CFFIXED_USER_HOME=str(tmp),FRAMEVIZ_HOME=str(tmp/'state'),PATH='/usr/bin:/bin:/usr/sbin:/sbin',FRAMEVIZ_DISCOVERY_PATH=str(tmp/'host.json'),FRAMEVIZ_LOG_DIR=str(tmp/'logs'),FRAMEVIZ_TAURI_CONTROL_PORT=str(cp),FRAMEVIZ_HTTP_SERVER='0')
        with open(OUT/'native-runtime.log','w') as log:
            process=subprocess.Popen([str(exe),'--ws-port',str(port),'--headless'],env=env,cwd=tmp,stdout=log,stderr=log)
            client=None
            try:
                for _ in range(200):
                    if (tmp/'host.json').exists():break
                    if process.poll() is not None:raise RuntimeError('Native process exited')
                    time.sleep(.05)
                token=json.loads((tmp/'host.json').read_text())['token'];url=f'ws://127.0.0.1:{port}'
                client=FrameVizClient(url,token=token);client.connect();state=client.send_command('create_view',{'title':'Native acceptance'})
                for _ in range(200):
                    try:
                        if control(cp,{'action':'ping'})['ok']: break
                    except OSError: time.sleep(.05)
                assert not control(cp,{'action':'open_view','view_id':state['view_id']})['ok']
                result=control(cp,{'action':'open_view','view_id':state['view_id'],'scene_id':state['scene_id'],'title':'FrameViz isolated native acceptance','token':token,'width':1000,'height':700})
                assert result['ok'],result
                viz=Viz(client,state['scene_id'],state['view_id'],owns_view=False)
                assert viz.wait_for_viewer(timeout=15)
                viz.add_box(color=(.15,.65,.35));viz.add_sphere(pos=(2,0,0),color=(.8,.25,.2))
                viz.set_camera_pose((5,-7,5),(0,0,0));pose=viz.get_camera_pose()
                assert all(abs(a-b)<1e-5 for a,b in zip(pose['eye'],[5,-7,5])),pose
                print('PASS isolated native window authenticates, constructs core, accepts scene commands and answers live camera query; unauthenticated control rejected',flush=True)
                (OUT/'native-result.json').write_text(json.dumps({'passed':True,'identity':identity,'camera':pose,'window':'FrameViz isolated native acceptance','manual_interaction':'not tested'},indent=2))
                # Optional short inspection window for native screenshots.
                time.sleep(float(os.environ.get('FRAMEVIZ_NATIVE_INSPECT_SECONDS','0')))
            finally:
                if client:client.close()
                process.terminate();process.wait(timeout=10)
if __name__=='__main__':main()
