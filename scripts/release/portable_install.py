#!/usr/bin/env python3
"""Install verified local files into a new, explicit prefix; never edit shell configuration."""
import argparse, hashlib, json, os, pathlib, shutil, tempfile
MANIFEST = 'frameviz-manifest.json'
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest()
def relative(name):
    path = pathlib.PurePosixPath(name)
    if path.is_absolute() or not path.parts or any(p in ('.','..') or p.startswith('.') for p in path.parts):
        raise ValueError(f'Unsafe manifest path: {name}')
    return path

def install(bundle, prefix):
    if prefix.exists() or prefix.is_symlink(): raise ValueError('Prefix already exists; use a new version directory')
    manifest = json.loads((bundle / MANIFEST).read_text())
    if manifest.get('format') != 1: raise ValueError('Unknown manifest format')
    files = manifest['files']
    for name, expected in files.items():
        rel = relative(name); source = bundle / rel
        if source.is_symlink() or not source.resolve().is_relative_to(bundle.resolve()) or digest(source) != expected:
            raise ValueError(f'Bundle verification failed: {name}')
    prefix.parent.mkdir(parents=True, exist_ok=True)
    stage = pathlib.Path(tempfile.mkdtemp(prefix='.frameviz-stage-', dir=prefix.parent))
    try:
        for name in files:
            dest=stage / relative(name); dest.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(bundle / name, dest)
        (stage / MANIFEST).write_text(json.dumps(manifest,indent=2)+'\n')
        os.rename(stage,prefix)
    finally:
        if stage.exists(): shutil.rmtree(stage)
    print(f'Installed verified files into {prefix}; existing installations unchanged')

def uninstall(prefix):
    manifest=json.loads((prefix / MANIFEST).read_text()); preserved=[]
    for name, expected in manifest['files'].items():
        path=prefix / relative(name)
        if not path.exists() and not path.is_symlink(): continue
        if path.is_symlink() or not path.resolve().is_relative_to(prefix.resolve()) or digest(path)!=expected:
            preserved.append(name); continue
        path.unlink()
    if preserved:
        print('Preserved modified files: '+', '.join(preserved)); return 2
    (prefix / MANIFEST).unlink()
    owned_parents = {parent for name in manifest['files'] for parent in (prefix / relative(name)).parents if parent != prefix and parent.is_relative_to(prefix)}
    for path in sorted(owned_parents, key=lambda p: len(p.parts), reverse=True):
        if path.is_dir() and not path.is_symlink():
            try: path.rmdir()
            except OSError: pass
    try: prefix.rmdir()
    except OSError: print('Preserved user-added files in '+str(prefix))
    return 0

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=['install','uninstall'])
    parser.add_argument('--bundle',type=pathlib.Path)
    parser.add_argument('--prefix',type=pathlib.Path,required=True)
    args=parser.parse_args(); prefix=args.prefix.expanduser().absolute()
    if prefix.is_symlink() or prefix.resolve() in (pathlib.Path('/'), pathlib.Path.home()) or len(prefix.parts)<3:
        parser.error('Choose a dedicated FrameViz version directory')
    if args.action=='install':
        if args.bundle is None: parser.error('--bundle is required')
        install(args.bundle,prefix); return 0
    return uninstall(prefix)
if __name__=='__main__': raise SystemExit(main())
