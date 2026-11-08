"""Maintenance commands must preserve unrelated state even from another cwd."""
import os,pathlib,subprocess
ROOT=pathlib.Path(__file__).resolve().parents[2]
def test_cleanup_helpers_preserve_shared_state_and_foreign_working_tree(tmp_path):
 home=tmp_path/'home';shared=home/'Library/Caches/com.frameviz.viewer/sentinel';shared.parent.mkdir(parents=True);shared.write_text('keep')
 foreign=tmp_path/'foreign';asset=foreign/'packages/frameviz-core/dist/user.txt';asset.parent.mkdir(parents=True);asset.write_text('keep')
 commands=tmp_path/'commands';commands.mkdir();trace=tmp_path/'pnpm-called'
 stub=commands/'pnpm';stub.write_text('#!/bin/sh\n: > "$FRAMEVIZ_MAINTENANCE_TRACE"\n');stub.chmod(0o755)
 env=dict(os.environ,HOME=str(home),PATH=str(commands)+os.pathsep+os.environ['PATH'],FRAMEVIZ_MAINTENANCE_TRACE=str(trace))
 result=subprocess.run(['bash',str(ROOT/'scripts/clean-cache.sh')],cwd=foreign,env=env,capture_output=True,text=True)
 assert result.returncode==0
 assert shared.read_text()=='keep'
 assert asset.read_text()=='keep'
 assert not trace.exists(),'Must not prune a shared package store'

def test_generated_template_is_independently_attributed(tmp_path):
 import json
 target=tmp_path/'Sample_App'
 subprocess.run(['bash',str(ROOT/'scripts/release/create_new_frameviz_app.sh'),'--name','Sample_App','--path',str(tmp_path)],check=True,capture_output=True)
 assert 'qqfly' in (target/'LICENSE').read_text()
 assert (target/'NOTICE').is_file()
 assert (target/'THIRD_PARTY_LICENSES/nlohmann-json-MIT.txt').is_file()
 assert json.loads((target/'src-tauri/tauri.conf.json').read_text())['identifier']=='dev.qqfly.frameviz.sample-app'
