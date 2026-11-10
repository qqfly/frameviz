from __future__ import annotations

import json
import queue
import socket
import sys
import threading
import time
import traceback
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple

import websocket  # websocket-client library

from .exceptions import (
    ConnectionError as FrameVizConnectionError,
    TimeoutError as FrameVizTimeoutError,
    ProtocolError,
)
from .discovery import get_discovery_path, get_token_from_discovery, get_ws_url_from_discovery
from .version import host_version_error

PROTOCOL_VERSION = "0.4.0"
MIN_COMPATIBLE_VERSION = "0.4.0"  # Minimum Host version SDK can work with
DEFAULT_WS_URL = "ws://127.0.0.1:9527"

# P0-2: Token authentication support
import os
import warnings

EventHandler = Callable[[Dict[str, Any]], None]


@dataclass
class FrameVizClient:
    """
    Synchronous Python client for the FrameViz protocol.

    Uses a background thread for WebSocket I/O while providing a synchronous
    API to the caller. Commands block until the Host returns a response.
    Callbacks run serially on a separate background thread after authentication.
    Set auto_events=False to dispatch manually with spin() or poll_events().
    """

    url: str = DEFAULT_WS_URL
    timeout: float = 10.0
    token: Optional[str] = None
    auto_events: bool = True

    # Internal state (initialized in __post_init__ or connect)
    _ws: Optional[websocket.WebSocketApp] = field(default=None,
                                                  init=False,
                                                  repr=False)
    _ws_thread: Optional[threading.Thread] = field(default=None,
                                                   init=False,
                                                   repr=False)
    _connected: threading.Event = field(default_factory=threading.Event,
                                        init=False,
                                        repr=False)
    _opened: threading.Event = field(default_factory=threading.Event,
                                     init=False,
                                     repr=False)
    _closing: bool = field(default=False, init=False, repr=False)
    _connect_error: Optional[BaseException] = field(default=None,
                                                    init=False,
                                                    repr=False)

    _request_id: int = field(default=0, init=False, repr=False)
    _pending: Dict[str, threading.Event] = field(default_factory=dict,
                                                 init=False,
                                                 repr=False)
    _responses: Dict[str, Dict[str, Any]] = field(default_factory=dict,
                                                  init=False,
                                                  repr=False)
    _lock: threading.Lock = field(default_factory=threading.Lock,
                                  init=False,
                                  repr=False)

    _send_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    _event_queue: "queue.Queue[Tuple[str, Dict[str, Any]]]" = field(
        default_factory=lambda: queue.Queue(maxsize=4096), init=False, repr=False)
    _query_events: Dict[str, Tuple[str, Dict[str, Any]]] = field(default_factory=dict, init=False, repr=False)
    _event_handlers: Dict[str, List[EventHandler]] = field(default_factory=dict,
                                                           init=False)

    # P0-2: Authentication
    _auth_token: Optional[str] = field(default=None, init=False)
    _auth_event: threading.Event = field(default_factory=threading.Event,
                                         init=False)
    _auth_ok: bool = field(default=False, init=False)

    # P1-3: Version compatibility
    _host_protocol_version: Optional[str] = field(default=None, init=False)
    _event_thread: Optional[threading.Thread] = field(default=None, init=False, repr=False)
    _event_stop: threading.Event = field(default_factory=threading.Event, init=False, repr=False)
    _event_condition: threading.Condition = field(init=False, repr=False)
    _event_history: Dict[int, Tuple[str, Dict[str, Any]]] = field(default_factory=dict, init=False, repr=False)
    _event_sequence: int = field(default=0, init=False, repr=False)

    def __post_init__(self) -> None:
        self._event_condition = threading.Condition(self._lock)

    def connect(self) -> None:
        """Connect to the Host WebSocket endpoint (blocking until open)."""
        if self._ws is not None and self._opened.is_set():
            return
        if self._ws is not None:
            self.close()
        if self._ws_thread is not None and self._ws_thread.is_alive():
            raise RuntimeError("The previous receiving thread is still closing; reconnect after it finishes")
        if self._event_thread is not None and self._event_thread.is_alive():
            raise RuntimeError("The previous callback is still running; reconnect after it finishes")

        self._closing = False
        self._event_stop = threading.Event()
        self._connected.clear()
        self._opened.clear()
        self._connect_error = None

        def on_open(ws: websocket.WebSocket) -> None:
            self._opened.set()
            self._connected.set()

        def on_message(ws: websocket.WebSocket, message: str) -> None:
            self._handle_message(message)

        def on_error(ws: websocket.WebSocket, error: Exception) -> None:
            self._connect_error = error
            self._connected.set()

        def on_close(ws: websocket.WebSocket, close_status_code: Any,
                     close_msg: Any) -> None:
            if not self._opened.is_set() and self._connect_error is None:
                self._connect_error = RuntimeError(
                    "Connection closed before open.")
            self._opened.clear()
            self._closing = True
            self._event_stop.set()
            self._connected.set()
            # Reject any pending requests
            with self._lock:
                for evt in self._pending.values():
                    evt.set()
                self._pending.clear()
                self._responses.clear()
                self._query_events.clear()
                self._event_condition.notify_all()

        self._ws = websocket.WebSocketApp(
            self.url,
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close,
        )

        self._ws_thread = threading.Thread(target=self._ws.run_forever,
                                           daemon=True)
        self._ws_thread.start()

        self._connected.wait(timeout=float(self.timeout))

        if self._opened.is_set():
            # P0-2: Authenticate after successful connection
            try:
                self._authenticate()
            except Exception:
                # P2: Close socket/thread on auth failure to avoid resource leak
                self.close()
                raise
            if self.auto_events:
                self._event_thread = threading.Thread(
                    target=self._run_events, args=(self._event_stop,),
                    name="FrameViz callbacks", daemon=True)
                self._event_thread.start()
            return

        self.close()
        if self._connect_error is not None:
            raise FrameVizConnectionError(
                f"Failed to connect to {self.url}: {self._connect_error}",
                url=self.url,
                cause=self._connect_error)
        raise FrameVizTimeoutError(f"Failed to connect to {self.url}",
                                   operation="connect",
                                   timeout_seconds=self.timeout)

    def _authenticate(self) -> None:
        """P0-2: Send authentication message after connect."""
        token = self._resolve_token()
        if token is None:
            raise ProtocolError("Authentication token required", code="AUTH_REQUIRED")

        self._auth_event.clear()
        self._auth_ok = False
        self._host_protocol_version = None

        auth_msg = {"type": "auth", "token": token}
        self._ws.send(json.dumps(auth_msg))

        # Wait for auth response
        if not self._auth_event.wait(timeout=float(self.timeout)):
            raise FrameVizTimeoutError("Authentication timed out",
                                       operation="authenticate",
                                       timeout_seconds=self.timeout)

        if not self._auth_ok:
            raise ProtocolError("Authentication failed: invalid token",
                                code="AUTH_FAILED")
        self._check_version_compatibility(self._host_protocol_version)

    def _check_version_compatibility(self, host_version: str) -> None:
        """Reject incompatible series on the calling thread after authentication."""
        error=host_version_error(host_version, PROTOCOL_VERSION)
        if error:raise ProtocolError(error, code="ERR_PROTOCOL_VERSION")

    @staticmethod
    def _parse_version(version: str) -> tuple:
        """Parse semver string to tuple for comparison."""
        parts = version.split(".")
        return tuple(int(p) for p in parts[:3])

    def _resolve_token(self) -> Optional[str]:
        """P0-2: Read token from discovery file (host.json)."""
        if self.token is not None:
            return self.token
        explicit = os.environ.get("FRAMEVIZ_AUTH_TOKEN")
        if explicit:
            return explicit
        from urllib.parse import urlsplit
        discovered = get_ws_url_from_discovery()
        if not discovered:
            return None
        def endpoint(url):
            value = urlsplit(url)
            host = value.hostname
            if host in ("localhost", "127.0.0.1", "::1"):
                host = "loopback"
            return value.scheme, host, value.port or (443 if value.scheme == "wss" else 80)
        return get_token_from_discovery() if endpoint(discovered) == endpoint(self.url) else None

    def close(self) -> None:
        """Close the WebSocket connection."""
        self._closing = True
        self._event_stop.set()
        with self._lock:
            for event in self._pending.values():
                event.set()
            self._pending.clear()
            self._responses.clear()
            self._query_events.clear()
            self._event_history.clear()
            self._event_condition.notify_all()
        app = self._ws
        if app:
            # Closing an fd from another thread need not wake a Linux socket
            # read. Capture it before receiver teardown clears the wrapper.
            transport = app.sock
            raw_socket = transport.sock if transport is not None else None
            app.keep_running = False
            if transport is not None:
                transport.abort()
            if raw_socket is not None:
                try:
                    raw_socket.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass  # Another teardown may already have closed it.
        if self._ws_thread and self._ws_thread.is_alive() and self._ws_thread is not threading.current_thread():
            self._ws_thread.join(timeout=2.0)
        # Keep the fd present until the selector can consume its shutdown
        # event. Removing it first can leave Linux epoll waiting on an empty set.
        if app:
            app.close()
        if self._event_thread and self._event_thread is not threading.current_thread():
            self._event_thread.join(timeout=2.0)
        self._ws = None
        if self._ws_thread is not None and not self._ws_thread.is_alive():
            self._ws_thread = None
        while True:
            try:
                self._event_queue.get_nowait()
            except queue.Empty:
                break

    def _run_events(self, stop: threading.Event) -> None:
        while not stop.is_set():
            try:
                event = self._event_queue.get(timeout=0.1)
            except queue.Empty:
                continue
            if not stop.is_set():
                self._dispatch_event(*event)

    def send_command(self,
                     name: str,
                     args: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Send a command and block until the response arrives.

        Raises RuntimeError on protocol errors or timeouts.
        """
        if self._ws is None:
            raise RuntimeError("WebSocket not connected. Call connect() first.")

        with self._lock:
            self._request_id += 1
            cmd_id = f"c_{self._request_id}"
            wait_event = threading.Event()
            self._pending[cmd_id] = wait_event

        try:
            envelope = {
                "protocol_version": PROTOCOL_VERSION,
                "type": "cmd",
                "id": cmd_id,
                "name": name,
                "args": args or {},
            }

            with self._send_lock:
                self._ws.send(json.dumps(envelope))

            if not wait_event.wait(timeout=self.timeout):
                with self._lock:
                    self._pending.pop(cmd_id, None)
                raise TimeoutError(
                    f"Command '{name}' timed out waiting for response.")

            with self._lock:
                self._pending.pop(cmd_id, None)
                response = self._responses.pop(cmd_id, None)

            if response is None:
                raise RuntimeError("Connection closed while waiting for response.")

            if not response.get("ok", False):
                error = response.get("error") or {}
                code = error.get("code", "UNKNOWN")
                msg = error.get("message", "Command failed")
                raise RuntimeError(f"[{code}] {msg}")

            return response.get("result") or {}
        finally:
            with self._lock:
                self._pending.pop(cmd_id, None)
                self._responses.pop(cmd_id, None)

    def send_command_with_binary(
        self,
        name: str,
        args: Dict[str, Any],
        binary_data: bytes,
    ) -> Dict[str, Any]:
        """
        Send a command followed immediately by a binary frame, then wait for response.

        This is used for upload_buffer_chunk where the protocol requires:
        1. Send JSON command
        2. Send binary frame
        3. Wait for response

        The command and binary frame must be sent atomically to avoid interleaving.
        """
        if self._ws is None:
            raise RuntimeError("WebSocket not connected. Call connect() first.")

        with self._lock:
            self._request_id += 1
            cmd_id = f"c_{self._request_id}"
            wait_event = threading.Event()
            self._pending[cmd_id] = wait_event

        try:
            envelope = {
                "protocol_version": PROTOCOL_VERSION,
                "type": "cmd",
                "id": cmd_id,
                "name": name,
                "args": args,
            }

            # Send both JSON and binary atomically (under lock to prevent interleaving)
            with self._send_lock:
                self._ws.send(json.dumps(envelope))
                self._ws.send(binary_data, opcode=websocket.ABNF.OPCODE_BINARY)

            if not wait_event.wait(timeout=self.timeout):
                with self._lock:
                    self._pending.pop(cmd_id, None)
                raise TimeoutError(
                    f"Command '{name}' timed out waiting for response.")

            with self._lock:
                self._pending.pop(cmd_id, None)
                response = self._responses.pop(cmd_id, None)

            if response is None:
                raise RuntimeError("Connection closed while waiting for response.")

            if not response.get("ok", False):
                error = response.get("error") or {}
                code = error.get("code", "UNKNOWN")
                msg = error.get("message", "Command failed")
                raise RuntimeError(f"[{code}] {msg}")

            return response.get("result") or {}
        finally:
            with self._lock:
                self._pending.pop(cmd_id, None)
                self._responses.pop(cmd_id, None)

    def send_binary(self, data: bytes) -> None:
        """Send a binary WebSocket frame (used for buffer uploads)."""
        if self._ws is None:
            raise RuntimeError("WebSocket not connected.")
        with self._send_lock:
            self._ws.send(data, opcode=websocket.ABNF.OPCODE_BINARY)

    def on_event(self, name: str, handler: EventHandler) -> None:
        """Register a handler for a protocol event."""
        with self._lock:
            self._event_handlers.setdefault(name, []).append(handler)

    def off_event(self,
                  name: str,
                  handler: Optional[EventHandler] = None) -> None:
        """Remove event handler(s). If handler is None, remove all for that event."""
        with self._lock:
            if handler is None:
                self._event_handlers.pop(name, None)
            else:
                handlers = self._event_handlers.get(name, [])
                if handler in handlers:
                    handlers.remove(handler)

    def wait_for_event(
        self,
        name: str,
        timeout: float = 5.0,
        filter_fn: Optional[Callable[[Dict[str, Any]], bool]] = None
    ) -> Optional[Dict[str, Any]]:
        """Wait for a specific event to arrive and return its data.

        Args:
            name: The event name to wait for.
            timeout: Maximum time to wait in seconds.
            filter_fn: Optional function to filter events. If provided, only events
                      for which filter_fn(data) returns True will be matched.

        Returns:
            The event data dict, or None if timeout.
        """
        if self.auto_events and self._event_thread is not None:
            return self._wait_automatic_event(name, timeout, filter_fn)
        result: List[Dict[str, Any]] = []
        received = threading.Event()

        def handler(data: Dict[str, Any]) -> None:
            # Apply filter if provided
            if filter_fn is None or filter_fn(data):
                result.append(data)
                received.set()

        self.on_event(name, handler)
        try:
            deadline = time.monotonic() + timeout
            while not received.is_set():
                # Correlated query responses are retained independently of event dispatch.
                with self._lock:
                    queries = list(self._query_events.items())
                for request_id, (event_name, data) in queries:
                    if event_name == name and (filter_fn is None or filter_fn(data)):
                        with self._lock:
                            retained = self._query_events.pop(request_id, None)
                        if retained is not None:
                            result.append(data)
                            received.set()
                            break
                self.poll_events()
                if received.is_set():
                    break

                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    break

                try:
                    # Efficiently wait for the next event to arrive
                    event_info = self._event_queue.get(timeout=min(remaining, 0.02))
                    self._dispatch_event(*event_info)
                except queue.Empty:
                    continue

            return result[0] if result else None
        finally:
            self.off_event(name, handler)

    def spin(self) -> None:
        """Process events in a blocking loop until the connection closes."""
        if self.auto_events and self._event_thread is not None:
            self._event_stop.wait()
            return
        while self._ws is not None and not self._closing:
            self.poll_events()
            if self._closing or self._ws is None:
                break
            try:
                # Efficiently wait for events, checking status every 100ms
                event_info = self._event_queue.get(timeout=0.1)
                self._dispatch_event(*event_info)
            except queue.Empty:
                pass

    def _dispatch_event(self, event_name: str, data: Dict[str, Any]) -> None:
        """Internal helper to call handlers for a single event."""
        with self._lock:
            handlers = tuple(self._event_handlers.get(event_name, []))
        for handler in handlers:
            if self._closing:
                break
            try:
                handler(data)
            except Exception:
                sys.stderr.write(f"[FrameViz] Event '{event_name}' handler failed:\n{traceback.format_exc()}")

    def poll_events(self) -> None:
        """Dispatch all queued events without blocking."""
        if self.auto_events and self._event_thread is not None:
            return
        while True:
            try:
                event_info = self._event_queue.get_nowait()
                self._dispatch_event(*event_info)
            except queue.Empty:
                break

    def _wait_automatic_event(self, name: str, timeout: float,
                              filter_fn: Optional[Callable[[Dict[str, Any]], bool]]) -> Optional[Dict[str, Any]]:
        deadline = time.monotonic() + timeout
        while True:
            with self._lock:
                candidates = [(self._query_events, key, event) for key, event in self._query_events.items()]
                candidates.extend((self._event_history, key, event) for key, event in self._event_history.items())
            # Filters may call the SDK. Never execute application code under
            # internal locks or on the WebSocket receiving thread.
            for source, key, (event_name, data) in candidates:
                if event_name == name and (filter_fn is None or filter_fn(data)):
                    with self._lock:
                        if source.pop(key, None) is not None:
                            return data
            remaining = deadline - time.monotonic()
            if remaining <= 0 or self._closing:
                return None
            with self._event_condition:
                self._event_condition.wait(timeout=min(remaining, 0.02))

    def _handle_message(self, message: str) -> None:
        """Parse an incoming message and route it appropriately."""
        try:
            envelope = json.loads(message)
        except json.JSONDecodeError:
            return

        msg_type = envelope.get("type")

        if msg_type == "resp":
            cmd_id = envelope.get("id")
            if cmd_id:
                with self._lock:
                    evt = self._pending.get(cmd_id)
                    if evt:
                        self._responses[cmd_id] = envelope
                if evt:
                    evt.set()
            return

        if msg_type == "event":
            event_name = envelope.get("name", "")
            data = envelope.get("data", {})
            if not event_name:
                return
            if data.get("request_id") and event_name.endswith("_response"):
                with self._lock:
                    if len(self._query_events) >= 4096:
                        self._query_events.pop(next(iter(self._query_events)))
                    self._query_events[data["request_id"]] = (event_name, data)
                    self._event_condition.notify_all()
                return
            if self.auto_events:
                with self._lock:
                    self._event_sequence += 1
                    if len(self._event_history) >= 4096:
                        self._event_history.pop(next(iter(self._event_history)))
                    self._event_history[self._event_sequence] = (event_name, data)
                    self._event_condition.notify_all()
            try:
                self._event_queue.put_nowait((event_name, data))
            except queue.Full:
                self._connect_error = ProtocolError("Event queue overflow; reconnect required", code="ERR_EVENT_OVERFLOW")
                if self._ws is not None:
                    self._ws.close()
            return

        # P0-2: Handle authentication response
        if msg_type == "auth_resp":
            self._auth_ok = envelope.get("ok", False)
            # P1-3: Capture and check Host protocol version
            host_version = envelope.get("protocol_version")
            if host_version:
                self._host_protocol_version = host_version
            self._auth_event.set()


def open(url: str = DEFAULT_WS_URL, timeout: float = 10.0, *, auto_events: bool = True) -> FrameVizClient:
    """Create a client, connect it, and return the instance."""
    client = FrameVizClient(url=url, timeout=timeout, auto_events=auto_events)
    client.connect()
    return client
