"""Populate the Vue example and open it using the current local Host credential."""
import argparse
import webbrowser
from urllib.parse import urlencode, urlsplit

import frameviz as fv
from frameviz.discovery import read_discovery_file


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--page", default="http://127.0.0.1:8000/embedded_viewer.html")
    args = parser.parse_args()
    page = urlsplit(args.page)
    if (page.scheme != "http" or page.hostname not in {"127.0.0.1", "localhost", "::1"}
            or page.query or page.fragment or page.username or page.password):
        parser.error("--page must be a loopback HTTP URL without credentials, query or fragment")
    viz = fv.open(title="Vue embedded scene", window_mode=0)
    try:
        viz.set_view_config(show_axes=False, show_grid=False, background=(1, 1, 1))
        viz.add_box(size=(0.95, 0.75, 0.9), pos=(-0.7, 0, 0.45), color=(0.2, 0.5, 0.87))
        viz.add_sphere(radius=0.38, pos=(0.85, 0, 0.38), color=(0.95, 0.62, 0.18))
        viz.set_camera_pose((4, -6, 4), (0, 0, 0.4))
        info = read_discovery_file()
        if not info or not info.get("token") or not info.get("port"):
            raise RuntimeError("No matching local Host discovery record")
        url = args.page + "?" + urlencode({"view_id": viz.view_id, "ws_port": info["port"]})
        url += "#" + urlencode({"token": info["token"]})
        webbrowser.open(url)
        print("Opened the local Vue page. Keep its session URL private.")
        input("Try Hide viewer / Show viewer. Enter to close the scene... ")
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        viz.close()


if __name__ == "__main__":
    main()
