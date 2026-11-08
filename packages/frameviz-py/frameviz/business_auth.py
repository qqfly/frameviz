"""Local example business-channel boundary (separate from Host authentication).

Set FRAMEVIZ_BUSINESS_TOKEN to a random token of at least 32 characters.
Browsers send it in the WebSocket subprotocol header as ``token.<value>``.
It is never sent in a URL or copied from the Host discovery file.
"""
import asyncio
import hmac
import os
import time
from urllib.parse import urlsplit


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
    tokens = [item.strip()[6:] for item in headers.get('Sec-WebSocket-Protocol', '').split(',')
              if item.strip().startswith('token.')]
    valid = len(expected) >= 32 and len(tokens) == 1 and hmac.compare_digest(tokens[0], expected)
    if not allowed_origin or not valid:
        await ws.close(code=1008, reason='Business authentication required')
        return False
    return True


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
