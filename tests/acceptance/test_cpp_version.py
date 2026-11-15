"""Installed C++ client's real socket authentication with versioned peers."""
import json
import os
import queue
import subprocess
import threading
import pytest
from websockets.sync.server import serve


@pytest.mark.parametrize('version,expected',[('0.5.1',None),('0.5.99',None),('0.4.8','runtime'),('0.6.0','SDK'),('0.5.01','malformed')])
def test_cpp_auth_patch_compatibility(version,expected,tmp_path):
    binary=os.environ.get('FRAMEVIZ_CPP_VERSION_CONNECT')
    if not binary:pytest.skip('Installed SDK version_connect executable required')
    def handler(ws):
        assert json.loads(ws.recv())['type']=='auth'
        ws.send(json.dumps({'type':'auth_resp','ok':True,'protocol_version':version}))
        try:ws.recv(timeout=3)
        except Exception:pass
    with serve(handler,'127.0.0.1',0) as server:
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            port=server.socket.getsockname()[1]
            env=dict(os.environ,FRAMEVIZ_AUTH_TOKEN='synthetic-acceptance-token',FRAMEVIZ_DISCOVERY_PATH=str(tmp_path/'unused.json'))
            result=subprocess.run([binary,f'ws://127.0.0.1:{port}'],env=env,capture_output=True,text=True,timeout=5)
            if expected is None:assert result.returncode==0,result.stderr
            else:assert result.returncode!=0 and expected in result.stderr,result.stderr
        finally:server.shutdown();thread.join(timeout=5)


def test_two_cpp_processes_connect_to_existing_host(tmp_path):
    binary = os.environ.get("FRAMEVIZ_CPP_VERSION_CONNECT")
    if not binary:
        pytest.skip("Installed SDK version_connect executable required")

    authenticated = queue.Queue()

    def handler(ws):
        assert json.loads(ws.recv(timeout=5)) == {"type": "auth", "token": "synthetic-token"}
        ws.send(json.dumps({"type": "auth_resp", "ok": True, "protocol_version": "0.5.0"}))
        authenticated.put(True)
        ws.wait_closed(timeout=10)

    with serve(handler, "127.0.0.1", 0) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        env = dict(os.environ, FRAMEVIZ_AUTH_TOKEN="synthetic-token",
                   FRAMEVIZ_DISCOVERY_PATH=str(tmp_path / "unused.json"))
        url = f"ws://127.0.0.1:{server.socket.getsockname()[1]}"
        try:
            with subprocess.Popen([binary, url, "--hold"], env=env, cwd=tmp_path,
                                  stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                  stderr=subprocess.PIPE, text=True) as first:
                try:
                    authenticated.get(timeout=4)
                    second = subprocess.run([binary, url], env=env, cwd=tmp_path,
                                            capture_output=True, text=True, timeout=5)
                    assert second.returncode == 0, second.stderr
                    assert authenticated.get(timeout=1)
                    assert first.poll() is None
                    out, err = first.communicate(input="\n", timeout=5)
                    assert first.returncode == 0, err
                    assert out.strip() == "connected"
                finally:
                    if first.poll() is None:
                        first.kill()
        finally:
            server.shutdown()
            thread.join(timeout=5)
