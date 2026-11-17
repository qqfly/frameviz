#!/usr/bin/env python3
"""Inventory ELF symbols and direct dependencies of the whole Linux runtime."""

import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import tarfile
from tempfile import TemporaryDirectory
from zipfile import ZipFile

# Keep in step with linux_appdir_launcher.sh. A module in another subdirectory
# does not count as a provider unless the consumer searches it.
LIBRARY_PATHS = ('usr/lib/x86_64-linux-gnu', 'lib/x86_64-linux-gnu', 'usr/lib/x86_64-linux-gnu/pulseaudio')
ELF_MAGIC = b'\x7fELF'
SYSTEM_BASE = {'ld-linux-x86-64.so.2', 'libc.so.6', 'libgcc_s.so.1', 'libm.so.6',
               'libresolv.so.2', 'libstdc++.so.6'}


def inspect(binary):
    result = subprocess.run(['readelf', '-W', '-h', '-d', '-V', '-l', binary],
                            text=True, capture_output=True, check=True)
    header = result.stdout.split('Program Headers:', 1)[0]
    if not re.search(r'Machine:\s+Advanced Micro Devices X86-64', header):
        raise ValueError(f'Unexpected ELF architecture: {binary}')
    needed = re.findall(r'\(NEEDED\)\s+Shared library: \[([^\]]+)\]', result.stdout)
    needs = result.stdout.partition('Version needs section')[2]
    versions = re.findall(r'Name: ((?:GLIBC|GLIBCXX|CXXABI)_[\w.]+)', needs)
    interpreter = re.search(r'Requesting program interpreter: ([^\]]+)', result.stdout)
    paths = dict(re.findall(r'\((RPATH|RUNPATH)\)\s+[^\[]*\[([^\]]*)\]', result.stdout))
    soname = re.search(r'\(SONAME\)\s+Library soname: \[([^\]]+)\]', result.stdout)
    return {'needed': sorted(set(needed)), 'required_versions': sorted(set(versions)),
            'interpreter': interpreter[1] if interpreter else None,
            'soname': soname[1] if soname else None, 'search_paths': paths}


def installed_dependencies(item, origin, root, library_paths):
    paths = list(library_paths)
    for value in item['search_paths'].values():
        for path in value.split(':'):
            if '$ORIGIN' in path or '${ORIGIN}' in path:
                paths.append(Path(path.replace('${ORIGIN}', str(origin)).replace('$ORIGIN', str(origin))))
    return {lib: [str(path.relative_to(root)) for directory in paths
                  if (path := (directory / lib).resolve()).is_relative_to(root) and path.is_file()]
            for lib in item['needed']}


def inventory(archive, host, other_files=None):
    with TemporaryDirectory(prefix='frameviz-abi-') as name:
        root = Path(name)
        with tarfile.open(archive) as appdir:
            appdir.extractall(root, filter='data')
        paths = sorted(path for path in root.rglob('*') if path.is_file() and not path.is_symlink())
        files = {'standalone/frameviz-server': inspect(host), **(other_files or {})}
        sources = {}
        library_paths = [root / directory for directory in LIBRARY_PATHS]
        for path in paths:
            with path.open('rb') as candidate:
                if candidate.read(4) != ELF_MAGIC:
                    continue
            relative = path.relative_to(root).as_posix()
            files[relative] = inspect(path)
            sources[relative] = installed_dependencies(files[relative], path.parent, root, library_paths)
        external = {}
        for relative, item in files.items():
            provided = sources.get(relative, {})
            item['appdir_providers'] = {lib: found for lib, found in provided.items() if found}
            for lib in item['needed']:
                if lib not in item['appdir_providers']:
                    external.setdefault(lib, []).append(relative)
    versions = {version for file in files.values() for version in file['required_versions']}
    glibc = [version for version in versions if re.fullmatch(r'GLIBC_\d+(?:\.\d+)+', version)]
    newest = max(glibc, key=lambda v: tuple(map(int, v.split('_')[1].split('.'))), default=None)
    return {'elf_count': len(files), 'highest_glibc': newest,
            'uses_glibc_private': 'GLIBC_PRIVATE' in versions,
            'external_needed': sorted(external), 'external_referrers': dict(sorted(external.items())),
            'files': files}


def wheel_inventory(wheel):
    with TemporaryDirectory(prefix='frameviz-wheel-abi-') as name, ZipFile(wheel) as bundle:
        root = Path(name)
        archive = root / 'desktop.tar.xz'
        host = root / 'frameviz-server'
        extra = {}
        for entry in bundle.infolist():
            base = Path(entry.filename).name
            with bundle.open(entry) as source:
                if base in {archive.name, host.name}:
                    with (root / base).open('xb') as target:
                        shutil.copyfileobj(source, target)
                elif source.read(4) == ELF_MAGIC:
                    temp = root / 'extra-elf'
                    with temp.open('wb') as target:
                        target.write(ELF_MAGIC)
                        shutil.copyfileobj(source, target)
                    extra[entry.filename] = inspect(temp)
        return inventory(archive, host, extra)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('desktop_or_wheel', type=Path)
    parser.add_argument('host', type=Path, nargs='?')
    parser.add_argument('output', type=Path)
    parser.add_argument('--check', action='store_true', help='Fail on new external ELF dependencies')
    args = parser.parse_args()
    if args.host is None:
        report = wheel_inventory(args.desktop_or_wheel)
    else:
        report = inventory(args.desktop_or_wheel, args.host)
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print({name: report[name] for name in report if name not in {'files', 'external_referrers'}})
    unexpected = set(report['external_needed']) - SYSTEM_BASE
    if args.check and (unexpected or report['uses_glibc_private']):
        parser.exit(1, f'Unexpected Linux ABI dependencies: {sorted(unexpected)}; '
                       f'GLIBC_PRIVATE: {report["uses_glibc_private"]}\n')


if __name__ == '__main__':
    main()
