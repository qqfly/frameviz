"""Real Host boundary contracts and synthetic security regression scenarios."""
import base64,json,os,pathlib,socket,subprocess,time
import pytest
from websockets.sync.client import connect
from frameviz.client import FrameVizClient
ROOT=pathlib.Path(__file__).resolve().parents[2]
OUT=pathlib.Path(os.environ.get('FRAMEVIZ_EVIDENCE',ROOT/'.validation/evidence'))
(OUT/'logs').mkdir(parents=True,exist_ok=True)
class Session:
 def __init__(self,url,token):self.url=url;self.token=token;self.c=FrameVizClient(url,token=token);self.c.connect();self.sockets=[]
 def cmd(self,name,**args):return self.c.send_command(name,args)
 def view(self,scene):return self.cmd('create_view',scene_id=scene)['view_id']
 def box(self,scene):return self.cmd('add_primitive',scene_id=scene,type='box',color=[1,1,1])['handle']
 def viewer(self,view=None,auth=True):
  ws=connect(self.url+'?type=viewer'+('' if view is None else '&view_id='+view),origin='http://localhost:8888');self.sockets.append(ws)
  if auth:
   ws.send(json.dumps({'type':'auth','token':self.token}));assert json.loads(ws.recv(timeout=2))['ok']
   if view:
    assert json.loads(ws.recv(timeout=2))['type']=='init';assert json.loads(ws.recv(timeout=2))['type']=='scene_snapshot'
  return ws
 def request(self,ws,name,args,version='0.4.0'):
  ws.send(json.dumps({'type':'cmd','protocol_version':version,'id':'review','name':name,'args':args}))
  while True:
   msg=json.loads(ws.recv(timeout=3))
   if msg.get('type')=='resp' and msg.get('id')=='review':return msg
 def buf(self,values=b'\0'*12):
  b=self.cmd('create_buffer',size_bytes=len(values),dtype='f32',shape=[len(values)//4])['buffer_id']
  self.cmd('upload_buffer_chunk',buffer_id=b,offset_bytes=0,chunk_bytes=len(values),data_base64=base64.b64encode(values).decode())
  return {'buffer_id':b,'dtype':'f32','shape':[1,len(values)//4]}
@pytest.fixture
def h(tmp_path,request):
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 env=dict(os.environ,HOME=str(tmp_path),FRAMEVIZ_DISCOVERY_PATH=str(tmp_path/'host.json'),FRAMEVIZ_LOG_DIR=str(tmp_path/'logs'))
 with (OUT/'logs'/('host-'+request.node.name.replace('/','_')+'.log')).open('w') as log:
  proc=subprocess.Popen([str(ROOT/'packages/frameviz-server/target/debug/frameviz-server'),str(port)],env=env,stdout=log,stderr=log)
  ss=None
  try:
   for _ in range(100):
    if (tmp_path/'host.json').exists():break
    time.sleep(.02)
   token=json.loads((tmp_path/'host.json').read_text())['token'];ss=Session(f'ws://127.0.0.1:{port}',token);yield ss
  finally:
   if ss:
    for ws in ss.sockets:ws.close()
    ss.c.close()
   proc.terminate();proc.wait(timeout=10)
def test_pre_auth_existing_view_attach_has_no_snapshot(h):
 v=h.view('private');obj=h.box('private');ws=h.viewer(v,auth=False)
 h.cmd('attach_scene',view_id=v,scene_id='private')
 with pytest.raises(TimeoutError):ws.recv(timeout=.3)
def test_pre_auth_unbound_view_create_has_no_snapshot(h):
 obj=h.box('private');ws=h.viewer(auth=False);h.view('private')
 with pytest.raises(TimeoutError):ws.recv(timeout=.3)
@pytest.mark.parametrize('scope',[None,[],7])
def test_viewer_cannot_bypass_scene_scope_with_nonstring(h,scope):
 v=h.view('a');obj=h.box('b');ws=h.viewer(v)
 result=h.request(ws,'set_transform',{'scene_id':scope,'handle':obj,'pose':{'pos':[9,0,0]}})
 after=h.cmd('get_transform',handle=obj)['pose']['pos']
 assert not result['ok'] and after==[0,0,0],{'reply':result,'actual_pos':after}
@pytest.mark.parametrize('command,valid,invalid,field',[('set_object_colors',{'rgba':[1,0,0]},{'rgba':[2,0,0]},'color'),('set_object_alphas',{'alpha':.3},{'alpha':2},'color'),('set_object_visibilities',{'visible':False},{'visible':'bad'},'visible')])
def test_rejected_batch_is_atomic(h,command,valid,invalid,field):
 a=h.box('a');b=h.box('a');before=h.cmd('get_scene_snapshot',scene_id='a')
 with pytest.raises(RuntimeError):h.cmd(command,scene_id='a',items=[dict(handle=a,**valid),dict(handle=b,**invalid)])
 after=h.cmd('get_scene_snapshot',scene_id='a')
 assert after==before,{'before':before,'after':after}
def test_invalid_scene_command_does_not_create_scene(h):
 before=h.cmd('list_scenes')
 with pytest.raises(RuntimeError):h.cmd('add_primitive',scene_id='must-not-exist')
 assert h.cmd('list_scenes')==before

def test_uniform_color_reclaims_replaced_color_buffer(h):
 p=h.buf();c=h.buf();obj=h.cmd('add_points',scene_id='a',positions=p,colors=c)['handle']
 h.cmd('free_buffer',buffer_id=p['buffer_id']);h.cmd('free_buffer',buffer_id=c['buffer_id'])
 h.cmd('set_color',handle=obj,rgba=[1,0,0]);h.cmd('remove_object',scene_id='a',handle=obj)
 counts=h.cmd('get_resource_counts');assert counts['buffers']==0,counts

def test_wrong_protocol_version_rejected(h):
 with connect(h.url) as ws:
  ws.send(json.dumps({'type':'auth','token':h.token}));assert json.loads(ws.recv(timeout=2))['ok']
  reply=h.request(ws,'create_scene',{},version='99.0.0');assert not reply['ok'],reply

def test_viewer_snapshot_has_current_revision(h):
 v=h.view('a');h.box('a');ws=h.viewer(v)
 expected=h.cmd('get_scene_snapshot',scene_id='a')['revision'];result=h.request(ws,'get_scene_snapshot',{})
 assert result['result'].get('revision')==expected,result

def test_reject_wrong_origin(h):
 with pytest.raises(Exception,match='403'):connect(h.url,origin='https://untrusted.invalid')
def test_viewer_cannot_destroy_scene(h):
 v=h.view('a');ws=h.viewer(v);r=h.request(ws,'destroy_scene',{'scene_id':'a'});assert not r['ok']
def test_cross_scene_delete_preserves_object(h):
 o=h.box('a')
 with pytest.raises(RuntimeError):h.cmd('remove_object',scene_id='b',handle=o)
 assert h.cmd('is_object_alive',handle=o)['alive']
def test_overlap_is_not_completion(h):
 b=h.cmd('create_buffer',size_bytes=12,dtype='f32',shape=[1,3])['buffer_id']
 for _ in range(2):h.cmd('upload_buffer_chunk',buffer_id=b,offset_bytes=0,chunk_bytes=6,data_base64=base64.b64encode(b'\0'*6).decode())
 with pytest.raises(RuntimeError):h.cmd('add_points',scene_id='a',positions={'buffer_id':b,'dtype':'f32','shape':[1,3]})
def test_referenced_buffer_rejects_mutation(h):
 b=h.buf();h.cmd('add_points',scene_id='a',positions=b)
 with pytest.raises(RuntimeError):h.cmd('upload_buffer_chunk',buffer_id=b['buffer_id'],offset_bytes=0,chunk_bytes=12,data_base64=base64.b64encode(b'\1'*12).decode())

def test_malformed_viewer_event_releases_connection_slot(h):
 v=h.view('a');before=h.cmd('get_resource_counts')['connections'];ws=h.viewer(v)
 ws.send(json.dumps({'type':'event','name':'picked','data':'not-an-object'}))
 time.sleep(.15);ws.close();time.sleep(.15)
 assert h.cmd('get_resource_counts')['connections']==before

def test_snapshot_read_unknown_scene_has_no_side_effect(h):
 before=h.cmd('list_scenes');h.cmd('get_scene_snapshot',scene_id='unknown-read');assert h.cmd('list_scenes')==before

def test_python_failed_sends_leave_no_pending_requests(h):
 h.c._ws.close();time.sleep(.1)
 for _ in range(3):
  with pytest.raises(Exception):h.cmd('list_scenes')
 assert not h.c._pending,{'pending_count':len(h.c._pending)}

def test_python_explicit_reconnect_and_late_reply_discard(h):
 h.c.close();h.c.connect();assert h.cmd('list_scenes')=={'scenes':[]}
 h.c._handle_message(json.dumps({'type':'resp','id':'timed-out-id','ok':True,'result':{}}))
 assert not h.c._responses

def test_python_scene_binding_changes_only_after_real_host_accepts(h):
 from frameviz.viz import Viz
 original=h.cmd('create_scene')['scene_id'];target=h.cmd('create_scene')['scene_id']
 view=h.view(original);viz=Viz(h.c,original,view,owns_view=False)
 before=h.cmd('list_views')
 # Deliberately bypass the type hint to exercise a real Host rejection.
 with pytest.raises(RuntimeError,match="ERR_INVALID_ARGS"):viz.attach_scene(None)
 assert viz.scene_id==original
 assert h.cmd('list_views')==before
 viz.attach_scene(target)
 assert viz.scene_id==target
 assert next(v for v in h.cmd('list_views')['views'] if v['view_id']==view)['scene_id']==target
