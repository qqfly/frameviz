"""Slow consumer must be disconnected; producer must remain usable."""
import json, os, pathlib, socket, subprocess, tempfile, time
from frameviz.client import FrameVizClient
from websockets.sync.client import connect
from host_smoke import free_port
ROOT=pathlib.Path(__file__).resolve().parents[2]
def main():
 with tempfile.TemporaryDirectory(prefix='frameviz-slow-') as temp:
  tmp=pathlib.Path(temp);port=free_port();url=f'ws://127.0.0.1:{port}'
  env=dict(os.environ,FRAMEVIZ_DISCOVERY_PATH=str(tmp/'host.json'),FRAMEVIZ_LOG_DIR=str(tmp/'logs'))
  with open(tmp/'server.log','w') as log:
   host=subprocess.Popen([str(ROOT/'packages/frameviz-server/target/debug/frameviz-server'),str(port)],env=env,stdout=log,stderr=log)
   client=None;slow=None
   try:
    for _ in range(100):
     if (tmp/'host.json').exists():break
     time.sleep(.05)
    token=json.loads((tmp/'host.json').read_text())['token'];client=FrameVizClient(url,token=token,timeout=20);client.connect()
    state=client.send_command('create_view',{});view,scene=state['view_id'],state['scene_id']
    slow=connect(url+f'?type=viewer&view_id={view}',max_queue=1,close_timeout=1)
    slow.socket.setsockopt(socket.SOL_SOCKET,socket.SO_RCVBUF,4096)
    slow.send(json.dumps({'type':'auth','token':token}))
    for _ in range(3):slow.recv(timeout=3)
    size=18*1024*1024;raw=bytes(size)
    bid=client.send_command('create_buffer',{'size_bytes':size,'dtype':'f32','shape':[size//12,3]})['buffer_id']
    for offset in range(0,size,16*1024*1024):
     chunk=raw[offset:offset+16*1024*1024];client.send_command_with_binary('upload_buffer_chunk',{'buffer_id':bid,'offset_bytes':offset,'chunk_bytes':len(chunk)},chunk)
    start=time.monotonic()
    for _ in range(5):client.send_command('add_points',{'scene_id':scene,'positions':{'buffer_id':bid,'dtype':'f32','shape':[size//12,3]}})
    for _ in range(50):
     counts=client.send_command('get_resource_counts',{})
     if counts['connections']==1:break
     time.sleep(.1)
    assert counts['connections']==1,counts
    assert time.monotonic()-start<15
    assert client.send_command('list_views',{})['views']
    print('PASS slow consumer disconnected within 15 seconds; producer still usable')
   finally:
    if slow:slow.close()
    if client:client.close()
    host.terminate();host.wait(timeout=10)
if __name__=='__main__':main()
