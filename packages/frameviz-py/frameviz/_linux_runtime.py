"""Prepare a wheel's Linux AppDir once in the user's runtime cache."""

import errno
import hashlib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import tarfile
from tempfile import TemporaryDirectory


def _digest(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unpack(archive, root):
    # The AppDir needs relative symlinks for the dynamic loader and GTK data.
    # Extract only those, directories and regular files under the fresh root.
    with tarfile.open(archive, mode="r|xz") as entries:
        for member in entries:
            relative = PurePosixPath(member.name)
            target = root.joinpath(*relative.parts)
            if relative.is_absolute() or ".." in relative.parts or not target.resolve().is_relative_to(root):
                raise ValueError(f"Unsafe bundled runtime entry: {member.name}")
            if member.isdir():
                target.mkdir(parents=True, exist_ok=True)
                continue
            target.parent.mkdir(parents=True, exist_ok=True)
            if member.issym():
                link = Path(member.linkname)
                if link.is_absolute() or not (target.parent / link).resolve().is_relative_to(root):
                    raise ValueError(f"Unsafe bundled runtime link: {member.name}")
                target.symlink_to(link)
            elif member.isfile():
                with entries.extractfile(member) as source, target.open("xb") as destination:
                    shutil.copyfileobj(source, destination)
                target.chmod(member.mode & 0o755)
            else:
                raise ValueError(f"Unsupported bundled runtime entry: {member.name}")


def prepare_desktop_runtime(directory):
    archive = directory / "desktop.tar.xz"
    if not archive.exists():
        return None
    try:
        checksum = (directory / "desktop.sha256").read_text(encoding="ascii").strip()
        if not re.fullmatch("[a-f0-9]{64}", checksum):
            raise ValueError("invalid packaged runtime checksum")
        configured = os.environ.get("XDG_CACHE_HOME")
        cache = (Path(configured).expanduser() if configured else Path.home() / ".cache") / "frameviz/runtimes"
        cache.mkdir(mode=0o700, exist_ok=True, parents=True)
        install = cache / checksum
        launcher = install / "bin/frameviz"
        if launcher.is_file() and os.access(launcher, os.X_OK):
            return launcher
        if _digest(archive) != checksum:
            raise ValueError("bundled runtime checksum mismatch")
        with TemporaryDirectory(dir=cache) as temp:
            target = Path(temp).resolve()
            _unpack(archive, target)
            if not (target / "bin/frameviz").is_file() or not os.access(target / "bin/frameviz", os.X_OK):
                raise ValueError("bundled desktop launcher is missing")
            try:
                target.rename(install)
            except OSError as error:
                if error.errno not in (errno.EEXIST, errno.ENOTEMPTY) or not os.access(launcher, os.X_OK):
                    raise
        return launcher
    except (OSError, ValueError, tarfile.TarError) as error:
        raise RuntimeError(f"Cannot prepare the bundled FrameViz desktop runtime: {error}") from error
