import hashlib, importlib.util, json, pathlib, subprocess
import pytest
ROOT=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('portable',ROOT/'scripts/release/portable_install.py');portable=importlib.util.module_from_spec(spec);spec.loader.exec_module(portable)
def bundle(tmp_path):
    root=tmp_path/'bundle';root.mkdir();(root/'sdk.txt').write_text('sdk')
    (root/portable.MANIFEST).write_text(json.dumps({'format':1,'files':{'sdk.txt':hashlib.sha256(b'sdk').hexdigest()}}));return root

def test_install_uninstall_preserves_unowned_and_modified_files(tmp_path):
    source=bundle(tmp_path);target=tmp_path/'installed';portable.install(source,target)
    (target/'user.txt').write_text('keep');(target/'sdk.txt').write_text('modified')
    assert portable.uninstall(target)==2
    assert (target/'sdk.txt').read_text()=='modified'
    (target/'sdk.txt').write_text('sdk');assert portable.uninstall(target)==0
    assert (target/'user.txt').read_text()=='keep'

def test_failed_upgrade_preserves_existing_install(tmp_path):
    source=bundle(tmp_path);target=tmp_path/'installed';portable.install(source,target)
    (source/'sdk.txt').write_text('corrupt')
    with pytest.raises(ValueError): portable.install(source,target)
    assert (target/'sdk.txt').read_text()=='sdk'
    with pytest.raises(ValueError): portable.install(source,tmp_path/'new-version')
    assert not (tmp_path/'new-version').exists()

@pytest.mark.parametrize('name',['..','../escape','a/b','/tmp/escape','.', '-bad'])
def test_generator_rejects_unsafe_names(tmp_path,name):
    keep=tmp_path/'sentinel';keep.write_text('keep')
    result=subprocess.run(['bash',str(ROOT/'scripts/release/create_new_frameviz_app.sh'),'--name',name,'--path',str(tmp_path),'--force'],capture_output=True)
    assert result.returncode!=0
    assert keep.read_text()=='keep'

def test_manifest_rejects_traversal(tmp_path):
    source=bundle(tmp_path);(source/portable.MANIFEST).write_text(json.dumps({'format':1,'files':{'../outside':hashlib.sha256(b'sdk').hexdigest()}}))
    with pytest.raises(ValueError): portable.install(source,tmp_path/'install')

def test_generator_preserves_symlinks_and_unowned_directories(tmp_path):
    source=tmp_path/'user';source.mkdir();sentinel=source/'sentinel';sentinel.write_text('keep')
    link=tmp_path/'Alias';link.symlink_to(source,target_is_directory=True)
    for name in ['Alias','user']:
        result=subprocess.run(['bash',str(ROOT/'scripts/release/create_new_frameviz_app.sh'),'--name',name,'--path',str(tmp_path),'--force'],capture_output=True)
        assert result.returncode!=0
    assert sentinel.read_text()=='keep'

def test_http_server_rejects_hidden_files_sources_and_symlink_escape(tmp_path):
    import socket,time,urllib.request,urllib.error,os
    dist=ROOT/'packages/frameviz-web-viewer/dist';dist.mkdir(exist_ok=True)
    secret=tmp_path/'private.txt';secret.write_text('synthetic sentinel')
    hidden=dist/'.acceptance-hidden';link=dist/'acceptance-link.txt'
    with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    hidden.write_text('synthetic sentinel');link.symlink_to(secret)
    process=subprocess.Popen(['node',str(ROOT/'packages/frameviz-web-viewer/serve.mjs')],env=dict(os.environ,FRAMEVIZ_HTTP_PORT=str(port)),stdout=subprocess.DEVNULL)
    try:
        for _ in range(100):
            try:
                with urllib.request.urlopen(f'http://127.0.0.1:{port}/') as response:assert response.status==200
                break
            except OSError:time.sleep(.02)
        for path in ['/.acceptance-hidden','/acceptance-link.txt','/packages/frameviz-py/frameviz/client.py','/%2e%2e/private.txt']:
            with pytest.raises(urllib.error.HTTPError) as error:urllib.request.urlopen(f'http://127.0.0.1:{port}'+path)
            assert error.value.code==404
    finally:
        process.terminate();process.wait(timeout=5);hidden.unlink();link.unlink()

def test_export_excludes_private_and_build_sentinels(tmp_path,monkeypatch):
    spec=importlib.util.spec_from_file_location('exporter',ROOT/'scripts/release/export_source.py');exporter=importlib.util.module_from_spec(spec);spec.loader.exec_module(exporter)
    fake=tmp_path/'source';fake.mkdir();subprocess.run(['git','init','-q',str(fake)],check=True)
    real_output=subprocess.check_output
    monkeypatch.setattr(subprocess,'check_output',lambda args,**kwargs: 'acceptance-fixture\n' if args==['git','rev-parse','HEAD'] else real_output(args,**kwargs))
    for name in ['safe.py','.env','.hidden/private.py','build/CMakeCache.txt','data/private.json','cache.log','node_modules/dependency/index.js']:
        path=fake/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_text('synthetic sentinel')
    (fake/'LICENSE').write_text('MIT fixture');(fake/'NOTICE').write_text('fixture notice');(fake/'source-manifest.json').write_text(json.dumps({'format':2,'version':'0.4.0','files':{'safe.py':hashlib.sha256((fake/'safe.py').read_bytes()).hexdigest()}}));exporter.ROOT=fake;dest=tmp_path/'export';exporter.export(dest)
    assert set(json.loads((dest/'source-manifest.json').read_text())['files'])=={'safe.py','LICENSE','NOTICE'}


def test_setup_bundle_has_verifiable_installer_and_preserves_existing_prefix(tmp_path):
    import tarfile
    inputs=tmp_path/'inputs';inputs.mkdir();(inputs/'frameviz-cpp-sdk-macos-arm64.tar.gz').write_bytes(b'synthetic artifact')
    version = json.loads((ROOT / 'version.json').read_text())['protocol_version']
    out = tmp_path / 'out'
    subprocess.run(['bash', str(ROOT / 'scripts/release/build-setup-bundle.sh'),
                    f'v{version}', str(inputs), str(out)], check=True, capture_output=True)
    unpacked=tmp_path/'unpacked';unpacked.mkdir()
    with tarfile.open(next(out.glob('*.tar.gz'))) as archive: archive.extractall(unpacked,filter='data')
    target=tmp_path/'installed'
    subprocess.run(['bash',str(unpacked/'install.sh'),'--bundle',str(unpacked),'--prefix',str(target)],check=True,capture_output=True)
    assert (target/'portable_install.py').is_file()
    before=(target/'frameviz-manifest.json').read_bytes()
    result=subprocess.run(['bash',str(unpacked/'install.sh'),'--bundle',str(unpacked),'--prefix',str(target)],capture_output=True)
    assert result.returncode!=0 and (target/'frameviz-manifest.json').read_bytes()==before
