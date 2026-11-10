"""A receiving thread blocked in a socket read must wake during client close."""
import threading
from unittest.mock import MagicMock

from frameviz.client import FrameVizClient


def test_close_wakes_a_blocked_receiver_before_joining():
    client = FrameVizClient()
    wake = threading.Event()
    transport = MagicMock()
    transport.sock.abort.side_effect = wake.set
    receiver = threading.Thread(target=wake.wait, daemon=True)
    client._ws = transport
    client._ws_thread = receiver
    receiver.start()
    try:
        client.close()
        assert not receiver.is_alive(), 'Close lost a receiving thread blocked in socket read'
        assert client._ws_thread is None
    finally:
        wake.set()
        receiver.join(timeout=1)


def test_reconnect_keeps_and_rejects_a_still_running_old_receiver():
    import pytest
    client = FrameVizClient()
    wake = threading.Event()
    receiver = threading.Thread(target=wake.wait, daemon=True)
    client._ws = MagicMock()
    client._ws_thread = receiver
    receiver.start()
    try:
        client.close()
        assert client._ws_thread is receiver
        with pytest.raises(RuntimeError, match='previous receiving thread'):
            client.connect()
    finally:
        wake.set()
        receiver.join(timeout=1)
