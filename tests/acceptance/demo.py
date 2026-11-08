"""Start a disposable manual acceptance scene; Ctrl+C removes only this session."""
import argparse, functools, http.server, json, os, pathlib, signal, socket, subprocess, tempfile, threading, time, webbrowser
import numpy as np
from frameviz.client import FrameVizClient
from frameviz.viz import Viz
ROOT=pathlib.Path(__file__).resolve().parents[2]
STL=b'solid demo\nfacet normal 0 0 1\nouter loop\nvertex -1 -1 0\nvertex 1 -1 0\nvertex 0 1 0\nendloop\nendfacet\nendsolid demo\n'
class Handler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        if self.path=='/demo.stl':
            self.send_response(200);self.send_header('Content-Type','model/stl');self.end_headers();self.wfile.write(STL)
        else: super().do_GET()
def server(directory):
    obj=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(Handler,directory=str(directory)))
    threading.Thread(target=obj.serve_forever,daemon=True).start();return obj
def free_port():
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));return sock.getsockname()[1]
def populate(client,scene,view,model=False):
    viz=Viz(client,scene,view,owns_view=False)
    viz.add_box(pos=(-1,0,0),color=(.2,.65,.9));viz.add_sphere(pos=(1,0,0),color=(.85,.3,.15))
    viz.add_points(np.array([[0,0,0],[0,1,0],[1,1,1]],np.float32),size=10,color=(.8,.1,.6))
    model_handle=None
    if model:
        model_handle=viz.load_mesh('/demo.stl',color=(.2,.8,.3));viz.set_transform(model_handle,pos=(0,2,0))
    viz.set_camera_pose((7,-9,7),(0,1,0))
    return viz,model_handle
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--vue-dist',type=pathlib.Path,default=ROOT/'packages/frameviz-vue/dist-acceptance')
    parser.add_argument('--no-open',action='store_true');parser.add_argument('--duration',type=float,default=0)
    args=parser.parse_args()
    if not (ROOT/'packages/frameviz-web-viewer/dist/index.html').is_file():parser.error('Build the bundled viewer first')
    with tempfile.TemporaryDirectory(prefix='frameviz-manual-') as temp:
        tmp=pathlib.Path(temp);port=free_port()
        env=dict(os.environ,FRAMEVIZ_DISCOVERY_PATH=str(tmp/'host.json'),FRAMEVIZ_LOG_DIR=str(tmp/'logs'))
        with open(tmp/'host.log','w') as log:
            process=subprocess.Popen([str(ROOT/'packages/frameviz-server/target/debug/frameviz-server'),str(port)],env=env,stdout=log,stderr=log)
            client=None;servers=[]
            try:
                for _ in range(100):
                    if (tmp/'host.json').exists():break
                    if process.poll() is not None:raise RuntimeError('Isolated Host exited')
                    time.sleep(.05)
                token=json.loads((tmp/'host.json').read_text())['token']
                client=FrameVizClient(f'ws://127.0.0.1:{port}',token=token);client.connect()
                state=client.send_command('create_view',{});main_viz,model_handle=populate(client,state['scene_id'],state['view_id'],True)
                web=server(ROOT/'packages/frameviz-web-viewer/dist');servers.append(web)
                urls=[('Python / model',f'http://127.0.0.1:{web.server_port}/?ws_port={port}&view_id={state["view_id"]}#token={token}')]
                if args.vue_dist.is_dir():
                    vue=server(args.vue_dist);servers.append(vue);entry='index.html' if (args.vue_dist/'index.html').exists() else 'acceptance.html'
                    urls.append(('Vue',f'http://127.0.0.1:{vue.server_port}/{entry}?ws_port={port}#token={token}'))
                for label,url in urls:
                    print(label+': '+url,flush=True)
                    if not args.no_open:webbrowser.open(url)
                print('仅用于本次本地验收。拖动模型、旋转相机、刷新页面；Vue 按钮可卸载/重挂。Ctrl+C 结束。',flush=True)
                deadline=time.monotonic()+args.duration if args.duration else float('inf');populated=set()
                while time.monotonic()<deadline:
                    if client.wait_for_event("object_ready",timeout=.01,filter_fn=lambda event:event.get("handle")==model_handle):main_viz.attach_gizmo(model_handle)
                    for info in client.send_command('list_viewers',{})['viewers']:
                        if info['viewer_name']=='acceptance-vue' and info['view_id'] not in populated:
                            populate(client,info['scene_id'],info['view_id']);populated.add(info['view_id'])
                    time.sleep(.2)
            except KeyboardInterrupt:pass
            finally:
                if client:client.close()
                for web in servers:web.shutdown();web.server_close()
                process.terminate();process.wait(timeout=10)
if __name__=='__main__':main()
