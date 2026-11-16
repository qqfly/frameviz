#!/usr/bin/env python3
"""Collect the exact Ubuntu source packages indexed by a FrameViz AppDir."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import lzma
from pathlib import Path, PurePosixPath
import shutil
import subprocess
from tempfile import NamedTemporaryFile
from urllib.request import urlopen


ARCHIVE = "https://archive.ubuntu.com/ubuntu"


def digest(path):
    checksum = sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            checksum.update(block)
    return checksum.hexdigest()


def records(lines):
    record, field = {}, None
    for line in lines:
        if not line.strip():
            if record:
                yield record
            record, field = {}, None
        elif line.startswith((" ", "\t")):
            record[field] += "\n" + line.strip()
        else:
            field, value = line.split(":", 1)
            record[field] = value.strip()
    if record:
        yield record


def checksum_entries(value):
    return {name: (checksum, int(size))
            for line in value.splitlines() if line
            for checksum, size, name in (line.split(),)}


def verified_download(urls, target, expected=None):
    def valid(path):
        return expected is None or (path.stat().st_size == expected[1] and digest(path) == expected[0])

    if target.exists() and valid(target):
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    errors = []
    for url in urls:
        with NamedTemporaryFile(dir=target.parent, delete=False) as stream:
            scratch = Path(stream.name)
            try:
                with urlopen(url, timeout=75) as response:
                    shutil.copyfileobj(response, stream)
                stream.close()
                if not valid(scratch):
                    raise ValueError("size or SHA-256 mismatch")
                scratch.replace(target)
                return
            except (OSError, ValueError) as error:
                errors.append(f"{url}: {error}")
            finally:
                scratch.unlink(missing_ok=True)
    raise ValueError("\n".join(errors))


def source_records(snapshot, suite, destination, keyring):
    base = f"{snapshot}/dists/{suite}"
    release = destination / suite / "InRelease"
    verified_download([f"{base}/InRelease"], release)
    signed_text = subprocess.run(
        ["gpgv", "--keyring", str(keyring), "--output", "-", str(release)],
        capture_output=True, check=True, text=True,
    ).stdout
    (release.parent / "Release.verified").write_text(signed_text)
    header, = records(signed_text.splitlines())
    if header["Suite"] != suite:
        raise ValueError(f"Signed release does not match suite {suite}")
    checksums = checksum_entries(header["SHA256"])
    for component in ("main", "universe"):
        name = f"{component}/source/Sources.xz"
        compressed = release.parent / name
        verified_download([f"{base}/{name}"], compressed, checksums[name])
        with lzma.open(compressed, "rt", encoding="utf-8") as stream:
            for entry in records(stream):
                yield entry, f"{suite}/{name}"


def collect(index, destination, keyring, workers):
    snapshot, suite = index["snapshot"], index["suite"]
    wanted = {(row["source"], row["version"]): row for row in index["sources"]}
    selected = {}
    for pocket in (suite, f"{suite}-updates", f"{suite}-security"):
        for entry, index_path in source_records(snapshot, pocket, destination / "apt", keyring):
            key = (entry["Package"], entry["Version"])
            if key not in wanted:
                continue
            directory = PurePosixPath(entry["Directory"])
            files = checksum_entries(entry["Checksums-Sha256"])
            if directory.parts[0] != "pool" or ".." in directory.parts:
                raise ValueError(f"Invalid pool directory: {directory}")
            if any(name != PurePosixPath(name).name or name in {".", ".."} for name in files):
                raise ValueError(f"Invalid source filename in {key}")
            if key in selected and selected[key][1] != files:
                raise ValueError(f"Conflicting signed source checksums for {key}")
            selected[key] = (directory, files, index_path)

    missing = wanted.keys() - selected.keys()
    if missing:
        raise ValueError(f"Versions missing from the signed snapshot: {sorted(missing)}")

    downloads, entries = {}, []
    for key, (directory, files, index_path) in sorted(selected.items()):
        pinned = wanted[key].get("files_sha256")
        if pinned and (pinned != {name: value[0] for name, value in files.items()}
                       or directory.as_posix() != wanted[key]["pool_directory"]):
            raise ValueError(f"Signed index disagrees with the source lock for {key}")
        package_files = []
        for name, (checksum, size) in sorted(files.items()):
            path = (directory / name).as_posix()
            existing = downloads.setdefault(path, (checksum, size))
            if existing != (checksum, size):
                raise ValueError(f"Conflicting checksums for {path}")
            package_files.append({"path": path, "sha256": checksum, "bytes": size})
        entries.append({"source": key[0], "version": key[1], "signed_index": index_path,
                        "files": package_files})

    def fetch(item):
        path, expected = item
        verified_download([f"{ARCHIVE}/{path}", f"{snapshot}/{path}"], destination / path, expected)
        return path

    size = sum(size for _, size in downloads.values())
    print(f"Resolved {len(entries)} source packages, {len(downloads)} files, {size} bytes", flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for number, path in enumerate(pool.map(fetch, downloads.items()), start=1):
            print(f"{number}/{len(downloads)} {path}", flush=True)

    manifest = {"snapshot": snapshot, "suite": suite, "source_bytes": size, "sources": entries}
    (destination / "source-manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
    checksums = "".join(f"{digest}  {path}\n" for path, (digest, _) in sorted(downloads.items()))
    (destination / "SHA256SUMS").write_text(checksums)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--keyring", type=Path, required=True, help="Trusted Ubuntu archive keyring")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    collect(json.loads(args.index.read_text()), args.destination, args.keyring.resolve(strict=True), args.workers)


if __name__ == "__main__":
    main()
