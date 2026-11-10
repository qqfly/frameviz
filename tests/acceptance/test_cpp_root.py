"""Installed C++ SDK must not select a legacy source tree's Host."""
import json,os,pathlib,subprocess
import pytest
ROOT=pathlib.Path(__file__).resolve().parents[2]
@pytest.mark.parametrize('identity',[None,{}, {'project_id':'other.frameviz','protocol_version':'0.4.0'}, {'project_id':'qqfly.frameviz','protocol_version':'0.3.4'}, {'project_id':'qqfly.frameviz','protocol_version':'0.4.0'}, {'project_id':'qqfly.frameviz','protocol_version':'0.4.7'}, {'project_id':'qqfly.frameviz','protocol_version':'0.4.01'}])
def test_cpp_source_identity(tmp_path,identity):
 executable=os.environ.get('FRAMEVIZ_CPP_FIND_HOST')
 if not executable:pytest.skip('Set FRAMEVIZ_CPP_FIND_HOST to the installed SDK find_host acceptance executable')
 (tmp_path/'pnpm-workspace.yaml').write_text('packages: []')
 binary=tmp_path/'packages/frameviz-host-tauri/src-tauri/target/debug/frameviz'
 binary.parent.mkdir(parents=True);binary.write_text('#!/bin/sh\nexit 0\n');binary.chmod(0o755)
 if identity is not None:(tmp_path/'version.json').write_text(json.dumps(identity))
 env=dict(os.environ)
 for key in ['FRAMEVIZ_HOST_PATH','FRAMEVIZ_TAURI_APP']:env.pop(key,None)
 result=subprocess.run([executable],cwd=tmp_path,env=env,capture_output=True,text=True,check=True).stdout.strip()
 assert result==(str(binary) if identity and identity.get('project_id')=='qqfly.frameviz' and identity.get('protocol_version') in ('0.4.0','0.4.7') else 'NONE')
