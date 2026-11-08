"""Real Rust Host + browser WebGL + Python SDK + built Vue component acceptance."""
import functools, hashlib, http.server, json, os, pathlib, shutil, socket, subprocess, tempfile, threading, time
import numpy as np
from playwright.sync_api import sync_playwright
from frameviz.client import FrameVizClient
from frameviz.viz import Viz
from host_smoke import free_port
ROOT=pathlib.Path(__file__).resolve().parents[2]
EVIDENCE=pathlib.Path(os.environ.get('FRAMEVIZ_EVIDENCE', ROOT/'.validation/evidence'))
STL='''solid triangle
facet normal 0 0 1
 outer loop
 vertex -1 -1 0
 vertex 1 -1 0
 vertex 0 1 0
 endloop
endfacet
endsolid triangle
'''
class QuietHandler(http.server.SimpleHTTPRequestHandler):
    def log_message(self,*args): pass

def serve(directory):
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),functools.partial(QuietHandler,directory=str(directory)))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    return server

def main():
    EVIDENCE.mkdir(parents=True,exist_ok=True); results=[]
    def passed(name): results.append({'name':name,'status':'passed'});print('PASS',name,flush=True)
    with tempfile.TemporaryDirectory(prefix='frameviz-browser-') as tmp:
        tmp=pathlib.Path(tmp); port=free_port();url=f'ws://127.0.0.1:{port}'
        env=dict(os.environ,HOME=str(tmp),CFFIXED_USER_HOME=str(tmp),FRAMEVIZ_DISCOVERY_PATH=str(tmp/'host.json'),FRAMEVIZ_LOG_DIR=str(tmp/'logs'))
        log=open(EVIDENCE/'browser-host.log','w')
        native_app=os.environ.get('FRAMEVIZ_ACCEPTANCE_APP_EXECUTABLE')
        if native_app:
            env['PATH']='/usr/bin:/bin:/usr/sbin:/sbin'
            env['FRAMEVIZ_TAURI_CONTROL_PORT']=str(free_port())
            command=[str(pathlib.Path(native_app).resolve()),'--ws-port',str(port),'--headless']
        else:
            command=[str(ROOT/'packages/frameviz-server/target/debug/frameviz-server'),str(port)]
        host=subprocess.Popen(command,env=env,cwd=tmp,stdout=log,stderr=log)
        servers=[]; client=None
        try:
            for _ in range(100):
                if (tmp/'host.json').exists(): break
                time.sleep(.05)
            token=json.loads((tmp/'host.json').read_text())['token']
            client=FrameVizClient(url,token=token);client.connect()
            if native_app:
                from types import SimpleNamespace
                for _ in range(100):
                    discovery=json.loads((tmp/'host.json').read_text())
                    if discovery.get('http_port'):break
                    if host.poll() is not None:raise RuntimeError('Packaged Host exited')
                    time.sleep(.05)
                assert discovery.get('http_port'), 'Packaged embedded HTTP server did not become ready'
                standalone=SimpleNamespace(server_port=discovery['http_port'],shutdown=lambda:None,server_close=lambda:None)
            else:
                standalone=serve(ROOT/'packages/frameviz-web-viewer/dist')
            servers.append(standalone)
            vue_dist=pathlib.Path(os.environ.get('FRAMEVIZ_VUE_DIST', str(ROOT/'.validation/vue-web')))
            vue=serve(vue_dist);servers.append(vue)
            vue_entry='index.html' if (vue_dist/'index.html').exists() else 'acceptance.html'
            with sync_playwright() as pw:
                browser=pw.chromium.launch(executable_path='/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',headless=True,args=['--use-angle=swiftshader','--enable-webgl'])
                context=browser.new_context(viewport={'width':1000,'height':720})
                external=[]; errors=[]
                def network(route):
                    from urllib.parse import urlsplit
                    if urlsplit(route.request.url).hostname not in {'127.0.0.1','localhost'}:
                        external.append(route.request.url);route.abort();return
                    if urlsplit(route.request.url).path.endswith(('acceptance.stl','cancelled.stl')):
                        route.fulfill(status=200,body=STL,content_type='model/stl');return
                    route.continue_()
                context.route('**/*',network)
                page=context.new_page();page.on('pageerror',lambda e:errors.append(str(e)))
                created=client.send_command('create_view',{})
                view,scene=created['view_id'],created['scene_id']
                viz=Viz(client,scene,view,owns_view=False)
                box=viz.add_box(size=(1,1,1),color=(.8,.2,.1))
                points=viz.add_points(np.array([[1,0,0],[0,1,0]],np.float32),color=(.2,.4,.6),size=12)
                target=f'http://127.0.0.1:{standalone.server_port}/?view_id={view}&ws_port={port}#token={token}'
                page.goto(target)
                page.wait_for_function('window.__FRAMEVIZ_CORE__?.getObjectCount()===2')
                passed('Python SDK -> real Host -> offline bundled WebGL snapshot')
                def objects(): return page.evaluate('Object.fromEntries([...window.__FRAMEVIZ_CORE__.objects].map(([k,o])=>[k,{pos:o.position.toArray(),visible:o.visible,type:o.type,color:o.material?.color?.toArray()}]))')
                state=objects();assert np.allclose(state[points]['color'],[.2,.4,.6]);passed('Uniform point color restored from snapshot')
                consumer=EVIDENCE/'consumer-build/consumer'
                installed_python=EVIDENCE/'installed-python/bin/python'
                childenv=dict(env,FRAMEVIZ_AUTH_TOKEN=token)
                if not consumer.exists() or not installed_python.exists(): raise RuntimeError('Build installed SDK consumers before this acceptance run')
                cpp=subprocess.run([str(consumer),url,view],cwd=tmp,env=childenv,text=True,capture_output=True,check=True,timeout=30)
                cpp_result=json.loads(cpp.stdout.strip().splitlines()[-1]);cpp_handle=cpp_result['handle']
                page.wait_for_function('(h)=>window.__FRAMEVIZ_CORE__.objects.has(h)',arg=cpp_handle)
                assert np.allclose(objects()[cpp_handle]['pos'],[1,2,3])
                for cloud in cpp_result['clouds']:
                    page.wait_for_function('(h)=>window.__FRAMEVIZ_CORE__.objects.has(h)',arg=cloud['handle'])
                    expected=(np.arange(cloud['count']*3,dtype=np.float32)%997)/997
                    actual=page.evaluate("""async(h)=>{const a=window.__FRAMEVIZ_CORE__.objects.get(h).geometry.attributes.position.array;return [...new Uint8Array(await crypto.subtle.digest('SHA-256',new Uint8Array(a.buffer,a.byteOffset,a.byteLength)))].map(x=>x.toString(16).padStart(2,'0')).join('')}""",cloud['handle'])
                    assert actual==hashlib.sha256(expected.tobytes()).hexdigest()
                    viz.remove(cloud['handle'])
                assert cpp_result['concurrent_queries']==20
                viz.remove(cpp_handle)
                passed('C++ two connections / four threads: four buffer hashes and 20 concurrent queries')
                passed('Repository-external C++ installed SDK consumer renders geometry and queries real viewer')
                py_code="""import sys,json,numpy as np,frameviz;from frameviz.client import FrameVizClient;from frameviz.viz import Viz
c=FrameVizClient(sys.argv[1]);c.connect();v=Viz(c,sys.argv[2],sys.argv[3],owns_view=False);h=v.add_points(np.array([[0,0,0],[1,2,3]],np.float32));print(json.dumps({'handle':h,'module':frameviz.__file__}));c.close()"""
                py=subprocess.run([str(installed_python),'-I','-c',py_code,url,scene,view],cwd=tmp,env=childenv,text=True,capture_output=True,check=True,timeout=30)
                py_result=json.loads(py.stdout.strip().splitlines()[-1]);assert 'installed-python' in py_result['module']
                page.wait_for_function('(h)=>window.__FRAMEVIZ_CORE__.objects.has(h)',arg=py_result['handle'])
                viz.remove(py_result['handle'])
                passed('Repository-external wheel installation uploads data into real viewer')
                model=viz.load_mesh('/acceptance.stl',color=(.1,.8,.2))
                viz.set_transform(model,pos=(2,0,0))
                page.wait_for_function('(h)=>window.__FRAMEVIZ_CORE__.objects.has(h)',arg=model)
                page.wait_for_function('(h)=>window.__FRAMEVIZ_CORE__.objects.get(h).position.x===2',arg=model)
                passed('Actual STL loader and transform during asynchronous load')
                failed=viz.load_mesh('/missing.stl')
                page.wait_for_function('(h)=>!window.__FRAMEVIZ_CORE__.pendingLoads.has(h)',arg=failed)
                error=client.wait_for_event('object_failed',timeout=3,filter_fn=lambda data:data.get('handle')==failed)
                assert error and not page.evaluate('(h)=>window.__FRAMEVIZ_CORE__.objects.has(h)',failed)
                viz.remove(failed)
                cancelled=viz.load_mesh('/cancelled.stl');viz.remove(cancelled)
                page.wait_for_timeout(150)
                assert not page.evaluate('(h)=>window.__FRAMEVIZ_CORE__.objects.has(h)',cancelled)
                passed('Model 404 reports failure; cancelled async load does not resurrect object')
                viz.set_camera_pose((0,-8,6),(0,0,0))
                pose=viz.get_camera_pose();assert np.allclose(pose['eye'],[0,-8,6]);passed('Correlated live camera query')
                before=page.evaluate('window.__FRAMEVIZ_CORE__.getCameraPose()')
                page.mouse.move(500,350);page.mouse.down();page.mouse.move(570,385,steps=8);page.mouse.up()
                page.wait_for_timeout(150)
                after=viz.get_camera_pose();assert not np.allclose(before['eye'],after['eye']);passed('Real mouse orbit changes camera returned by SDK')
                # Use one known transformed point to give picking an independent world-space oracle.
                viz.set_visible(box,False);viz.set_visible(model,False)
                viz.set_transform(points,pos=(2,3,0),quat=(0,0,np.sqrt(.5),np.sqrt(.5)),scale=(2,2,2))
                viz.set_camera_pose((2,5,10),(2,5,0),up=(0,1,0))
                viz.set_pick_config(enabled=True,mode='point',button=0,ctrl_modifier=False,point_threshold=.2)
                page.wait_for_timeout(150);page.mouse.click(500,360)
                picked=viz.get_picked_info();assert picked['handle']==points,picked
                assert np.allclose(picked['point_world'],[2,5,0],atol=1e-5),picked
                passed('Actual mouse picking returns transformed world coordinates')
                viz.set_visible(box,True);viz.set_visible(points,False)
                viz.set_camera_pose((0,0,10),(0,0,0),up=(0,1,0));viz.attach_gizmo(box,mask=1)
                page.wait_for_timeout(200)
                picker=page.evaluate("""()=>{const c=window.__FRAMEVIZ_CORE__, controls=c.gizmoManager.controls;
                const rect=c.getSceneManager().renderer.domElement.getBoundingClientRect(), camera=c.getSceneManager().camera;
                const points=[];controls._gizmo.picker.traverse(o=>{if(o.name==='TR_X' && o.geometry){o.geometry.computeBoundingBox();const v=o.geometry.boundingBox.getCenter(o.position.clone()).applyMatrix4(o.matrixWorld).project(camera);points.push({x:rect.x+(v.x+1)*rect.width/2,y:rect.y+(1-v.y)*rect.height/2});}});return points.sort((a,b)=>b.x-a.x)[0];}""")
                page.mouse.move(picker['x'],picker['y']);page.mouse.down();page.mouse.move(picker['x']+60,picker['y'],steps=12);page.mouse.up();page.wait_for_timeout(200)
                moved=objects()[box]['pos'];assert moved[0]>.1 and abs(moved[1])<1e-5,moved
                snap=client.send_command('get_scene_snapshot',{'scene_id':scene})
                assert np.allclose(next(o for o in snap['objects'] if o['handle']==box)['pose']['pos'],moved)
                passed('Physical gizmo mouse drag updates model and authoritative Host pose')
                viz.set_visible(box,False)
                # Commit the same command emitted by the real gizmo; physical drag remains separately tested.
                page.evaluate('(h)=>window.__FRAMEVIZ_CORE__.options.onCommand("set_transform",{handle:h,pose:{pos:[4,0,0],quat:[0,0,0,1]}})',box)
                page.wait_for_timeout(150)
                snap=client.send_command('get_scene_snapshot',{'scene_id':scene})
                assert next(o for o in snap['objects'] if o['handle']==box)['pose']['pos']==[4,0,0]
                passed('Viewer gizmo command callback commits to Host')
                page.reload();page.wait_for_function('window.__FRAMEVIZ_CORE__?.getObjectCount()===3')
                assert objects()[box]['pos']==[4,0,0] and not objects()[box]['visible']
                restored_camera=viz.get_camera_pose()
                assert np.allclose(restored_camera['eye'],[0,0,10],atol=1e-4),restored_camera
                revision=client.send_command('get_scene_snapshot',{'scene_id':scene})['revision']
                assert page.evaluate('window.__FRAMEVIZ_CORE__.sceneRevision')==revision
                passed('Refresh restores model, pose, visibility, configured camera and matching revision')
                for visible_handle in (box,model,points):viz.set_visible(visible_handle,True)
                viz.set_camera_pose((9,-10,8),(2,2,0))
                page.wait_for_timeout(150)
                page.screenshot(path=str(EVIDENCE/'standalone.png'))
                # Vue mounting registers an actual viewer and uses the same snapshot interpreter.
                embedded=context.new_page();embedded.on('pageerror',lambda e:errors.append(str(e)))
                embedded.goto(f'http://127.0.0.1:{vue.server_port}/{vue_entry}?ws_port={port}#token={token}')
                embedded.wait_for_function('window.acceptance?.info?.viewId')
                info=embedded.evaluate('window.acceptance.info');vv=Viz(client,info['sceneId'],info['viewId'],owns_view=False)
                vh=vv.add_box(color=(.2,.8,.4));vp=vv.add_points(np.array([[0,0,0],[1,1,1]],np.float32),color=(.7,.2,.5),size=10)
                embedded.wait_for_function('window.acceptance.core.getObjectCount()===2')
                vv.set_camera_pose((0,-5,3),(0,0,0));assert np.allclose(vv.get_camera_pose()['eye'],[0,-5,3]);passed('Built Vue component renders SDK geometry and answers camera query')
                for _ in range(3):
                    embedded.click('#toggle');embedded.wait_for_function('document.querySelectorAll("canvas").length===0')
                    embedded.click('#toggle');embedded.wait_for_function('window.acceptance.core.getObjectCount()===2')
                passed('Vue unmount/remount three times restores geometry without duplicate canvases')
                embedded.evaluate('(h)=>window.acceptance.core.options.onCommand("set_transform",{handle:h,pose:{pos:[3,0,0],quat:[0,0,0,1]}})',vh)
                embedded.wait_for_timeout(150)
                snap=client.send_command('get_scene_snapshot',{'scene_id':info['sceneId']});assert next(o for o in snap['objects'] if o['handle']==vh)['pose']['pos']==[3,0,0]
                passed('Vue model manipulation persists in Host')
                vv.set_camera_pose((7,-8,6),(1.5,0,0))
                embedded.wait_for_timeout(150)
                embedded.screenshot(path=str(EVIDENCE/'vue.png'))
                assert not external,external;assert not errors,errors
                passed('No external runtime network dependencies or uncaught browser exceptions')
                browser.close()
        finally:
            if client: client.close()
            for server in servers: server.shutdown();server.server_close()
            host.terminate();host.wait(timeout=10);log.close()
            (EVIDENCE/'browser-results.json').write_text(json.dumps(results,indent=2))
if __name__=='__main__': main()
