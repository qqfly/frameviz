#!/usr/bin/env python3
"""Assemble the Jammy x86-64 FrameViz AppDir from a preview .deb and locked Ubuntu packages."""

import argparse
from concurrent.futures import ThreadPoolExecutor
import platform
from pathlib import Path
import json
import re
import shutil
import subprocess
import tempfile
from urllib.request import urlopen

from runtime_metadata import build_info, check_pair, file_hash

HERE = Path(__file__).resolve().parent
WEBKIT = 'usr/lib/x86_64-linux-gnu/webkit2gtk-4.1'
SYSTEM_GLIBC = {'libanl', 'libBrokenLocale', 'libc', 'libdl', 'libm', 'libmvec', 'libnss_compat',
                'libnss_dns', 'libnss_files', 'libpthread', 'libresolv', 'librt', 'libthread_db', 'libutil'}


def command(*args, **kwargs):
    return subprocess.run(args, check=True, text=True, **kwargs)


def ubuntu_packages(lock, cache):
    cache.mkdir(parents=True, exist_ok=True)
    lines = [line for line in lock.read_text().splitlines() if line and not line.startswith('#')]

    def obtain(line):
        name, version, source, digest, filename = line.split('\t')
        target = cache / Path(filename).name
        if not target.exists():
            # The pool mirror and snapshot are interchangeable only when the digest agrees.
            bases = ('https://archive.ubuntu.com/ubuntu', 'https://snapshot.ubuntu.com/ubuntu/20261115T150000Z')
            with tempfile.TemporaryDirectory(dir=cache) as work:
                partial = Path(work) / target.name
                for base in bases:
                    try:
                        with urlopen(f'{base}/{filename}', timeout=45) as response, partial.open('wb') as out:
                            shutil.copyfileobj(response, out)
                        if file_hash(partial) != digest:
                            raise ValueError(f'Ubuntu download does not match lock: {name}')
                        partial.replace(target)
                        break
                    except OSError:
                        if base == bases[-1]:
                            raise
        if file_hash(target) != digest:
            raise ValueError(f'Cached Ubuntu package checksum mismatch: {target}')
        actual = command('dpkg-deb', '-f', target, 'Package', 'Version', capture_output=True).stdout
        if actual.splitlines() != [f'Package: {name}', f'Version: {version}']:
            raise ValueError(f'Cached Ubuntu package metadata mismatch: {target}')
        return name, version, source, target

    with ThreadPoolExecutor(max_workers=8) as pool:
        return list(pool.map(obtain, lines))


def copy_payload(sysroot, root):
    for name in ('usr/lib/x86_64-linux-gnu', 'lib/x86_64-linux-gnu', 'usr/share/glib-2.0',
                 'usr/share/glvnd', 'usr/share/icons', 'usr/share/mime', 'usr/share/fonts'):
        source = sysroot / name
        if source.is_dir():
            shutil.copytree(source, root / name, symlinks=True)
    for name in ('bwrap', 'xdg-dbus-proxy', 'xdg-open'):
        shutil.copy2(sysroot / 'usr/bin' / name, root / 'bin' / name)
    for directory in (root / 'usr/lib', root / 'lib'):
        if directory.exists():
            for path in directory.rglob('*'):
                if path.is_dir() and not path.is_symlink():
                    continue
                if (path.name.endswith(('.a', '.la', '.pc')) or path.name == 'MiniBrowser'
                        or path.name.split('.so', 1)[0] in SYSTEM_GLIBC
                        or path.name.startswith('ld-linux')):
                    path.unlink()
    # Multiple driver entry names in Jammy's Mesa package share one ELF payload.
    dri = root / 'usr/lib/x86_64-linux-gnu/dri'
    recorded = {}
    for driver in sorted(dri.glob('*_dri.so')):
        if driver.is_symlink():
            continue
        digest = file_hash(driver)
        if digest in recorded:
            driver.unlink()
            driver.symlink_to(recorded[digest])
        else:
            recorded[digest] = driver.name


def relocate_webkit(root):
    pattern = root / 'usr/lib/x86_64-linux-gnu'
    libraries = [path for path in pattern.glob('libwebkit2gtk-4.1.so.*') if not path.is_symlink()]
    if len(libraries) != 1:
        raise ValueError('Expected exactly one real WebKitGTK library in the locked AppDir')
    path = libraries[0]
    original = file_hash(path)
    absolute = ('/' + WEBKIT).encode('ascii')
    relative = (WEBKIT + '/').encode('ascii')
    data = path.read_bytes()
    if len(relative) != len(absolute) or data.count(absolute) != 2:
        raise ValueError('WebKitGTK helper paths changed. Review relocation for this package.')
    path.write_bytes(data.replace(absolute, relative))
    return {'file': str(path.relative_to(root)), 'before_sha256': original,
            'after_sha256': file_hash(path), 'from': absolute.decode(), 'to': relative.decode()}


def notices(sysroot, root, packages):
    to = root / 'usr/share/doc'
    for name, _, _, _ in packages:
        source = sysroot / 'usr/share/doc' / name
        copyright_file = source / 'copyright'
        if not copyright_file.is_file():
            raise ValueError(f'Missing Ubuntu copyright notice: {name}')
        (to / name).mkdir(parents=True, exist_ok=True)
        shutil.copy2(copyright_file, to / name / 'copyright')
    # Include project and Rust dependency notices shipped with the preview .deb.
    shutil.copytree(sysroot / 'usr/share/doc/frameviz', to / 'frameviz', dirs_exist_ok=True)


def build(args):
    os_info = Path('/etc/os-release').read_text()
    if platform.machine() != 'x86_64' or 'ID=ubuntu' not in os_info or 'VERSION_ID="22.04"' not in os_info:
        raise ValueError('Run the AppDir builder on Ubuntu 22.04 x86-64')
    if file_hash(args.preview_deb) != args.preview_sha256:
        raise ValueError('FrameViz preview .deb checksum does not match')
    if not re.fullmatch(r'[a-f0-9]{40}', args.source_revision):
        raise ValueError('Use a full FrameViz source commit SHA')
    output = args.output.resolve()
    if output.exists():
        raise ValueError('Choose a new AppDir output directory')
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=output.parent) as directory:
        work = Path(directory)
        sysroot, root, result = (work / sub for sub in ('sysroot', 'appdir', 'result'))
        (root / 'bin').mkdir(parents=True)
        result.mkdir()
        packages = list(ubuntu_packages(args.lock, args.cache))
        for _, _, _, deb in packages:
            command('dpkg-deb', '-x', deb, sysroot)
        command('dpkg-deb', '-x', args.preview_deb, sysroot)
        copy_payload(sysroot, root)
        notices(sysroot, root, packages)
        relocation = relocate_webkit(root)
        desktop_binary = root / 'bin/frameviz-real'
        standalone = result / 'frameviz-server'
        shutil.copy2(sysroot / 'usr/bin/frameviz', desktop_binary)
        shutil.copy2(sysroot / 'usr/bin/frameviz-server', standalone)
        command('strip', '--strip-unneeded', desktop_binary, standalone)
        launcher = root / 'bin/frameviz'
        shutil.copy2(HERE / 'linux_appdir_launcher.sh', launcher)
        launcher.chmod(0o755)
        # Use the Jammy builder's compiler for the schemas, never the user's system.
        command('glib-compile-schemas', root / 'usr/share/glib-2.0/schemas')
        desktop_info = build_info(launcher, 'desktop')
        server_info = build_info(standalone, 'standalone')
        check_pair(desktop_info['release'], desktop_info['protocol'], server_info)
        manifest = {'source_revision': args.source_revision, 'preview_deb_sha256': args.preview_sha256,
                    'ubuntu_lock_sha256': file_hash(args.lock), 'webkit_relocation': relocation,
                    'launcher_sha256': file_hash(launcher),
                    'desktop': dict(desktop_info, sha256=file_hash(desktop_binary)),
                    'standalone': dict(server_info, sha256=file_hash(standalone))}
        (root / 'runtime-build.json').write_text(json.dumps(manifest, indent=2) + '\n')
        shutil.copy2(root / 'runtime-build.json', result)
        shutil.copy2(args.lock, result / 'ubuntu-runtime-packages.txt')
        shutil.copy2(args.lock, root / 'ubuntu-runtime-packages.txt')
        command('tar', '--sort=name', '--mtime=@0', '--owner=0', '--group=0', '--numeric-owner',
                '-I', 'xz -T2 -6', '-cf', result / 'desktop.tar.xz', '-C', root, '.')
        names = ('desktop.tar.xz', 'frameviz-server', 'runtime-build.json', 'ubuntu-runtime-packages.txt')
        (result / 'SHA256SUMS').write_text(''.join(f'{file_hash(result / name)}  {name}\n' for name in names))
        result.rename(output)
    print(output)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('preview_deb', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--preview-sha256', required=True)
    parser.add_argument('--source-revision', required=True)
    parser.add_argument('--cache', type=Path, required=True, help='Directory for verified Ubuntu .deb downloads')
    parser.add_argument('--lock', type=Path, default=HERE / 'ubuntu-runtime-packages.txt')
    args = parser.parse_args()
    try:
        build(args)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        parser.error(str(error))


if __name__ == '__main__':
    main()
