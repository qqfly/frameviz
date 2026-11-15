#!/usr/bin/env python3
"""Package the Python and C++ teaching examples for use outside the source tree."""

import argparse
import hashlib
import json
from pathlib import Path
import posixpath
import re
import subprocess
from tempfile import TemporaryDirectory
from urllib.parse import quote
from zipfile import ZIP_DEFLATED, ZipFile

from export_source import ROOT, export


DOCS = {
    'data/README.md',
    'data/models/pointcloud/synthetic_cloud.pcd',
    'docs/INSTALLATION.md',
    'docs/MACOS.md',
    'docs/PYTHON_DISTRIBUTION.md',
    'docs/SCENE_TREE.md',
    'docs/TROUBLESHOOTING.md',
    'examples/DOWNLOAD.md',
    'examples/INVENTORY.md',
    'examples/README.md',
    'packages/frameviz-cpp/README.md',
    'LICENSE',
    'NOTICE',
    'version.json',
}


def included(path):
    return path.as_posix() in DOCS or any(
        path.is_relative_to(directory)
        for directory in ('examples/python', 'examples/cpp', 'THIRD_PARTY_LICENSES')
    )


def default_source_ref():
    if (ROOT / '.git').exists():
        result = subprocess.run(['git', 'rev-parse', '--verify', 'HEAD'], cwd=ROOT,
                                capture_output=True, text=True, check=True)
        return result.stdout.strip()
    return 'task/7.6-release-candidate'


def stage_examples(directory, source_ref=None):
    source_ref = source_ref or default_source_ref()
    export(directory, select=included)
    manifest_path = directory / 'source-manifest.json'
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    paths = manifest['files']
    if not DOCS.issubset(paths):
        raise ValueError(f'Missing example inputs: {sorted(DOCS - paths.keys())}')

    # Keep packaged documentation navigable and send workspace-only links to the repository.
    link = re.compile(r'(\]\()((?:\.\.?/)?[^)\s]+)(\))')
    for name in sorted(paths):
        if not name.endswith('.md'):
            continue

        def resolve(match):
            url = match[2]
            if '://' in url or url.startswith(('#', 'mailto:')):
                return match[0]
            target, separator, anchor = url.partition('#')
            target = posixpath.normpath(posixpath.join(posixpath.dirname(name), target))
            if (directory / target).exists():
                return match[0]
            if not (ROOT / target).is_file():
                raise ValueError(f'Broken example documentation link in {name}: {url}')
            base = f'https://github.com/qqfly/frameviz/blob/{quote(source_ref, safe="/")}/'
            return f'{match[1]}{base}{quote(target)}{separator}{anchor}{match[3]}'

        document = directory / name
        content = link.sub(resolve, document.read_text(encoding='utf-8'))
        document.write_text(content, encoding='utf-8')
        paths[name] = hashlib.sha256(document.read_bytes()).hexdigest()

    # Add a root entry while keeping the canonical instructions under examples/.
    start = 'Start with [FrameViz examples](examples/DOWNLOAD.md).\n'
    (directory / 'README.md').write_text(start, encoding='utf-8')
    paths['README.md'] = hashlib.sha256(start.encode('utf-8')).hexdigest()
    manifest['documentation_ref'] = source_ref
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + '\n', encoding='utf-8')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', type=Path, help='Path to the new examples ZIP')
    parser.add_argument('--source-ref', help='Git commit for links to unpackaged documentation')
    args = parser.parse_args()
    with TemporaryDirectory(prefix='frameviz-examples-') as temp:
        stage = Path(temp) / 'contents'
        stage_examples(stage, args.source_ref)
        with ZipFile(args.output, 'x', compression=ZIP_DEFLATED) as archive:
            for path in sorted(stage.rglob('*')):
                if path.is_file():
                    archive.write(path, path.relative_to(stage).as_posix())
    print(args.output)


if __name__ == '__main__':
    main()
