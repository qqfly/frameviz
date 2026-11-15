"""Open the built Simple Slider app with temporary local credentials.

Build from the repo root: pnpm --filter simple-slider-app build
Run with the matching Python SDK and installed App/Host available.
"""
import argparse
from contextlib import redirect_stdout
import functools
import http.server
import io
import os
from pathlib import Path
import secrets
import subprocess
import sys
import tempfile
import threading
import time
from urllib.parse import urlencode, urlsplit
import webbrowser

import frameviz as fv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui-dir", type=Path, default=Path(__file__).resolve().parents[1] / "dist")
    args = parser.parse_args()
    ui_dir = args.ui_dir.resolve()
    if not (ui_dir / "index.html").is_file():
        parser.error("Build the UI first: pnpm --filter simple-slider-app build")
    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(ui_dir)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    viz = backend = None
    try:
        # The launcher supplies both credentials directly to the browser.
        with redirect_stdout(io.StringIO()):
            viz = fv.open(title="Vue slider application", window_mode=0)
        token = viz._client._auth_token
        ws_port = urlsplit(viz._client.url).port
        if not token or not ws_port:
            raise RuntimeError("No authenticated local FrameViz Host")
        business_token = secrets.token_urlsafe(32)
        env = dict(os.environ, FRAMEVIZ_BUSINESS_TOKEN=business_token,
                   SIMPLE_SLIDER_WS_HOST="127.0.0.1", SIMPLE_SLIDER_WS_PORT="0")
        with tempfile.TemporaryDirectory(prefix="frameviz-slider-") as temporary:
            ready = Path(temporary) / "business-port"
            backend = subprocess.Popen([
                sys.executable, "-u", str(Path(__file__).with_name("backend_simple_slider.py")),
                "--ready-file", str(ready),
            ], env=env)
            deadline = time.monotonic() + 10
            while not ready.exists() and backend.poll() is None and time.monotonic() < deadline:
                time.sleep(.025)
            if not ready.is_file():
                raise RuntimeError("Simple Slider business backend did not start")
            business_port = int(ready.read_text(encoding="utf-8"))
        url = f"http://127.0.0.1:{server.server_port}/?" + urlencode({
            "view_id": viz.view_id, "ws_port": ws_port, "business_port": business_port,
        })
        url += "#" + urlencode({"token": token, "business_token": business_token})
        webbrowser.open(url)
        print("Opened Simple Slider. Keep its temporary session URL private.")
        input("Move the sliders; press Enter to stop this demo... ")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        if backend:
            if backend.poll() is None:
                backend.terminate()
            backend.wait(timeout=10)
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)
        if viz:
            viz.close()


if __name__ == "__main__":
    main()
