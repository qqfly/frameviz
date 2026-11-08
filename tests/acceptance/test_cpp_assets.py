"""Approved model roots, hidden files, origins, and symlinks for the C++ asset server."""
import os,pathlib,socket,subprocess,time,urllib.request,urllib.error
import pytest
ROOT=pathlib.Path(__file__).resolve().parents[2]
@pytest.fixture
def assets(tmp_path):
 binary=os.environ.get('FRAMEVIZ_ASSET_TEST_BINARY')
 if not binary:pytest.skip('Set FRAMEVIZ_ASSET_TEST_BINARY to the built asset_harness')
 model=tmp_path/'model';model.mkdir();(model/'mesh.stl').write_text('synthetic public mesh');(model/'.private').mkdir();(model/'.private/hidden.stl').write_text('synthetic private mesh')
 (model/'private.json').write_text('synthetic private config');(tmp_path/'sibling.stl').write_text('synthetic outside mesh');(model/'escape.stl').symlink_to(tmp_path/'sibling.stl')
 with socket.socket() as s:s.bind(('127.0.0.1',0));port=s.getsockname()[1]
 with (tmp_path/'server.log').open('w') as log:
  proc=subprocess.Popen([binary,str(model),str(port)],stdout=log,stderr=log)
  try:
   for _ in range(100):
    try:
     with socket.create_connection(('127.0.0.1',port),timeout=.05):break
    except OSError:time.sleep(.02)
   else:
    pytest.fail(f'Asset server not ready within the existing readiness budget; exit={proc.poll()}; log='+(tmp_path/'server.log').read_text())
   yield f'http://127.0.0.1:{port}'
  finally:proc.terminate();proc.wait(timeout=10)

def test_allowed_model_and_local_cors(assets):
 req=urllib.request.Request(assets+'/mesh.stl',headers={'Origin':'http://localhost:5174'})
 with urllib.request.urlopen(req) as response:
  assert response.read()==b'synthetic public mesh';assert response.headers['Access-Control-Allow-Origin']=='http://localhost:5174'
@pytest.mark.parametrize('path',['/.private/hidden.stl','/%2eprivate/hidden.stl','/escape.stl','/../sibling.stl','/private.json','/'])
def test_asset_boundaries(assets,path):
 with pytest.raises(urllib.error.HTTPError) as error:urllib.request.urlopen(assets+path)
 assert error.value.code==404

def test_foreign_origin_is_rejected(assets):
 req=urllib.request.Request(assets+'/mesh.stl',headers={'Origin':'https://foreign.invalid'})
 with pytest.raises(urllib.error.HTTPError) as error:urllib.request.urlopen(req)
 assert error.value.code==403
