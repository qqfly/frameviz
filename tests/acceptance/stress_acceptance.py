"""Concurrent upload hashes and 1000 create/remove cycles on the actual viewer."""
import base64, concurrent.futures, hashlib, json, os, pathlib, subprocess, tempfile, time
import numpy as np
from playwright.sync_api import sync_playwright
from frameviz.client import FrameVizClient
from frameviz.viz import Viz
from host_smoke import free_port
from browser_acceptance import serve
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=pathlib.Path(os.environ.get('FRAMEVIZ_EVIDENCE', ROOT/'.validation/evidence'))
def run():
    OUT.mkdir(parents=True,exist_ok=True);results={}
    with tempfile.TemporaryDirectory(prefix='frameviz-stress-') as temp:
        tmp=pathlib.Path(temp);port=free_port();url=f'ws://127.0.0.1:{port}'
        env=dict(os.environ,FRAMEVIZ_DISCOVERY_PATH=str(tmp/'host.json'),FRAMEVIZ_LOG_DIR=str(tmp/'logs'))
        log=open(OUT/'stress-host.log','w');process=subprocess.Popen([str(ROOT/'packages/frameviz-server/target/debug/frameviz-server'),str(port)],env=env,stdout=log,stderr=log)
        server=serve(ROOT/'packages/frameviz-web-viewer/dist');clients=[]
        try:
            for _ in range(100):
                if (tmp/'host.json').exists():break
                time.sleep(.05)
            token=json.loads((tmp/'host.json').read_text())['token']
            for _ in range(2):
                c=FrameVizClient(url,token=token,timeout=30);c.connect();clients.append(c)
            state=clients[0].send_command('create_view',{});scene,view=state['scene_id'],state['view_id']
            viz=[Viz(c,scene,view,owns_view=False) for c in clients]
            with sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True,args=['--use-angle=swiftshader','--enable-webgl'])
                page=browser.new_page();page.goto(f'http://127.0.0.1:{server.server_port}/?ws_port={port}&view_id={view}#token={token}')
                page.wait_for_function('document.querySelector("#status").textContent.includes("→")')
                sizes=[4096,25000,100000,1500000]
                def upload(i):
                    points=(np.arange(sizes[i]*3,dtype=np.float32)%997).reshape(-1,3)/997
                    start=time.monotonic()
                    if i == 3:
                        c=clients[i%2];raw=points.tobytes();bid=c.send_command('create_buffer',{'size_bytes':len(raw),'dtype':'f32','shape':list(points.shape)})['buffer_id']
                        for offset in range(0,len(raw),16*1024*1024):
                            chunk=raw[offset:offset+16*1024*1024]
                            c.send_command_with_binary('upload_buffer_chunk',{'buffer_id':bid,'offset_bytes':offset,'chunk_bytes':len(chunk)},chunk)
                        handle=c.send_command('add_points',{'scene_id':scene,'positions':{'buffer_id':bid,'dtype':'f32','shape':list(points.shape)},'size':1})['handle']
                        c.send_command('free_buffer',{'buffer_id':bid})
                    else:
                        handle=viz[i%2].add_points(points,size=1)
                    return handle,hashlib.sha256(points.tobytes()).hexdigest(),time.monotonic()-start,points.nbytes
                with concurrent.futures.ThreadPoolExecutor(4) as pool: uploads=list(pool.map(upload,range(4)))
                page.wait_for_function('window.__FRAMEVIZ_CORE__.objects.size===4',timeout=60000)
                async_hash='''async(h)=>{let c=window.__FRAMEVIZ_CORE__,o=c.objects.get(h),id=o.userData.bufferIds[0],e=c.buffers.get(id),d=e.data;const b=ArrayBuffer.isView(d)?new Uint8Array(d.buffer,d.byteOffset,d.byteLength):new Uint8Array(d);return [...new Uint8Array(await crypto.subtle.digest('SHA-256',b))].map(x=>x.toString(16).padStart(2,'0')).join('');}'''
                for handle,expected,_,_ in uploads: assert page.evaluate(async_hash,handle)==expected
                results['concurrent_uploads']=[{'bytes':n,'seconds':t,'sha256':h} for _,h,t,n in uploads]
                print('PASS two producers / four threads: 49KB,300KB,1.2MB,18MB Viewer hashes match input',flush=True)
                page.reload();page.wait_for_function('window.__FRAMEVIZ_CORE__.objects.size===4',timeout=60000)
                for handle,expected,_,_ in uploads: assert page.evaluate(async_hash,handle)==expected
                print('PASS same hashes after snapshot restoration',flush=True)
                for handle,_,_,_ in uploads:viz[0].remove(handle)
                page.wait_for_function('window.__FRAMEVIZ_CORE__.objects.size===0 && window.__FRAMEVIZ_CORE__.buffers.size===0')
                samples=[];latencies=[]
                for i in range(1000):
                    start=time.monotonic();handle=viz[0].add_points(np.array([[1,2,3]],np.float32));viz[0].remove(handle);latencies.append(time.monotonic()-start)
                    if (i+1)%100==0:
                        page.wait_for_function('window.__FRAMEVIZ_CORE__.objects.size===0 && window.__FRAMEVIZ_CORE__.buffers.size===0')
                        counts=clients[0].send_command('get_resource_counts',{})
                        assert counts['objects']==counts['buffers']==counts['buffer_bytes']==0,counts
                        gpu=page.evaluate('window.__FRAMEVIZ_CORE__.getSceneManager().renderer.info.memory')
                        samples.append({'cycles':i+1,'host':counts,'gpu':gpu})
                        print('PASS cycle',i+1,counts,flush=True)
                results['cycles']=samples;results['latency_seconds']={'p50':float(np.percentile(latencies,50)),'p95':float(np.percentile(latencies,95))}
                # Independent same-view and cross-view requests share one SDK connection.
                def query(_):return viz[0].get_camera_pose()
                with concurrent.futures.ThreadPoolExecutor(4) as pool: poses=list(pool.map(query,range(40)))
                assert all(np.allclose(p['eye'],poses[0]['eye']) for p in poses)
                results['concurrent_queries']=len(poses);print('PASS 40 same-view concurrent correlated queries',flush=True)
                sibling=clients[0].send_command('create_view',{'scene_id':scene})
                second=browser.new_page();second.goto(f'http://127.0.0.1:{server.server_port}/?ws_port={port}&view_id={sibling["view_id"]}#token={token}')
                second.wait_for_function('document.querySelector("#status").textContent.includes("→")')
                sibling_viz=Viz(clients[0],scene,sibling['view_id'],owns_view=False)
                viz[0].set_camera_pose((3,4,5),(0,0,0));sibling_viz.set_camera_pose((7,8,9),(0,0,0))
                def cross_query(i):
                    pose=(viz[0] if i%2==0 else sibling_viz).get_camera_pose()
                    assert np.allclose(pose['eye'],[3,4,5] if i%2==0 else [7,8,9]);return pose
                with concurrent.futures.ThreadPoolExecutor(4) as pool: cross=list(pool.map(cross_query,range(40)))
                results['cross_view_queries']=len(cross);print('PASS 40 cross-view concurrent correlated queries',flush=True)
                shared=viz[0].add_box()
                page.wait_for_function('(h)=>window.__FRAMEVIZ_CORE__.objects.has(h)',arg=shared)
                second.wait_for_function('(h)=>window.__FRAMEVIZ_CORE__.objects.has(h)',arg=shared)
                page.evaluate('(h)=>window.__FRAMEVIZ_CORE__.options.onCommand("set_transform",{handle:h,pose:{pos:[6,0,0],quat:[0,0,0,1]}})',shared)
                second.wait_for_function('(h)=>window.__FRAMEVIZ_CORE__.objects.get(h).position.x===6',arg=shared)
                page.evaluate('window.__FRAMEVIZ_CORE__.options.onCommand("set_camera_pose",{eye:[2,3,4],target:[0,0,0],up:[0,0,1]})')
                page.wait_for_timeout(100)
                assert np.allclose(viz[0].get_camera_pose()['eye'],[2,3,4])
                assert np.allclose(sibling_viz.get_camera_pose()['eye'],[7,8,9])
                results['multi_view_sync']='shared object transforms synchronize; camera updates stay in the originating view'
                print('PASS two views share model transforms and keep independent camera state',flush=True)
                viz[0].remove(shared)
                browser.close()
        finally:
            for c in clients:c.close()
            server.shutdown();server.server_close();process.terminate();process.wait(timeout=10);log.close()
            (OUT/'stress-results.json').write_text(json.dumps(results,indent=2))
if __name__=='__main__':run()
