"""Managed browser presentation may rebind only an authenticated marked page."""
import json

import pytest
from websockets.sync.client import connect
from test_host_contracts import h


def marked_viewer(h, view, session='sdk_test'):
    ws = connect(f'{h.url}?type=viewer&view_id={view}&browser_session={session}', origin='http://localhost:8888')
    h.sockets.append(ws)
    ws.send(json.dumps({'type': 'auth', 'token': h.token}))
    assert json.loads(ws.recv(timeout=2))['ok']
    assert json.loads(ws.recv(timeout=2))['type'] == 'init'
    assert json.loads(ws.recv(timeout=2))['type'] == 'scene_snapshot'
    return ws


def test_present_rebinds_page_and_preserves_both_views_and_scenes(h):
    first = h.view('a'); second = h.view('b')
    left = h.box('a'); right = h.box('b')
    ws = marked_viewer(h, first)
    before = h.cmd('list_views')
    result = h.cmd('present_view', browser_session='sdk_test', view_id=second)
    assert result['viewer_count'] == 1
    init = json.loads(ws.recv(timeout=2)); snapshot = json.loads(ws.recv(timeout=2))
    assert init['type'] == 'init' and init['view_id'] == second
    assert snapshot['scene_id'] == 'b'
    assert {o['handle'] for o in snapshot['objects']} == {right}
    assert h.cmd('list_views') == before
    assert h.cmd('is_object_alive', handle=left)['alive']
    denied = h.request(ws, 'get_scene_snapshot', {'scene_id': 'a'})
    assert not denied['ok'] and denied['error']['code'] == 'ERR_INVALID_SCOPE'


def test_unavailable_session_does_not_advance_scene_revision(h):
    view = h.view('a'); h.box('a')
    before = h.cmd('get_scene_snapshot', scene_id='a')
    assert h.cmd('present_view', browser_session='not_open', view_id=view) == {'viewer_count': 0}
    assert h.cmd('get_scene_snapshot', scene_id='a') == before


@pytest.mark.parametrize('label', ['', 'bad label', 'x'*129, '视图'])
def test_invalid_session_is_rejected_without_side_effect(h, label):
    view = h.view('a'); h.box('a')
    before = h.cmd('get_scene_snapshot', scene_id='a')
    with pytest.raises(RuntimeError, match='ERR_INVALID_ARGS'):
        h.cmd('present_view', browser_session=label, view_id=view)
    assert h.cmd('get_scene_snapshot', scene_id='a') == before


def test_unknown_view_preserves_existing_browser_binding(h):
    view = h.view('a'); ws = marked_viewer(h, view)
    before = h.cmd('get_scene_snapshot', scene_id='a')
    with pytest.raises(RuntimeError, match='ERR_NOT_FOUND'):
        h.cmd('present_view', browser_session='sdk_test', view_id='missing')
    assert h.cmd('get_scene_snapshot', scene_id='a') == before
    assert h.request(ws, 'get_scene_snapshot', {})['ok']


def test_viewer_and_unauthenticated_callers_cannot_present(h):
    view = h.view('a'); ws = marked_viewer(h, view)
    before = h.cmd('get_scene_snapshot', scene_id='a')
    denied = h.request(ws, 'present_view', {'browser_session': 'sdk_test', 'view_id': view})
    assert not denied['ok'] and denied['error']['code'] == 'ERR_FORBIDDEN'
    with connect(h.url) as unauthenticated:
        unauthenticated.send(json.dumps({'type':'cmd','protocol_version':'0.5.0','id':'unauth-present',
            'name':'present_view','args':{'browser_session':'sdk_test','view_id':view}}))
        # The existing authentication contract silently ignores pre-auth commands.
        with pytest.raises(TimeoutError):
            unauthenticated.recv(timeout=.3)
    assert h.cmd('get_scene_snapshot', scene_id='a') == before
