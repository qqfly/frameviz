#!/usr/bin/env python3
"""Add a colocated native runtime to the prebuilt FrameViz SDK wheel."""

import argparse
from email.parser import Parser
import hashlib
import os
from pathlib import Path
import plistlib
import stat
import struct
from tempfile import TemporaryDirectory

from wheel.wheelfile import WheelFile


def mac_runtime(app):
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
    return 'macosx_11_0_arm64', files


def linux_runtime(desktop_archive, host):
    if desktop_archive.suffixes[-2:] != ['.tar', '.xz']:
        raise ValueError('Expected a .tar.xz desktop runtime archive')
    with host.open('rb') as stream:
        header = stream.read(20)
    if header[:6] != b'\x7fELF\x02\x01' or header[18:20] != b'\x3e\x00':
        raise ValueError('Expected an x86-64 Linux standalone Host')
    if not os.access(host, os.X_OK):
        raise ValueError('Expected an executable standalone Host')
    return 'linux_x86_64', {'desktop.tar.xz': desktop_archive, 'frameviz-server': host}


def build_wheel(sdk, output, platform, runtime):
    with WheelFile(sdk) as source:
        if not sdk.name.startswith('frameviz-') or not sdk.name.endswith('-py3-none-any.whl'):
            raise ValueError('Expected the universal FrameViz SDK wheel')
        dist_info = source.dist_info_path
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
                if 'desktop.tar.xz' in runtime:
                    digest = hashlib.sha256()
                    with runtime['desktop.tar.xz'].open('rb') as archive:
                        for chunk in iter(lambda: archive.read(1024 * 1024), b''):
                            digest.update(chunk)
                    wheel.writestr('frameviz/_binaries/desktop.sha256', digest.hexdigest() + '\n')
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
    args = parser.parse_args()
    if args.mac_app:
        if args.linux_host:
            parser.error('--linux-host requires --linux-desktop')
        platform, files = mac_runtime(args.mac_app)
    elif args.linux_host:
        platform, files = linux_runtime(args.linux_desktop, args.linux_host)
    else:
        parser.error('--linux-desktop requires --linux-host')
    print(build_wheel(args.sdk, args.output, platform, files))


if __name__ == '__main__':
    main()
