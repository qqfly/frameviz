"""Serve a small closed STL. Pass --run followed by a program to launch it with the URL."""

import argparse
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import struct
import subprocess
from threading import Event, Thread


def sample_stl():
    # Closed square-based pyramid with outward-facing triangle winding.
    vertices = [(-0.45, -0.45, 0), (0.45, -0.45, 0), (0.45, 0.45, 0),
                (-0.45, 0.45, 0), (0, 0, 0.8)]
    triangles = [(0, 2, 1), (0, 3, 2), (0, 1, 4), (1, 2, 4), (2, 3, 4), (3, 0, 4)]
    records = []
    for face in triangles:
        a, b, c = (vertices[i] for i in face)
        u, v = [b[i] - a[i] for i in range(3)], [c[i] - a[i] for i in range(3)]
        normal = [u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2],
                  u[0] * v[1] - u[1] * v[0]]
        length = sum(x * x for x in normal) ** 0.5
        records.append(struct.pack("<12fH", *(x / length for x in normal), *a, *b, *c, 0))
    return bytes(80) + struct.pack("<I", len(triangles)) + b"".join(records)


class SampleMeshHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/model.stl":
            self.send_error(404)
            return
        content = sample_stl()
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Type", "model/stl")
        self.send_header("Content-Length", str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def log_message(self, *args):
        pass


@contextmanager
def sample_mesh_url(port=0):
    with ThreadingHTTPServer(("127.0.0.1", port), SampleMeshHandler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}/model.stl"
        finally:
            server.shutdown()
            thread.join()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--run", nargs=argparse.REMAINDER, help="Command that accepts the sample URL")
    args = parser.parse_args()
    if args.run == []:
        parser.error("--run requires a program")
    with sample_mesh_url(args.port) as url:
        if args.run:
            return subprocess.call([*args.run, url])
        print(url, flush=True)
        try:
            Event().wait()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
