import json,base64,time,struct,importlib.util,os,asyncio
from pathlib import Path
import pytest
from test_host_contracts import h

@pytest.mark.parametrize('index',[0,1,2])
@pytest.mark.parametrize('cmd,key,good,bad',[
 ('set_object_colors','rgba',[0,1,0],[2,0,0]),
 ('set_object_alphas','alpha',.2,'bad'),
 ('set_object_visibilities','visible',False,None),
 ('set_object_transforms','pose',{'pos':[1,2,3]},{'pos':[1,2]})])
def test_batch_all_positions_leave_host_and_two_viewers_unchanged(h,index,cmd,key,good,bad):
 v=h.view('s');objs=[h.box('s') for _ in range(3)];a=h.viewer(v);b=h.viewer(v)
 before=h.cmd('get_scene_snapshot',scene_id='s');counts=h.cmd('get_resource_counts')
 items=[{'handle':o,key:good} for o in objs];items[index][key]=bad
 with pytest.raises(RuntimeError):h.cmd(cmd,scene_id='s',items=items)
 assert h.cmd('get_scene_snapshot',scene_id='s')==before
 assert h.cmd('get_resource_counts')==counts
 for ws in [a,b]:
  with pytest.raises(TimeoutError):ws.recv(timeout=.05)

@pytest.mark.parametrize('args',[None,[],7,'x'])
def test_nonobject_envelope_rejected(h,args):
 v=h.view('s');ws=h.viewer(v);assert not h.request(ws,'set_transform',args)['ok']

def test_nested_scope_batch_atomic(h):
 a=h.box('s');b=h.box('s');before=h.cmd('get_scene_snapshot',scene_id='s')
 with pytest.raises(RuntimeError):h.cmd('set_object_colors',scene_id='s',items=[{'handle':a,'rgba':[1,0,0]},{'handle':b,'rgba':[1,0,0],'view_id':None}])
 assert h.cmd('get_scene_snapshot',scene_id='s')==before

def test_shared_color_and_thousand_replacements(h):
 def point():
  p=h.buf();c=h.buf();o=h.cmd('add_points',scene_id='s',positions=p,colors=c)['handle'];return o,c
 o,c=point();copy=h.cmd('clone_object',handle=o)['handle'];h.cmd('set_color',handle=o,rgba=[1,0,0]);snap=h.cmd('get_scene_snapshot',scene_id='s');assert c['buffer_id'] in snap['buffers']
 h.cmd('set_color',handle=copy,rgba=[0,1,0]);assert c['buffer_id'] not in h.cmd('get_scene_snapshot',scene_id='s')['buffers']
 h.cmd('clear_scene',scene_id='s');before=h.cmd('get_resource_counts')
 for _ in range(1000):
  o,_=point();h.cmd('set_color',handle=o,rgba=[1,0,0]);h.cmd('remove_object',scene_id='s',handle=o)
 assert h.cmd('get_resource_counts')==before

def test_python_failed_binary_send_cleans_pending(h):
 h.c._ws.close();time.sleep(.05)
 for _ in range(3):
  with pytest.raises(Exception):h.c.send_command_with_binary('upload_buffer_chunk',{},b'1')
 assert not h.c._pending and not h.c._responses

def test_uninstall_preserves_user_empty_dirs(tmp_path):
 root=Path(__file__).resolve().parents[2];spec=importlib.util.spec_from_file_location('installer',root/'scripts/release/portable_install.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 bundle=tmp_path/'bundle';bundle.mkdir();(bundle/'file').write_text('owned');(bundle/m.MANIFEST).write_text(json.dumps({'format':1,'files':{'file':m.digest(bundle/'file')}}))
 prefix=tmp_path/'prefix';m.install(bundle,prefix);(prefix/'user-empty/nested').mkdir(parents=True);m.uninstall(prefix);assert (prefix/'user-empty/nested').is_dir()

def test_business_socket_security_and_legitimate_state(monkeypatch):
 from frameviz.business_auth import authorize_business_socket,business_messages
 import websockets
 token='synthetic-token-'+('x'*40);monkeypatch.setenv('FRAMEVIZ_BUSINESS_TOKEN',token)
 received=[]
 async def handler(ws):
  if not await authorize_business_socket(ws):return
  await ws.send('authorized')
  async for msg in business_messages(ws):received.append(msg);await ws.send('ok')
 async def run():
  async with websockets.serve(handler,'127.0.0.1',0,max_size=65536,max_queue=16) as server:
   url=f'ws://127.0.0.1:{server.sockets[0].getsockname()[1]}'
   for origin,protocols in [('https://evil.invalid',['token.'+token]),('http://localhost:9999',None),('http://localhost:9999',['token.wrong'])]:
    async with websockets.connect(url,origin=origin,subprotocols=protocols) as ws:
     with pytest.raises(websockets.exceptions.ConnectionClosed):await ws.recv()
   assert received==[]
   async with websockets.connect(url,origin='http://localhost:9999',subprotocols=['token.'+token]) as ws:
    assert await ws.recv()=='authorized';await ws.send('business-command');assert await ws.recv()=='ok'
   assert received==['business-command']
 asyncio.run(run())
