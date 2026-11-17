"""Safe unpack and reuse of a small Linux runtime fixture."""

from hashlib import sha256
import io
import tarfile

import pytest

from frameviz._linux_runtime import prepare_desktop_runtime


def _runtime(directory, link):
    archive = directory / "desktop.tar.xz"
    with tarfile.open(archive, "w:xz") as entries:
        launcher = tarfile.TarInfo("bin/frameviz")
        content = b"#!/bin/sh\nexit 0\n"
        launcher.size = len(content)
        launcher.mode = 0o755
        entries.addfile(launcher, io.BytesIO(content))
        alias = tarfile.TarInfo("bin/alias")
        alias.type = tarfile.SYMTYPE
        alias.linkname = link
        entries.addfile(alias)
    (directory / "desktop.sha256").write_text(sha256(archive.read_bytes()).hexdigest() + "\n")


def test_runtime_cache_is_reused(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "Empty cache"))
    _runtime(tmp_path, "frameviz")
    launcher = prepare_desktop_runtime(tmp_path)
    assert launcher.is_file()
    assert (launcher.parent / "alias").samefile(launcher)
    inode = launcher.stat().st_ino
    reused = prepare_desktop_runtime(tmp_path)
    assert reused == launcher and reused.stat().st_ino == inode


def test_runtime_rejects_link_escape(tmp_path, monkeypatch):
    cache = tmp_path / "cache"
    monkeypatch.setenv("XDG_CACHE_HOME", str(cache))
    _runtime(tmp_path, "../../escape")
    with pytest.raises(RuntimeError, match="Unsafe bundled runtime link"):
        prepare_desktop_runtime(tmp_path)
    assert not list((cache / "frameviz/runtimes").iterdir())
