"""Open the built Simple Slider app with temporary local credentials.

Build from the repo root: pnpm --filter simple-slider-app build
Run with the matching Python SDK and installed App/Host available.
"""
import argparse
import functools
import http.server
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
from urllib.parse import urlencode
import webbrowser

import frameviz as fv
from frameviz.discovery import read_discovery_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ui-dir", type=Path, default=Path(__file__).resolve().parents[1] / "dist")
    args = parser.parse_args()
    ui_dir = args.ui_dir.resolve()
    if not (ui_dir / "index.html").is_file():
        parser.error("Build the UI first: pnpm --filter simple-slider-app build")
    # Match the application's default business endpoint. Never reuse another backend.
    try:
        with socket.socket() as probe:
            probe.bind(("127.0.0.1", 9621))
    except OSError:
        parser.error("Port 9621 is in use; stop your own previous demo before retrying")

    class Handler(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *args):
            pass

    server = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Handler, directory=str(ui_dir)))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    viz = backend = None
    try:
        viz = fv.open(title="Vue slider application", window_mode=0)
        info = read_discovery_file()
        if not info or not info.get("token") or not info.get("port"):
            raise RuntimeError("No local Host discovery record")
        business_token = secrets.token_urlsafe(32)
        env = dict(os.environ, FRAMEVIZ_BUSINESS_TOKEN=business_token,
                   SIMPLE_SLIDER_WS_HOST="127.0.0.1", SIMPLE_SLIDER_WS_PORT="9621")
        backend = subprocess.Popen([sys.executable, "-u", str(Path(__file__).with_name("backend_simple_slider.py"))], env=env)
        url = f"http://127.0.0.1:{server.server_port}/?" + urlencode({"view_id": viz.view_id, "ws_port": info["port"]})
        url += "#" + urlencode({"token": info["token"], "business_token": business_token})
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
