"""
Unit tests for frameviz/client.py WebSocket client.

Tests cover:
- Connection management (connect, close)
- Command sending and response handling
- Binary data transmission
- Event handling and dispatching
- Message parsing
- Error handling
"""
from __future__ import annotations

import json
import queue
import threading
import time
from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from frameviz.client import FrameVizClient, PROTOCOL_VERSION, DEFAULT_WS_URL

# =============================================================================
# Connection Management Tests
# =============================================================================


class TestConnection:
    """Tests for connection management."""

    def test_client_default_values(self):
        """Test client has correct default values."""
        client = FrameVizClient()
        assert client.url == DEFAULT_WS_URL
        assert client.timeout == 10.0

    def test_client_custom_values(self):
        """Test client accepts custom values."""
        client = FrameVizClient(url="ws://localhost:8080", timeout=5.0)
        assert client.url == "ws://localhost:8080"
        assert client.timeout == 5.0

    def test_connect_already_connected(self, mock_client):
        """Test that calling connect when already connected is a no-op."""
        client, _ = mock_client
        # Client is already connected via fixture
        # Calling connect again should not raise
        client.connect()

    def test_close_cleans_up(self, mock_client):
        """Test that close properly cleans up resources."""
        client, mock_server = mock_client
        client.close()
        assert mock_server._closed

    def test_send_command_not_connected_raises(self):
        """Test that sending command without connection raises error."""
        client = FrameVizClient()
        with pytest.raises(RuntimeError, match="not connected"):
            client.send_command("test", {})


# =============================================================================
# Command Sending Tests
# =============================================================================


class TestSendCommand:
    """Tests for send_command method."""

    def test_send_command_success(self, mock_client):
        """Test successful command sending and response."""
        client, mock_server = mock_client
        mock_server.configure_response("ping", {"pong": True})

        result = client.send_command("ping", {"value": 1})

        assert result == {"pong": True}

    def test_send_command_envelope_format(self, mock_client):
        """Test that command envelope has correct format."""
        client, mock_server = mock_client
        mock_server.configure_response("test", {})

        client.send_command("test", {"arg1": "value1"})

        cmd = mock_server.get_last_command()
        assert cmd["protocol_version"] == PROTOCOL_VERSION
        assert cmd["type"] == "cmd"
        assert "id" in cmd
        assert cmd["name"] == "test"
        assert cmd["args"]["arg1"] == "value1"

    def test_send_command_error_response(self, mock_client):
        """Test that error response raises RuntimeError."""
        client, mock_server = mock_client
        mock_server.configure_error("failing_cmd", "ERR_001",
                                    "Something went wrong")

        with pytest.raises(RuntimeError, match="ERR_001.*Something went wrong"):
            client.send_command("failing_cmd", {})

    def test_send_command_increments_request_id(self, mock_client):
        """Test that each command gets a unique ID."""
        client, mock_server = mock_client
        mock_server.configure_response("cmd1", {})
        mock_server.configure_response("cmd2", {})

        client.send_command("cmd1", {})
        client.send_command("cmd2", {})

        commands = mock_server.get_all_commands()
        assert commands[0]["id"] != commands[1]["id"]


class TestSendCommandWithBinary:
    """Tests for send_command_with_binary method."""

    def test_send_binary_data(self, mock_client):
        """Test sending command with binary data."""
        client, mock_server = mock_client
        mock_server.configure_response("upload_buffer_chunk", {})

        binary_data = b'\x00\x01\x02\x03\x04\x05'
        result = client.send_command_with_binary("upload_buffer_chunk", {
            "buffer_id": "buf_1",
            "offset": 0
        }, binary_data)

        # Verify binary was sent
        assert len(mock_server.sent_binary) == 1
        assert mock_server.sent_binary[0] == binary_data

    def test_send_command_with_binary_not_connected(self):
        """Test that binary command without connection raises error."""
        client = FrameVizClient()
        with pytest.raises(RuntimeError, match="not connected"):
            client.send_command_with_binary("test", {}, b"data")


# =============================================================================
# Event Handling Tests
# =============================================================================


class TestEventHandling:
    """Tests for event handling methods."""

    def test_on_event_registers_handler(self, mock_client):
        """Test that on_event registers a handler."""
        client, _ = mock_client
        handler = MagicMock()

        client.on_event("test_event", handler)

        assert "test_event" in client._event_handlers
        assert handler in client._event_handlers["test_event"]

    def test_on_event_multiple_handlers(self, mock_client):
        """Test registering multiple handlers for same event."""
        client, _ = mock_client
        handler1 = MagicMock()
        handler2 = MagicMock()

        client.on_event("test_event", handler1)
        client.on_event("test_event", handler2)

        assert len(client._event_handlers["test_event"]) == 2

    def test_off_event_removes_handler(self, mock_client):
        """Test that off_event removes a specific handler."""
        client, _ = mock_client
        handler = MagicMock()

        client.on_event("test_event", handler)
        client.off_event("test_event", handler)

        assert handler not in client._event_handlers.get("test_event", [])

    def test_off_event_removes_all_handlers(self, mock_client):
        """Test that off_event with no handler removes all handlers."""
        client, _ = mock_client
        handler1 = MagicMock()
        handler2 = MagicMock()

        client.on_event("test_event", handler1)
        client.on_event("test_event", handler2)
        client.off_event("test_event")

        assert "test_event" not in client._event_handlers

    def test_poll_events_dispatches_events(self, mock_client):
        """Test that poll_events dispatches queued events."""
        client, _ = mock_client
        handler = MagicMock()
        client.on_event("test_event", handler)

        # Manually queue an event
        client._event_queue.put(("test_event", {"value": 42}))

        client.poll_events()

        handler.assert_called_once_with({"value": 42})

    def test_poll_events_handles_multiple_events(self, mock_client):
        """Test that poll_events handles multiple events."""
        client, _ = mock_client
        handler = MagicMock()
        client.on_event("test_event", handler)

        client._event_queue.put(("test_event", {"value": 1}))
        client._event_queue.put(("test_event", {"value": 2}))
        client._event_queue.put(("test_event", {"value": 3}))

        client.poll_events()

        assert handler.call_count == 3

    def test_poll_events_handler_error_does_not_stop_processing(
            self, mock_client, capsys):
        """Test that handler errors don't stop event processing."""
        client, _ = mock_client

        def failing_handler(data):
            raise ValueError("Handler error")

        good_handler = MagicMock()
        client.on_event("event1", failing_handler)
        client.on_event("event2", good_handler)

        client._event_queue.put(("event1", {}))
        client._event_queue.put(("event2", {"ok": True}))

        client.poll_events()

        # Good handler should still be called
        good_handler.assert_called_once()


class TestWaitForEvent:
    """Tests for wait_for_event method."""

    def test_wait_for_event_success(self, mock_client):
        """Test waiting for an event that arrives."""
        client, _ = mock_client

        # Queue event in background thread
        def queue_event():
            time.sleep(0.1)
            client._event_queue.put(("target_event", {"data": "found"}))

        thread = threading.Thread(target=queue_event)
        thread.start()

        result = client.wait_for_event("target_event", timeout=2.0)
        thread.join()

        assert result == {"data": "found"}

    def test_wait_for_event_timeout(self, mock_client):
        """Test wait_for_event returns None on timeout."""
        client, _ = mock_client

        result = client.wait_for_event("never_arrives", timeout=0.1)

        assert result is None

    def test_wait_for_event_with_filter(self, mock_client):
        """Test wait_for_event with filter function."""
        client, _ = mock_client

        def queue_events():
            time.sleep(0.05)
            client._event_queue.put(("event", {"id": 1}))
            time.sleep(0.05)
            client._event_queue.put(("event", {"id": 2}))

        thread = threading.Thread(target=queue_events)
        thread.start()

        # Filter for id=2
        result = client.wait_for_event("event",
                                       timeout=2.0,
                                       filter_fn=lambda d: d.get("id") == 2)
        thread.join()

        assert result == {"id": 2}


# =============================================================================
# Message Parsing Tests
# =============================================================================


class TestHandleMessage:
    """Tests for _handle_message method."""

    def test_handle_resp_message(self, mock_client):
        """Test handling response message."""
        client, _ = mock_client

        # Set up a pending request
        wait_event = threading.Event()
        client._pending["test_id"] = wait_event

        # Simulate response
        response = {
            "protocol_version": PROTOCOL_VERSION,
            "type": "resp",
            "id": "test_id",
            "ok": True,
            "result": {
                "data": "test"
            }
        }

        client._handle_message(json.dumps(response))

        # Wait event should be set
        assert wait_event.is_set()
        # Response should be stored
        assert client._responses.get("test_id") == response

    def test_handle_event_message(self, mock_client):
        """Test handling event message."""
        client, _ = mock_client

        event = {
            "protocol_version": PROTOCOL_VERSION,
            "type": "event",
            "name": "test_event",
            "data": {
                "value": 123
            }
        }

        client._handle_message(json.dumps(event))

        # Event should be queued
        queued_event = client._event_queue.get_nowait()
        assert queued_event == ("test_event", {"value": 123})

    def test_handle_invalid_json(self, mock_client):
        """Test handling invalid JSON message."""
        client, _ = mock_client

        # Should not raise
        client._handle_message("not valid json {{{")

    def test_handle_event_without_name(self, mock_client):
        """Test handling event without name is ignored."""
        client, _ = mock_client

        event = {"type": "event", "data": {"value": 123}}

        client._handle_message(json.dumps(event))

        # Event should not be queued
        assert client._event_queue.empty()


# =============================================================================
# Binary Data Tests
# =============================================================================


class TestSendBinary:
    """Tests for send_binary method."""

    def test_send_binary_success(self, mock_client):
        """Test sending binary data."""
        client, mock_server = mock_client

        binary_data = b'\xff\xfe\xfd'
        client.send_binary(binary_data)

        # Binary should be recorded
        assert binary_data in mock_server.sent_binary

    def test_send_binary_not_connected(self):
        """Test send_binary raises when not connected."""
        client = FrameVizClient()
        with pytest.raises(RuntimeError, match="not connected"):
            client.send_binary(b"data")


# =============================================================================
# Protocol Version Tests
# =============================================================================


class TestProtocolVersion:
    """Tests for protocol version handling."""

    def test_protocol_version_constant(self):
        """Test protocol version constant is a valid semver string."""
        import re
        assert re.match(r'^\d+\.\d+\.\d+$', PROTOCOL_VERSION)

    def test_commands_include_protocol_version(self, mock_client):
        """Test all commands include protocol version."""
        client, mock_server = mock_client
        mock_server.configure_response("test", {})

        client.send_command("test", {})

        cmd = mock_server.get_last_command()
        assert cmd["protocol_version"] == PROTOCOL_VERSION


# =============================================================================
# Module-level open() Function Tests
# =============================================================================


class TestOpenFunction:
    """Tests for the module-level open() function."""

    def test_open_creates_connected_client(self):
        """Test that open() creates and connects a client."""
        # This would require mocking the actual WebSocket connection
        # Skipping as it requires integration with real server
        pass
