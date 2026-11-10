"""License collector graph selection and path boundaries, using synthetic metadata."""
import importlib.util,pathlib,json
import pytest
ROOT=pathlib.Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('macos_licenses',ROOT/'scripts/release/collect_macos_licenses.py');module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
def metadata(tmp_path,escape=False):
 packages=[{'id':'root','source':None,'manifest_path':str(ROOT/'packages/frameviz-server/Cargo.toml')}];nodes=[{'id':'root','deps':[]}]
 for name,kind in [('runtime',None),('build-only','build'),('dev-only','dev')]:
  directory=tmp_path/name;directory.mkdir();(directory/'Cargo.toml').write_text('fixture');(directory/'LICENSE').write_text('Synthetic license notice')
  package={'id':name,'name':name,'version':'1','source':'registry+fixture','manifest_path':str(directory/'Cargo.toml'),'license':'MIT','repository':None,'license_file':None}
  if escape and name=='runtime':package['license_file']=str(tmp_path/'outside-license.txt');(tmp_path/'outside-license.txt').write_text('private synthetic sentinel')
  packages.append(package);nodes.append({'id':name,'deps':[]});nodes[0]['deps'].append({'pkg':name,'dep_kinds':[{'kind':kind}]})
 return {'packages':packages,'resolve':{'root':'root','nodes':nodes}}
def test_only_normal_runtime_dependencies_are_collected(tmp_path):
 app=tmp_path/'Preview.app';app.mkdir();result=module.collect(metadata(tmp_path),app)
 assert [p['name'] for p in result['components']]==['runtime']
 assert (app/'Contents/Resources/ThirdPartyLicenses/runtime-1/LICENSE').read_text()=='Synthetic license notice'
 assert not (app/'Contents/Resources/ThirdPartyLicenses/build-only-1').exists()
def test_license_file_cannot_escape_dependency_source(tmp_path):
 app=tmp_path/'Preview.app';app.mkdir()
 with pytest.raises(ValueError,match='escapes'):module.collect(metadata(tmp_path,True),app)
 assert not (app/'Contents/Resources/ThirdPartyLicenses/runtime-1/outside-license.txt').exists()

def test_mpl_source_does_not_follow_external_symlinks(tmp_path):
 data=metadata(tmp_path);next(p for p in data['packages'] if p['id']=='runtime')['license']='MPL-2.0'
 secret=tmp_path/'private-sentinel.txt';secret.write_text('synthetic private sentinel');(tmp_path/'runtime/escape.txt').symlink_to(secret)
 app=tmp_path/'Preview.app';app.mkdir()
 with pytest.raises(ValueError,match='symlink'):module.collect(data,app)


def test_dependency_notices_can_be_collected_for_standalone_distribution(tmp_path):
 resources=tmp_path/'standalone-notices'
 result=module.collect_resources(metadata(tmp_path),resources)
 assert [p['name'] for p in result['components']]==['runtime']
 assert (resources/'ThirdPartyLicenses/runtime-1/LICENSE').read_text()=='Synthetic license notice'
 assert (resources/'LICENSE').is_file()
 assert not (resources/'Contents').exists()


def test_reviewed_missing_repository_requires_exact_package_version_and_commit():
 package={'name':'libappindicator-sys','version':'0.9.0','repository':None}
 sha='eafd1e3682a1247f595410266091e9684021cb6f'
 assert module.license_repository(package,sha)=='https://github.com/tauri-apps/libappindicator-rs'
 with pytest.raises(ValueError,match='License text unavailable'):
  module.license_repository(package,'0'*40)
 with pytest.raises(ValueError,match='License text unavailable'):
  module.license_repository(dict(package,version='0.9.1'),sha)
