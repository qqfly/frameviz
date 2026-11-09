"""README media must survive source export, not just a Git checkout."""
import hashlib
import importlib.util
import json
from pathlib import Path, PurePosixPath
import re
import sys

ROOT = Path(__file__).resolve().parents[2]


def test_readme_media_survive_source_export(tmp_path):
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        from update_source_manifest import allowed
        refs = set()
        for name in ("README.md", "README.zh-CN.md"):
            refs.update(re.findall(r"!\[[^\]]*\]\((docs/media/[^)]+)\)", (ROOT / name).read_text()))
        assert refs, "README must contain its local developer media"
        for rel in refs:
            assert allowed(PurePosixPath(rel)), f"Source export excludes README media: {rel}"
        spec = importlib.util.spec_from_file_location("media_exporter", ROOT / "scripts/release/export_source.py")
        exporter = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(exporter)
        target = tmp_path / "source"
        exporter.export(target)
        manifest = json.loads((target / "source-manifest.json").read_text())["files"]
        for rel in refs:
            assert manifest[rel] == hashlib.sha256((target / rel).read_bytes()).hexdigest()
    finally:
        sys.path.remove(str(ROOT / "scripts"))
