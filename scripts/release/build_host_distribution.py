#!/usr/bin/env python3
"""Build the pure SDK wheel and its three versioned native release assets."""

import argparse
from email.parser import Parser
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
from tempfile import TemporaryDirectory

from packaging.utils import parse_wheel_filename
from packaging.version import Version
from wheel.wheelfile import WheelFile

from build_runtime_wheel import linux_runtime, mac_runtime
from runtime_metadata import check_pair, file_hash, sdk_protocol


def _archive(path, files):
    def metadata(entry):
        entry.uid = entry.gid = entry.mtime = 0
        entry.uname = entry.gname = ''
        return entry

    with tarfile.open(path, 'w:xz') as archive:
        for name, source in sorted(files.items()):
            if not source.is_file() or source.is_symlink():
                raise ValueError(f'Expected a regular runtime file: {source}')
            archive.add(source, arcname=name, recursive=False, filter=metadata)


def build(args):
    for revision in (args.source_revision, args.mac_source_revision, args.linux_source_revision):
        if not re.fullmatch(r'[a-f0-9]{40}', revision):
            raise ValueError('Use full SHA-1 revisions for the SDK and each native input')
    standalone_notices = args.linux_host_notices
    if any(not (standalone_notices / name).is_file() for name in ('LICENSE', 'NOTICE', 'runtime-dependencies.json')):
        raise ValueError('Supply the standalone Host notices from the matching Linux preview build')
    mac_tag, app, (mac,) = mac_runtime(args.mac_app, args.mac_source_revision)
    assert mac_tag == 'macosx_11_0_arm64'
    subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', args.mac_app], check=True)
    subprocess.run(['xcrun', 'stapler', 'validate', args.mac_app], check=True)
    _, _, (desktop, standalone) = linux_runtime(args.linux_desktop, args.linux_host, args.linux_source_revision)

    name, release, _, tags = parse_wheel_filename(args.sdk.name)
    if name != 'frameviz' or {str(tag) for tag in tags} != {'py3-none-any'}:
        raise ValueError('Expected the pure FrameViz SDK wheel')
    release = str(release)
    output = args.output.resolve()
    if output.exists():
        raise ValueError('Choose a new output directory')
    output.parent.mkdir(parents=True, exist_ok=True)

    with WheelFile(args.sdk) as source, TemporaryDirectory(dir=output.parent) as temp:
        dist_info = source.dist_info_path
        metadata = Parser().parsestr(source.read(f'{dist_info}/METADATA').decode('utf-8'))
        if metadata['Name'].lower() != 'frameviz' or Version(metadata['Version']) != Version(release):
            raise ValueError('SDK metadata does not match its wheel filename')
        manifest_path = 'frameviz/runtime-assets.json'
        if any(n.startswith('frameviz/_binaries/') or n == manifest_path for n in source.namelist()):
            raise ValueError('Use an SDK wheel without binaries or a release runtime manifest')
        protocol = sdk_protocol(source.read('frameviz/client.py').decode('utf-8'))
        for info in (mac, desktop, standalone):
            check_pair(release, protocol, info)
        stage = Path(temp) / 'distribution'
        stage.mkdir()
        files = {f'notices/{p.relative_to(standalone_notices)}': p
                 for p in standalone_notices.rglob('*') if p.is_file() or p.is_symlink()}
        files['frameviz-server'] = args.linux_host
        manifest = {'release': release, 'source_revision': args.source_revision, 'assets': {}}
        for key, info, content in (
            ('macos-arm64-desktop', mac, app),
            ('linux-x86_64-desktop', desktop, None),
            ('linux-x86_64-standalone', standalone, files),
        ):
            path = stage / f'FrameViz-{release}-{key}.tar.xz'
            if content is None:
                shutil.copyfile(args.linux_desktop, path)
            else:
                _archive(path, content)
            manifest['assets'][key] = dict(info, binary_sha256=info['sha256'], sha256=file_hash(path), size=path.stat().st_size)

        encoded = json.dumps(manifest, indent=2) + '\n'
        (stage / 'runtime-assets.json').write_text(encoded, encoding='utf-8')
        with WheelFile(stage / args.sdk.name, 'w') as wheel:
            replaced = {source.record_path, f'{source.record_path}.jws', f'{source.record_path}.p7s'}
            for entry in source.infolist():
                if entry.filename not in replaced:
                    wheel.writestr(entry, source.read(entry))
            wheel.writestr(manifest_path, encoded)
        checks = {path.name: file_hash(path) for path in sorted(stage.iterdir())}
        (stage / 'SHA256SUMS').write_text(''.join(f'{digest}  {name}\n' for name, digest in checks.items()))
        stage.rename(output)
    print(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sdk', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--mac-app', type=Path, required=True)
    parser.add_argument('--mac-source-revision', required=True)
    parser.add_argument('--linux-desktop', type=Path, required=True)
    parser.add_argument('--linux-host', type=Path, required=True)
    parser.add_argument('--linux-host-notices', type=Path, required=True)
    parser.add_argument('--linux-source-revision', required=True)
    try:
        build(parser.parse_args())
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
