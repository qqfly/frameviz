"""Run the optional renderer on behalf of the C++ SDK."""

import json
from pathlib import Path
import sys
from urllib.parse import urlsplit

from ._capture import _LOOPBACK
from .client import FrameVizClient
from .viz import Viz


def main(directory):
    token = ""
    client = None
    try:
        request_path = directory / "request.json"
        request = json.loads(request_path.read_text(encoding="utf-8"))
        request_path.unlink()
        token = request["token"]
        endpoint = urlsplit(request["url"])
        if (endpoint.scheme != "ws" or endpoint.hostname not in _LOOPBACK
                or not endpoint.port or endpoint.username or endpoint.password):
            raise ValueError("Automatic capture requires a local FrameViz runtime.")
        client = FrameVizClient(request["url"], token=token, auto_events=False)
        client.connect()
        state = client.send_command("get_display_state", {"view_id": request["view"]})
        viz = Viz(client, state["scene_id"], request["view"], owns_view=False)
        output = directory / "output"
        if request["operation"] == "png":
            viz.screenshot(output, camera_view=request.get("camera_view"),
                           width=request.get("width"), height=request.get("height"))
        elif request["operation"] == "html":
            viz.export_html(output, animation=request.get("animation"))
        else:
            raise ValueError("Unknown FrameViz capture operation")
    except Exception as error:
        message = str(error)
        if token:
            message = message.replace(token, "<session credential>")
        (directory / "error.txt").write_text(message, encoding="utf-8")
        return 1
    finally:
        if client is not None:
            client.close()
    return 0


if __name__ == "__main__":
    sys.exit(main(Path(sys.argv[1])))
