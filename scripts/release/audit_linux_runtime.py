#!/usr/bin/env python3
"""Inventory ELF symbols and direct dependencies of the whole Linux runtime."""

import argparse
import json
from pathlib import Path
import re
import subprocess
import tarfile
from tempfile import TemporaryDirectory


def inspect(binary):
    result = subprocess.run(['readelf', '-W', '-h', '-d', '-V', '-l', binary],
                            text=True, capture_output=True, check=True)
    header = result.stdout.split('Program Headers:', 1)[0]
    if not re.search(r'Machine:\s+Advanced Micro Devices X86-64', header):
        raise ValueError(f'Unexpected ELF architecture: {binary}')
    needed = re.findall(r'\(NEEDED\)\s+Shared library: \[([^\]]+)\]', result.stdout)
    versions = re.findall(r'Name: ((?:GLIBC|GLIBCXX|CXXABI)_[\w.]+)', result.stdout)
    interpreter = re.search(r'Requesting program interpreter: ([^\]]+)', result.stdout)
    return {'needed': sorted(set(needed)), 'required_versions': sorted(set(versions)),
            'interpreter': interpreter[1] if interpreter else None}


def inventory(archive, host):
    with TemporaryDirectory(prefix='frameviz-abi-') as name:
        root = Path(name)
        with tarfile.open(archive) as appdir:
            appdir.extractall(root, filter='data')
        paths = sorted(path for path in root.rglob('*') if path.is_file())
        libraries = {path.name for path in paths
                     if path.is_relative_to(root / 'lib') or path.is_relative_to(root / 'usr/lib')}
        files = {'standalone/frameviz-server': inspect(host)}
        for path in paths:
            if not path.is_symlink():
                with path.open('rb') as candidate:
                    if candidate.read(4) != b'\x7fELF':
                        continue
                files[path.relative_to(root).as_posix()] = inspect(path)
    versions = {version for file in files.values() for version in file['required_versions']}
    glibc = [version for version in versions if re.fullmatch(r'GLIBC_\d+(?:\.\d+)+', version)]
    newest = max(glibc, key=lambda v: tuple(map(int, v.split('_')[1].split('.'))), default=None)
    return {'elf_count': len(files), 'highest_glibc': newest,
            'uses_glibc_private': 'GLIBC_PRIVATE' in versions,
            'external_needed': sorted({lib for item in files.values() for lib in item['needed']} - libraries),
            'files': files}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('desktop', type=Path)
    parser.add_argument('host', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    report = inventory(args.desktop, args.host)
    with args.output.open('x') as stream:
        json.dump(report, stream, indent=2)
        stream.write('\n')
    print({name: report[name] for name in report if name != 'files'})


if __name__ == '__main__':
    main()
