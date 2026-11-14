#!/usr/bin/env python3
"""Build a manifest-verified portable candidate from explicitly supplied artifacts."""
import argparse, hashlib, json, pathlib, re, shutil, tarfile, tempfile
from build_examples_zip import stage_examples
ROOT=pathlib.Path(__file__).resolve().parents[2]
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('version');p.add_argument('input',type=pathlib.Path);p.add_argument('output',type=pathlib.Path,nargs='?',default=pathlib.Path('release-final'))
    a=p.parse_args()
    if not re.fullmatch(r'v?\d+\.\d+\.\d+(?:-[A-Za-z0-9.-]+)?',a.version): p.error('Invalid version')
    if a.version.lstrip('v').split('-')[0] != json.loads((ROOT/'version.json').read_text())['protocol_version']: p.error('Version does not match version.json')
    candidates=[f for f in a.input.rglob('*') if f.is_file() and not f.is_symlink()]
    a.output.mkdir(parents=True,exist_ok=True); created=[]
    for platform, patterns in [('macOS-arm64',('FrameViz*.dmg','frameviz*.dmg','FrameViz*.app.tar.gz','*cpp-sdk*macos*.tar.gz')),('Linux-x64',('*frameviz*.deb','*FrameViz*.deb','*cpp-sdk*linux*x64*.tar.gz'))]:
        selected=[f for f in candidates if any(f.match(pattern) for pattern in patterns)]
        if not selected: continue
        selected += [f for f in candidates if f.match('*.whl')]
        names=[f.name for f in selected]
        if len(names)!=len(set(names)): raise ValueError('Ambiguous duplicate artifact names')
        output=a.output/f'FrameViz-{a.version}-{platform}-bundle.tar.gz'
        if output.exists(): raise ValueError('Output already exists; choose a new directory')
        with tempfile.TemporaryDirectory(prefix='frameviz-bundle-') as temp:
            stage=pathlib.Path(temp)/'bundle'
            stage_examples(stage)
            for name in ('README.txt','install.sh','uninstall.sh','portable_install.py'):
                shutil.copy2(ROOT/'scripts/release'/name,stage/name)
            (stage/'artifacts').mkdir()
            for source in selected: shutil.copy2(source,stage/'artifacts'/source.name)
            files={str(f.relative_to(stage)):hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(stage.rglob('*')) if f.is_file()}
            (stage/'frameviz-manifest.json').write_text(json.dumps({'format':1,'version':a.version,'platform':platform,'files':files},indent=2)+'\n')
            with tarfile.open(output,'w:gz') as archive:
                for f in sorted(stage.iterdir()): archive.add(f,arcname=f.name)
        created.append(str(output))
    if not created: p.error('No supported platform payload found in input')
    print('\n'.join(created))
if __name__=='__main__': main()
