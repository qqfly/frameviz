"""Fetch and verify the existing release examples ZIP."""

import hashlib
import json
from pathlib import Path, PurePosixPath
import re
import shutil
import stat
from tempfile import TemporaryDirectory
from urllib.error import HTTPError
from urllib.parse import quote, urlsplit
from urllib.request import urlopen
from zipfile import BadZipFile, ZipFile


def _sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _unpack_examples(archive, stage, sdk_version):
    with ZipFile(archive) as entries:
        manifest = json.loads(entries.read("source-manifest.json"))
        files = manifest["files"]
        if manifest["project"] != "FrameViz" or manifest["version"] != sdk_version.split("+", 1)[0]:
            raise ValueError("Examples are for a different FrameViz version")
        names = entries.namelist()
        if len(names) != len(set(names)) or set(names) != {*files, "source-manifest.json"}:
            raise ValueError("Examples ZIP contents differ from its manifest")
        for member in entries.infolist():
            name = member.filename
            path = PurePosixPath(name)
            if (path.is_absolute() or not path.parts or ".." in path.parts
                    or "\\" in name or ":" in name or member.is_dir()
                    or stat.S_ISLNK(member.external_attr >> 16)):
                raise ValueError(f"Unsafe examples ZIP entry: {name}")
            destination = stage.joinpath(*path.parts)
            destination.parent.mkdir(parents=True, exist_ok=True)
            with entries.open(member) as source, destination.open("xb") as target:
                shutil.copyfileobj(source, target)
            if name in files and _sha256(destination) != files[name]:
                raise ValueError(f"Examples ZIP checksum mismatch: {name}")


def download_examples(sdk_version, output, asset_base=None):
    name = f"FrameViz-{sdk_version}-examples.zip"
    default_base = f"https://github.com/qqfly/frameviz/releases/download/v{quote(sdk_version, safe='')}"
    base = (asset_base or default_base).rstrip("/")
    endpoint = urlsplit(base)
    if endpoint.scheme != "https" and not (
        endpoint.scheme == "http" and endpoint.hostname in {"127.0.0.1", "::1", "localhost"}
    ):
        raise ValueError("Examples assets require HTTPS or a loopback HTTP endpoint")
    output = output.expanduser().absolute()
    if output.exists() or output.is_symlink():
        raise FileExistsError(f"Examples output already exists: {output}. Choose a new directory.")

    with TemporaryDirectory(prefix="frameviz-examples-") as temp:
        temp = Path(temp)
        archive, stage = temp / name, temp / "contents"
        try:
            with urlopen(f"{base}/SHA256SUMS", timeout=30) as response:
                checks = re.findall(
                    rf"(?im)^([0-9a-f]{{64}})[ \t]+\*?(?:\./)?{re.escape(name)}\r?$",
                    response.read(1024 * 1024).decode("utf-8"),
                )
            if len(checks) != 1:
                raise ValueError(f"SHA256SUMS does not contain one checksum for {name}")
            with urlopen(f"{base}/{quote(name)}", timeout=30) as response, archive.open("xb") as target:
                shutil.copyfileobj(response, target)
        except HTTPError as error:
            if error.code == 404:
                raise ValueError(
                    f"Examples for FrameViz {sdk_version} are unavailable at {base}. "
                    "For an unpublished candidate, obtain the matching ZIP from its maintainer."
                ) from error
            raise
        if _sha256(archive) != checks[0].lower():
            raise ValueError(f"Download checksum mismatch for {name}")
        try:
            _unpack_examples(archive, stage, sdk_version)
        except (BadZipFile, KeyError, TypeError) as error:
            raise ValueError("Examples ZIP manifest is missing or malformed") from error
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(stage, output)
    return output
