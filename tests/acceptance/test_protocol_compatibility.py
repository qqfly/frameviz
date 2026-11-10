"""Version rejection is atomic; compatible patch commands use a real Host."""
import pytest
import json
from test_host_contracts import h


@pytest.mark.parametrize('version',['0.4.1','0.4.99'])
def test_real_host_accepts_patch_commands(h,version):
    view=h.view('compatible');ws=h.viewer(view)
    reply=h.request(ws,'get_scene_snapshot',{},version=version)
    assert reply['ok'],reply


@pytest.mark.parametrize('version,upgrade',[('0.3.9','SDK'),('0.5.0','runtime'),('1.0.0','runtime')])
def test_real_host_rejects_other_series_without_changes(h,version,upgrade):
    view=h.view('original');ws=h.viewer(view);before=h.cmd('get_scene_snapshot',scene_id='original')
    reply=h.request(ws,'add_primitive',{'scene_id':'original','type':'box'},version=version)
    assert not reply['ok'] and reply['error']['code']=='ERR_PROTOCOL_VERSION'
    assert 'Upgrade' in reply['error']['message'] and upgrade in reply['error']['message']
    assert h.cmd('get_scene_snapshot',scene_id='original')==before


@pytest.mark.parametrize('version,accepted',[('0.4.9',True),('0.3.9',False),(None,False)])
def test_viewer_events_obey_the_same_version_boundary(h,version,accepted):
    view=h.view('events');ws=h.viewer(view)
    event={'type':'event','name':'key_down','data':{'key':'version-boundary'}}
    if version is not None:event['protocol_version']=version
    ws.send(json.dumps(event))
    received=h.c.wait_for_event('key_down',timeout=.25,filter_fn=lambda d:d.get('key')=='version-boundary')
    assert bool(received)==accepted
