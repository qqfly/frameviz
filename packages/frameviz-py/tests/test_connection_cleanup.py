"""Failed transport operations must not retain requests or stale query replies."""
import pytest
from frameviz.client import FrameVizClient

@pytest.mark.parametrize('binary',[False,True])
def test_send_exception_releases_pending_request(binary):
    class ClosedTransport:
        def send(self,*args,**kwargs):raise RuntimeError('synthetic transport closed')
    client=FrameVizClient('ws://127.0.0.1:1')
    client._ws=ClosedTransport()
    with pytest.raises(RuntimeError,match='transport closed'):
        if binary:client.send_command_with_binary('upload_buffer_chunk',{},b'123')
        else:client.send_command('list_scenes')
    assert not client._pending and not client._responses
    client._ws=None

def test_close_discards_previous_session_query_replies():
    client=FrameVizClient('ws://127.0.0.1:1')
    client._query_events['previous-session']=('camera_pose_response',{})
    client.close()
    assert not client._query_events
