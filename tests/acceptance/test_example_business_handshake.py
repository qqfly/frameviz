"""Browsers require the server to select an offered business subprotocol."""
import argparse
import asyncio
import importlib.util
from pathlib import Path
import socket
import sys

import pytest
from websockets.asyncio.client import connect

ROOT = Path(__file__).resolve().parents[2]


@pytest.mark.parametrize("example", ["simple_slider", "urdf_robot", "external_template"])
def test_python_example_selects_business_protocol_and_retains_auth(example, monkeypatch):
    path = ROOT / "examples/apps" / example / "python" / ("backend_simple_slider.py" if example == "simple_slider" else "backend_urdf.py")
    if example == "external_template":
        path = ROOT / "templates/frameviz-template-external-app/python/backend_external_app.py"
    name = "handshake_" + example
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, name, module)
    spec.loader.exec_module(module)
    token = "synthetic-local-business-token-0123456789"
    monkeypatch.setenv("FRAMEVIZ_BUSINESS_TOKEN", token)
    monkeypatch.setattr(module.fv, "is_host_running", lambda: True)
    monkeypatch.setattr(module.fv, "list_views", lambda **kwargs: [])
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    if example in {"simple_slider", "external_template"}:
        args = argparse.Namespace(ws_host="127.0.0.1", ws_port=port, viewer_name="test", host_headless=True)
        if example == "external_template":
            args.parent_pid = 0
            args.frameviz_host = f"ws://127.0.0.1:{port}"
            args.connect_timeout = 0.5
        start = lambda: module.run_backend(args)
    else:
        monkeypatch.setattr(module, "WS_PORT", port)
        monkeypatch.setattr(module, "parse_args", lambda: argparse.Namespace(path=None))
        monkeypatch.setattr(module, "_get_mesh_base_urls", lambda path: ("http://127.0.0.1/visual", "http://127.0.0.1/collision", None))
        monkeypatch.setattr(module, "_maybe_start_asset_server", lambda: None)
        monkeypatch.setattr(module, "_wait_asset_server_ready", lambda: None)
        start = module.main

    async def scenario():
        import json
        task = asyncio.create_task(start())
        try:
            for _ in range(100):
                try:
                    ws = await connect(f"ws://127.0.0.1:{port}", origin="http://localhost:8088", subprotocols=["frameviz-business", "token." + token])
                    break
                except OSError:
                    await asyncio.sleep(0.01)
            else:
                raise AssertionError("Business server didn't start")
            async with ws:
                assert ws.subprotocol == "frameviz-business", "A browser rejects a handshake without a selected protocol"
                assert json.loads(await ws.recv())["type"] == "state_update"
            for origin, protocols in [
                ("http://localhost:8088", ["frameviz-business", "token.wrong"]),
                ("http://localhost:8088", ["frameviz-business"]),
                ("https://untrusted.invalid", ["frameviz-business", "token." + token]),
            ]:
                async with connect(f"ws://127.0.0.1:{port}", origin=origin, subprotocols=protocols) as rejected:
                    from websockets.exceptions import ConnectionClosed
                    with pytest.raises(ConnectionClosed) as exc:
                        await rejected.recv()
                    assert exc.value.rcvd.code == 1008
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    asyncio.run(scenario())
