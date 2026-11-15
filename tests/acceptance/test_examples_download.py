"""Download the actual examples release archive from a loopback asset server."""

from functools import partial
from hashlib import sha256
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import subprocess
import sys
from threading import Thread

import pytest

from frameviz._examples import download_examples


ROOT = Path(__file__).resolve().parents[2]


def test_versioned_download_verifies_archive_and_preserves_existing_files(tmp_path):
    version = json.loads((ROOT / "version.json").read_text())["protocol_version"]
    assets = tmp_path / "assets"
    assets.mkdir()
    name = f"FrameViz-{version}-examples.zip"
    archive = assets / name
    subprocess.run([sys.executable, str(ROOT / "scripts/release/build_examples_zip.py"), str(archive)],
                   check=True)
    checksums = assets / "SHA256SUMS"
    checksums.write_text(f"{sha256(archive.read_bytes()).hexdigest()}  {name}\n")
    handler = partial(SimpleHTTPRequestHandler, directory=assets)
    with ThreadingHTTPServer(("127.0.0.1", 0), handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            target = tmp_path / "Examples with spaces"
            assert download_examples(version, target, base) == target
            assert (target / "data/models/pointcloud/synthetic_cloud.pcd").is_file()
            assert (target / "examples/python/01_basic_primitives/hello_world.py").is_file()
            assert (target / "NOTICE").is_file()
            readme = target / "README.md"
            readme.write_text("Local edits")
            with pytest.raises(FileExistsError, match="Choose a new directory"):
                download_examples(version, target, base)
            assert readme.read_text() == "Local edits"
            checksums.write_text(f"{'0' * 64}  {name}\n")
            corrupt_target = tmp_path / "Corrupt examples"
            with pytest.raises(ValueError, match="Download checksum mismatch"):
                download_examples(version, corrupt_target, base)
            assert not corrupt_target.exists()
            checksums.unlink()
            with pytest.raises(ValueError, match="obtain the matching ZIP"):
                download_examples(version, corrupt_target, base)
        finally:
            server.shutdown()
            thread.join(timeout=5)
