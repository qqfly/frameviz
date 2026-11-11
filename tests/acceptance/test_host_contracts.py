"""Real Host boundary contracts and synthetic security regression scenarios."""
import base64,json,os,pathlib,time
import pytest
from websockets.sync.client import connect
from frameviz.client import FrameVizClient
from test_standalone_viewer import standalone_runtime
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
 def request(self,ws,name,args,version='0.5.0'):
  ws.send(json.dumps({'type':'cmd','protocol_version':version,'id':'review','name':name,'args':args}))
  while True:
   msg=json.loads(ws.recv(timeout=3))
   if msg.get('type')=='resp' and msg.get('id')=='review':return msg
 def buf(self,values=b'\0'*12):
  b=self.cmd('create_buffer',size_bytes=len(values),dtype='f32',shape=[len(values)//4])['buffer_id']
  self.cmd('upload_buffer_chunk',buffer_id=b,offset_bytes=0,chunk_bytes=len(values),data_base64=base64.b64encode(values).decode())
  return {'buffer_id':b,'dtype':'f32','shape':[1,len(values)//4]}
@pytest.fixture
def h(tmp_path, request):
 with standalone_runtime(tmp_path) as (info, _, log, _):
  session = Session(info['ws_url'], info['token'])
  try:yield session
  finally:
   for ws in session.sockets:ws.close()
   session.c.close()
   (OUT/'logs'/('host-'+request.node.name.replace('/','_')+'.log')).write_bytes(log.read_bytes())
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
 import sys,traceback,websocket
 receiver=h.c._ws_thread;transport=h.c._ws
 h.c.close()
 frame=sys._current_frames().get(receiver.ident)
 diagnostic={'websocket_client':websocket.__version__,
             'receiver_stack':''.join(traceback.format_stack(frame)) if frame else None,
             'keep_running':transport.keep_running,'socket_present':transport.sock is not None}
 assert not receiver.is_alive(),diagnostic
 h.c.connect();assert h.cmd('list_scenes')=={'scenes':[]}
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


def test_named_viewer_uses_host_ids_and_cannot_rebind_existing_view(h):
    original = h.view('existing')
    h.box('existing')
    ws = h.viewer()
    reply = h.request(ws, 'register_viewer', {'viewer_name': 'embedded', 'scene_id': 'embedded-scene'})
    assert reply['ok'], reply
    embedded = reply['result']['view_id']
    assert embedded != h.view('new')
    assert {v['view_id']: v['scene_id'] for v in h.cmd('list_views')['views']}[original] == 'existing'
    conflicting = h.viewer(original)
    before = h.cmd('list_views')
    reply = h.request(conflicting, 'register_viewer', {
        'viewer_name': 'different', 'scene_id': 'embedded-scene',
    })
    assert not reply['ok'], reply
    assert h.cmd('list_views') == before


def test_named_viewer_refresh_uses_current_binding(h):
    ws = h.viewer()
    args = {'viewer_name': 'embedded', 'scene_id': 'initial'}
    first = h.request(ws, 'register_viewer', args)
    assert first['ok']
    view = first['result']['view_id']
    right = h.box('current')
    h.cmd('attach_scene', view_id=view, scene_id='current')
    ws.close()
    named = h.cmd('get_viewer_by_name', viewer_name='embedded')
    assert (named['view_id'], named['scene_id']) == (view, 'current')
    refreshed = h.viewer()
    result = h.request(refreshed, 'register_viewer', args)
    assert result['ok'], result
    assert (result['result']['view_id'], result['result']['scene_id']) == (view, 'current')
    assert json.loads(refreshed.recv(timeout=2))['type'] == 'init'
    snapshot = json.loads(refreshed.recv(timeout=2))
    assert {obj['handle'] for obj in snapshot['objects']} == {right}


def test_missing_handle_and_invalid_gizmo_bindings_are_rejected(h):
    view = h.view('local')
    valid = h.box('local')
    foreign = h.box('foreign')
    ws = h.viewer(view)
    assert h.request(ws, 'attach_gizmo', {'handle': valid})['ok']
    for handle, code in [('missing', 'ERR_NOT_FOUND'), (foreign, 'ERR_INVALID_SCOPE')]:
        with pytest.raises(RuntimeError, match=code):
            h.cmd('attach_gizmo', view_id=view, handle=handle)
    for command, values in [
        ('set_color', {'rgba': [1, 0, 0]}),
        ('set_alpha', {'alpha': .5}),
        ('set_visible', {'visible': False}),
    ]:
        with pytest.raises(RuntimeError, match='ERR_NOT_FOUND'):
            h.cmd(command, handle='missing', **values)
    original = h.cmd('get_scene_snapshot', scene_id='local')
    with pytest.raises(RuntimeError, match='ERR_NOT_FOUND'):
        h.cmd('set_object_alphas', scene_id='local', items=[
            {'handle': valid, 'alpha': .2}, {'handle': 'missing', 'alpha': .4},
        ])
    assert h.cmd('get_scene_snapshot', scene_id='local') == original


def test_delayed_camera_event_cannot_override_new_camera_command(h):
    view = h.view('camera')
    ws = h.viewer(view)
    before = h.cmd('get_scene_snapshot', scene_id='camera')['revision']
    desired = {'eye': [3, -4, 5], 'target': [0, 0, 0], 'up': [0, 0, 1],
               'projection': {'type': 'perspective', 'fov': 60}}
    h.cmd('set_camera_view', view_id=view, camera_view=desired)
    ws.send(json.dumps({'type': 'event', 'protocol_version': '0.5.0', 'name': 'camera_view_changed',
                        'data': {**desired, 'eye': [9, 8, 7], 'revision': before}}))
    assert h.request(ws, 'get_camera_view', {})['result'] == desired


def test_automatic_scene_ids_and_rejected_view_creation_preserve_existing_scenes(h):
    first = h.cmd('create_view', view_id='v_1', scene_id='s_1')
    with pytest.raises(RuntimeError, match='ERR_ALREADY_EXISTS'):
        h.cmd('create_view', view_id=first['view_id'], scene_id='must-not-exist')
    assert [item['scene_id'] for item in h.cmd('list_scenes')['scenes']] == ['s_1']
    named = h.request(h.viewer(), 'register_viewer', {'viewer_name': 'new'})
    assert named['ok'] and named['result']['view_id'] != first['view_id']
    assert named['result']['scene_id'] != first['scene_id']


def test_named_viewer_can_reuse_an_unbound_view_after_scene_destroy(h):
    view = h.view('old')
    socket = h.viewer(view)
    assert h.request(socket, 'register_viewer', {'viewer_name': 'embedded'})['ok']
    h.cmd('destroy_scene', scene_id='old')
    response = h.request(socket, 'register_viewer', {'viewer_name': 'embedded', 'scene_id': 'new'})
    assert response['ok']
    assert response['result']['view_id'] == view and response['result']['scene_id'] == 'new'


def test_failed_embedded_registration_does_not_leave_an_empty_scene(h):
    invalid = h.viewer('')
    before = h.cmd('list_scenes')
    reply = h.request(invalid, 'register_viewer', {'viewer_name': 'invalid', 'scene_id': 'would-leak'})
    assert reply['error']['code'] == 'ERR_INVALID_ARGS'
    assert h.cmd('list_scenes') == before
