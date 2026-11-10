"""The shipped standalone binary serves its own Viewer, without a desktop."""
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import time
from urllib.error import HTTPError
from urllib.parse import parse_qs, urlsplit
from urllib.request import urlopen

import pytest
from frameviz.client import FrameVizClient
from frameviz.viz import Viz

ROOT = Path(__file__).resolve().parents[2]
BINARY = ROOT / 'packages/frameviz-server/target/debug/frameviz-server'


def free_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


@pytest.fixture
def standalone(tmp_path):
    port = free_port()
    env = {k: v for k, v in os.environ.items() if not k.startswith('FRAMEVIZ_')}
    env.pop('DISPLAY', None)
    env.pop('WAYLAND_DISPLAY', None)
    discovery = tmp_path / 'state/host.json'
    env.update(HOME=str(tmp_path), FRAMEVIZ_HOME=str(tmp_path / 'state'),
               FRAMEVIZ_LOG_DIR=str(tmp_path / 'logs'))
    log_path = tmp_path / 'standalone.log'
    with log_path.open('w') as log:
        process = subprocess.Popen([str(BINARY), str(port)], cwd=tmp_path,
                                   env=env, stdout=log, stderr=log)
        try:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                assert process.poll() is None, log_path.read_text()
                if discovery.exists():
                    try:
                        info = json.loads(discovery.read_text())
                        if info.get('http_port'):
                            break
                    except json.JSONDecodeError:
                        pass
                time.sleep(.025)
            else:
                pytest.fail('Standalone discovery has no HTTP Viewer endpoint')
            yield info, process, log_path, discovery
        finally:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


def test_embedded_viewer_and_authenticated_url_without_source_or_display(standalone):
    info, _, log, discovery = standalone
    assert info['host'] == '127.0.0.1'
    assert info['http_port'] != info['port']
    assert info['version'] == '0.4.0'
    assert not (discovery.stat().st_mode & 0o077)
    with urlopen(info['viewer_url'], timeout=3) as response:
        html = response.read().decode()
        assert 'FrameViz' in html and '<script' in html
    urls = [line.split('Viewer URL: ', 1)[1].strip() for line in log.read_text().splitlines() if 'Viewer URL: ' in line]
    assert len(urls) == 1
    link = urlsplit(urls[0])
    assert parse_qs(link.fragment)['token'] == [info['token']]
    assert parse_qs(link.query)['ws_port'] == [str(info['port'])]
    assert 'token' not in parse_qs(link.query)
    assert urlsplit(info['viewer_url']).fragment == ''


def test_http_cannot_serve_discovery_or_local_paths(standalone):
    info, *_ = standalone
    for path in ['host.json', '.local/share/qqfly/frameviz/host.json', '../state/host.json', '%2e%2e/state/host.json']:
        with pytest.raises(HTTPError) as error:
            urlopen(info['viewer_url'] + path, timeout=3)
        assert error.value.code == 404


def test_real_browser_mouse_picking_dragging_and_authentication(standalone):
    from playwright.sync_api import sync_playwright
    info, *_ = standalone
    client = FrameVizClient(info['ws_url'], token=info['token'])
    client.connect()
    try:
        created = client.send_command('create_view', {})
        viz = Viz(client, created['scene_id'], created['view_id'], owns_view=False)
        handle = viz.add_box()
        url = info['viewer_url'] + f"?view_id={viz.view_id}&ws_port={info['port']}"
        with sync_playwright() as pw:
            options = {'headless': True, 'args': ['--use-gl=angle', '--use-angle=swiftshader', '--enable-unsafe-swiftshader']}
            if os.environ.get('FRAMEVIZ_TEST_CHROME'):
                options['executable_path'] = os.environ['FRAMEVIZ_TEST_CHROME']
            browser = pw.chromium.launch(**options)
            try:
                page = browser.new_page(viewport={'width':1000,'height':720})
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(url + '#token=incorrect')
                page.wait_for_function('window.__FRAMEVIZ_CORE__')
                # A rejected viewer must receive no scene data.
                page.wait_for_timeout(200)
                assert page.evaluate('window.__FRAMEVIZ_CORE__.getObjectCount()') == 0
                page.close()
                page = browser.new_page(viewport={'width':1000,'height':720})
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(url + '#token=' + info['token'])
                page.wait_for_function('(h)=>window.__FRAMEVIZ_CORE__?.objects.has(h)', arg=handle)
                # Keep this startup/interaction test away from OrbitControls'
                # polar singularity; retain the same numerical tolerance.
                viz.set_camera_pose((0,-8,6),(0,0,0),up=(0,0,1))
                viz.set_pick_config(enabled=True, mode='object', button=0, ctrl_modifier=False)
                camera = viz.get_camera_pose()
                assert all(abs(actual-expected)<1e-5 for actual,expected in zip(camera['eye'],[0,-8,6])), camera
                assert viz.get_pick_config()['enabled']
                # A command response does not imply the browser has rendered a
                # frame. Wait on actual animation frames, not a longer sleep.
                page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                center = page.evaluate('''(h)=>{const c=window.__FRAMEVIZ_CORE__,m=c.getSceneManager(),
                  r=m.renderer.domElement.getBoundingClientRect(),o=c.objects.get(h),
                  p=o.getWorldPosition(o.position.clone()).project(m.camera);
                  return {x:r.x+(p.x+1)*r.width/2,y:r.y+(1-p.y)*r.height/2};}''',handle)
                page.mouse.click(center['x'],center['y'])
                picked = client.wait_for_event('picked', timeout=3, filter_fn=lambda data:data.get('handle')==handle)
                assert picked and picked['handle'] == handle
                viz.attach_gizmo(handle, mask=1)
                page.wait_for_function('window.__FRAMEVIZ_CORE__.gizmoManager.controls')
                page.evaluate('()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))')
                picker = page.evaluate('''()=>{const c=window.__FRAMEVIZ_CORE__,controls=c.gizmoManager.controls;
                  const rect=c.getSceneManager().renderer.domElement.getBoundingClientRect(),camera=c.getSceneManager().camera;
                  const points=[];controls._gizmo.picker.traverse(o=>{if(o.name==='TR_X'&&o.geometry){o.geometry.computeBoundingBox();
                  const v=o.geometry.boundingBox.getCenter(o.position.clone()).applyMatrix4(o.matrixWorld).project(camera);
                  points.push({x:rect.x+(v.x+1)*rect.width/2,y:rect.y+(1-v.y)*rect.height/2});}});
                  return points.sort((a,b)=>b.x-a.x)[0];}''')
                assert picker
                page.mouse.move(picker['x'],picker['y'])
                page.mouse.down()
                page.mouse.move(picker['x']+60,picker['y'],steps=12)
                page.mouse.up()
                page.wait_for_function('(h)=>window.__FRAMEVIZ_CORE__.objects.get(h).position.x>.1', arg=handle)
                pose = viz.get_transform(handle)
                assert pose['pos'][0] > .1 and abs(pose['pos'][1]) < 1e-5
                assert not errors
            finally:
                browser.close()
    finally:
        client.close()


@pytest.mark.parametrize('arguments', [['--http-port'], ['--http-port','invalid'], ['--ws-port','0'], ['--unknown']])
def test_invalid_cli_fails_without_creating_discovery(tmp_path, arguments):
    state = tmp_path / 'state'
    env = dict(os.environ, HOME=str(tmp_path), FRAMEVIZ_HOME=str(state),
               FRAMEVIZ_DISCOVERY_PATH=str(state/'host.json'), FRAMEVIZ_LOG_DIR=str(tmp_path/'logs'))
    result = subprocess.run([str(BINARY), *arguments], env=env, cwd=tmp_path,
                            capture_output=True, text=True, timeout=5)
    assert result.returncode != 0 and result.stderr
    assert not (state/'host.json').exists()


def test_explicit_http_port_conflict_fails_without_discovery(tmp_path):
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1',0))
        occupied.listen()
        state = tmp_path / 'state'
        env = dict(os.environ, HOME=str(tmp_path), FRAMEVIZ_HOME=str(state),
                   FRAMEVIZ_DISCOVERY_PATH=str(state/'host.json'), FRAMEVIZ_LOG_DIR=str(tmp_path/'logs'))
        result = subprocess.run([str(BINARY),'--ws-port',str(free_port()),'--http-port',str(occupied.getsockname()[1])],
                                env=env,cwd=tmp_path,capture_output=True,text=True,timeout=5)
        assert result.returncode != 0
        assert not (state/'host.json').exists()


def test_websocket_port_conflict_does_not_advertise_a_viewer(tmp_path):
    with socket.socket() as occupied:
        occupied.bind(('127.0.0.1',0))
        occupied.listen()
        discovery = tmp_path / 'host.json'
        env = dict(os.environ, HOME=str(tmp_path), FRAMEVIZ_DISCOVERY_PATH=str(discovery),
                   FRAMEVIZ_LOG_DIR=str(tmp_path/'logs'))
        result = subprocess.run([str(BINARY),str(occupied.getsockname()[1])],
                                env=env,cwd=tmp_path,capture_output=True,text=True,timeout=5)
        assert result.returncode != 0
        assert 'Viewer URL:' not in result.stdout
        assert not discovery.exists()


def test_graceful_shutdown_removes_discovery(standalone):
    _, process, _, discovery = standalone
    process.send_signal(signal.SIGINT)
    assert process.wait(timeout=5) == 0
    assert not discovery.exists()
