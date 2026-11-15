"""Local example business-channel boundary (separate from Host authentication).

Set FRAMEVIZ_BUSINESS_TOKEN to a random token of at least 32 characters.
The first WebSocket frame authenticates browser examples. Legacy clients may
also send ``token.<value>`` in the subprotocol header.
"""
import asyncio
import hmac
import json
import os
import time
from urllib.parse import urlsplit


def select_business_subprotocol(connection, offered):
    """Permit a first-frame handshake and preserve the existing token subprotocol."""
    # websockets 11–13 call with (client offers, server choices).
    proposals = connection if isinstance(connection, (list, tuple)) else offered
    return "frameviz-business" if "frameviz-business" in proposals else None


async def authorize_business_socket(ws):
    headers = getattr(getattr(ws, 'request', None), 'headers', None)
    if headers is None:
        headers = getattr(ws, 'request_headers', {})
    origin = headers.get('Origin')
    parsed = urlsplit(origin or '')
    allowed_origin = origin is None or (parsed.scheme in ('http', 'https', 'tauri') and
        parsed.hostname in ('localhost', '127.0.0.1', '::1', 'tauri.localhost') and
        not parsed.username and not parsed.password)
    expected = os.environ.get('FRAMEVIZ_BUSINESS_TOKEN', '')
    protocols = headers.get('Sec-WebSocket-Protocol', '')

    def matches(token):
        return isinstance(token, str) and hmac.compare_digest(token.encode(), expected.encode())

    if allowed_origin and len(expected) >= 32:
        if protocols:
            tokens = [item.strip()[6:] for item in protocols.split(',')
                      if item.strip().startswith('token.')]
            if len(tokens) == 1 and matches(tokens[0]):
                return True
        else:
            try:
                raw = await asyncio.wait_for(ws.recv(), 3)
                auth = json.loads(raw) if isinstance(raw, str) and len(raw) <= 65536 else None
                if isinstance(auth, dict) and auth.get('type') == 'auth' and matches(auth.get('token')):
                    await ws.send('{"type":"auth_ok"}')
                    return True
            except (ValueError, asyncio.TimeoutError):
                pass
            except Exception:
                # A client may close while authentication is pending.
                return False
    await ws.close(code=1008, reason='Business authentication required')
    return False


async def business_messages(ws):
    """Bound message size/rate even when a caller uses its own server options."""
    started, count = time.monotonic(), 0
    async for raw in ws:
        now = time.monotonic()
        if now - started >= 1:
            started, count = now, 0
        count += 1
        if not isinstance(raw, str) or len(raw.encode('utf-8')) > 65536 or count > 120:
            await ws.close(code=1008, reason='Business message limit exceeded')
            return
        yield raw
