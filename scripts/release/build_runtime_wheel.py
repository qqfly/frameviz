#!/usr/bin/env python3
"""Add a colocated native runtime to the prebuilt FrameViz SDK wheel."""

import argparse
from email.parser import Parser
import json
import os
from pathlib import Path
import plistlib
import re
import stat
import struct
import subprocess
import tarfile
from tempfile import TemporaryDirectory

from packaging.utils import parse_wheel_filename
from packaging.version import Version
from wheel.wheelfile import WheelFile

from runtime_metadata import build_info, check_pair, file_hash, sdk_protocol, sha256


def mac_runtime(app, revision):
    if app.name != 'FrameViz.app':
        raise ValueError('Expected the packaged FrameViz.app')
    with (app / 'Contents/Info.plist').open('rb') as stream:
        info = plistlib.load(stream)
    executable = info.get('CFBundleExecutable')
    if info.get('CFBundleIdentifier') != 'dev.qqfly.frameviz.viewer' or executable != 'frameviz':
        raise ValueError('The App must declare the FrameViz bundle identifier and executable')
    binary = app / 'Contents/MacOS' / executable
    if not os.access(binary, os.X_OK):
        raise ValueError('Expected an executable FrameViz App binary')
    with binary.open('rb') as stream:
        if stream.read(8) != struct.pack('<II', 0xfeedfacf, 0x0100000c):
            raise ValueError('Expected an Apple Silicon Mach-O executable')
    if info.get('LSMinimumSystemVersion') != '11.0':
        raise ValueError('Expected macOS 11.0 as the App deployment baseline')
    # Keep the bundle's paths and contents intact so codesign can verify the
    # App after pip installation. Wheel installers do not preserve symlinks.
    files = {}
    for path in sorted(app.rglob('*')):
        if path.is_symlink() or not (path.is_dir() or path.is_file()):
            raise ValueError(f'The App has a wheel-incompatible file: {path}')
        if path.is_file():
            files[f'FrameViz.app/{path.relative_to(app).as_posix()}'] = path
    desktop = build_info(binary, 'desktop')
    desktop_release = Version(desktop['release'])
    if Version(info['CFBundleShortVersionString']) not in {desktop_release, Version(desktop_release.base_version)}:
        raise ValueError('The App bundle version does not match its desktop executable')
    digest = file_hash(binary)
    receipt = app.parent / 'app-build.json'
    if receipt.exists():
        source = json.loads(receipt.read_text())
        if source['source_revision'] != revision or source['files']['FrameViz.app/Contents/MacOS/frameviz'] != digest:
            raise ValueError('The Apple App does not match its build receipt')
    return 'macosx_11_0_arm64', files, [dict(desktop, sha256=digest)]


def linux_runtime(desktop_archive, host, revision):
    if desktop_archive.suffixes[-2:] != ['.tar', '.xz']:
        raise ValueError('Expected a .tar.xz desktop runtime archive')
    with host.open('rb') as stream:
        header = stream.read(20)
    if header[:6] != b'\x7fELF\x02\x01' or header[18:20] != b'\x3e\x00':
        raise ValueError('Expected an x86-64 Linux standalone Host')
    if not os.access(host, os.X_OK):
        raise ValueError('Expected an executable standalone Host')
    manifest = None
    desktop_hash = None
    launcher_hash = None
    with tarfile.open(desktop_archive, mode='r|xz') as archive:
        for member in archive:
            name = member.name.removeprefix('./')
            if name == 'runtime-build.json':
                if manifest is not None or not member.isfile() or member.size > 1024 * 1024:
                    raise ValueError('Invalid runtime-build.json in the Linux AppDir')
                manifest = json.load(archive.extractfile(member))
            elif name == 'bin/frameviz-real':
                if desktop_hash is not None or not member.isfile():
                    raise ValueError('Invalid desktop executable in the Linux AppDir')
                desktop_hash = sha256(archive.extractfile(member))
            elif name == 'bin/frameviz':
                if launcher_hash is not None or not member.isfile():
                    raise ValueError('Invalid launcher in the Linux AppDir')
                launcher_hash = sha256(archive.extractfile(member))
    if not manifest or not desktop_hash or not launcher_hash:
        raise ValueError('The Linux AppDir must contain the launcher, desktop executable and runtime-build.json')
    if manifest['source_revision'] != revision or manifest['launcher_sha256'] != launcher_hash:
        raise ValueError('The Linux AppDir does not match the candidate revision or launcher checksum')
    desktop, standalone = manifest['desktop'], manifest['standalone']
    if desktop['role'] != 'desktop' or desktop['sha256'] != desktop_hash:
        raise ValueError('The Linux AppDir desktop executable does not match its build manifest')
    if standalone['role'] != 'standalone' or standalone['sha256'] != file_hash(host):
        raise ValueError('The standalone Host does not match the Linux AppDir build manifest')
    return 'linux_x86_64', {'desktop.tar.xz': desktop_archive, 'frameviz-server': host}, [desktop, standalone]


def build_wheel(sdk, output, platform, runtime, native, revision):
    if not re.fullmatch(r'[a-f0-9]{40}', revision):
        raise ValueError('Use a full FrameViz source commit SHA')
    with WheelFile(sdk) as source:
        if not sdk.name.startswith('frameviz-') or not sdk.name.endswith('-py3-none-any.whl'):
            raise ValueError('Expected the universal FrameViz SDK wheel')
        dist_info = source.dist_info_path
        name, version, _, _ = parse_wheel_filename(sdk.name)
        sdk_meta = Parser().parsestr(source.read(f'{dist_info}/METADATA').decode('utf-8'))
        if name != 'frameviz' or sdk_meta['Name'].lower() != 'frameviz' or Version(sdk_meta['Version']) != version:
            raise ValueError('SDK metadata does not match its wheel filename')
        wire = sdk_protocol(source.read('frameviz/client.py').decode('utf-8'))
        for item in native:
            check_pair(str(version), wire, item)
        provenance = {'source_revision': revision, 'platform': platform,
                      'sdk_release': str(version), 'sdk_protocol': wire,
                      'sdk_wheel_sha256': file_hash(sdk), 'runtimes': native}

        distribution = sdk.name.removesuffix('-py3-none-any.whl')
        destination = output / f'{distribution}-py3-none-{platform}.whl'
        metadata = Parser().parsestr(source.read(f'{dist_info}/WHEEL').decode('utf-8'))
        if metadata.get_all('Tag') != ['py3-none-any']:
            raise ValueError('Unexpected SDK wheel tags')
        metadata.replace_header('Root-Is-Purelib', 'false')
        metadata.replace_header('Tag', f'py3-none-{platform}')
        if any(name.startswith('frameviz/_binaries/') for name in source.namelist()):
            raise ValueError('The source wheel already contains a runtime')
        for path in runtime.values():
            if not stat.S_ISREG(path.lstat().st_mode):
                raise ValueError(f'Expected a regular runtime file: {path}')
        output.mkdir(parents=True, exist_ok=True)
        with TemporaryDirectory(dir=output) as directory:
            staged = Path(directory) / destination.name
            replaced = {f'{dist_info}/WHEEL', source.record_path,
                        f'{source.record_path}.jws', f'{source.record_path}.p7s'}
            with WheelFile(staged, 'w') as wheel:
                for entry in source.infolist():
                    if entry.filename not in replaced:
                        wheel.writestr(entry, source.read(entry))
                wheel.writestr(f'{dist_info}/WHEEL', metadata.as_bytes())
                for name, path in runtime.items():
                    wheel.write(path, f'frameviz/_binaries/{name}')
                wheel.writestr('frameviz/_binaries/build.json', json.dumps(provenance, indent=2) + '\n')
                if 'desktop.tar.xz' in runtime:
                    wheel.writestr('frameviz/_binaries/desktop.sha256',
                                   file_hash(runtime['desktop.tar.xz']) + '\n')
            destination.hardlink_to(staged)
    return destination


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('sdk', type=Path)
    parser.add_argument('output', type=Path)
    inputs = parser.add_mutually_exclusive_group(required=True)
    inputs.add_argument('--mac-app', type=Path)
    inputs.add_argument('--linux-desktop', type=Path, help='Local Linux candidate AppDir archive')
    parser.add_argument('--linux-host', type=Path)
    parser.add_argument('--source-revision', required=True, help='Source revision for the SDK build receipt')
    args = parser.parse_args()
    try:
        if args.mac_app:
            if args.linux_host:
                parser.error('--linux-host requires --linux-desktop')
            platform, files, native = mac_runtime(args.mac_app, args.source_revision)
        elif args.linux_host:
            platform, files, native = linux_runtime(args.linux_desktop, args.linux_host, args.source_revision)
        else:
            parser.error('--linux-desktop requires --linux-host')
        print(build_wheel(args.sdk, args.output, platform, files, native, args.source_revision))
    except (OSError, KeyError, TypeError, ValueError, tarfile.TarError, subprocess.SubprocessError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
