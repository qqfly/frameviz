"""Installed C++ SDK must not select a legacy source tree's Host."""
import json,os,pathlib,subprocess
import plistlib
import sys
import pytest
ROOT=pathlib.Path(__file__).resolve().parents[2]
@pytest.mark.parametrize('identity',[None,{}, {'project_id':'other.frameviz','protocol_version':'0.5.0'}, {'project_id':'qqfly.frameviz','protocol_version':'0.4.4'}, {'project_id':'qqfly.frameviz','protocol_version':'0.5.0'}, {'project_id':'qqfly.frameviz','protocol_version':'0.5.7'}, {'project_id':'qqfly.frameviz','protocol_version':'0.5.01'}])
def test_cpp_source_identity(tmp_path,identity):
 executable=os.environ.get('FRAMEVIZ_CPP_FIND_HOST')
 if not executable:pytest.skip('Set FRAMEVIZ_CPP_FIND_HOST to the installed SDK find_host acceptance executable')
 (tmp_path/'pnpm-workspace.yaml').write_text('packages: []')
 binary=tmp_path/'packages/frameviz-host-tauri/src-tauri/target/debug/frameviz'
 binary.parent.mkdir(parents=True);binary.write_text('#!/bin/sh\nexit 0\n');binary.chmod(0o755)
 if identity is not None:(tmp_path/'version.json').write_text(json.dumps(identity))
 env=dict(os.environ)
 for key in ['FRAMEVIZ_HOST_PATH','FRAMEVIZ_TAURI_APP']:env.pop(key,None)
 env['HOME'] = str(tmp_path)
 result=subprocess.run([executable],cwd=tmp_path,env=env,capture_output=True,text=True,check=True).stdout.strip()
 valid = identity and identity.get('project_id') == 'qqfly.frameviz' and identity.get('protocol_version') in ('0.5.0','0.5.7')
 if sys.platform == 'darwin' and result.startswith('/Applications/FrameViz.app/Contents/MacOS/'):
  return  # A verified system installation takes precedence on macOS.
 assert result == (str(binary) if valid else 'NONE')


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS App bundles")
def test_cpp_installed_app_identity_and_version(tmp_path):
    harness = os.environ.get("FRAMEVIZ_CPP_FIND_HOST")
    if not harness:
        pytest.skip("Installed C++ SDK find_host acceptance executable required")
    app = tmp_path / "Applications/FrameViz.app"
    binary = app / "Contents/MacOS/FrameViz"
    binary.parent.mkdir(parents=True)
    binary.write_text("#!/bin/sh\nexit 0\n")
    binary.chmod(0o755)
    plist = app / "Contents/Info.plist"
    env = {key: value for key, value in os.environ.items()
           if key not in ("FRAMEVIZ_HOST_PATH", "FRAMEVIZ_TAURI_APP")}
    env["HOME"] = str(tmp_path)

    def find(**changes):
        return subprocess.run([harness], cwd=tmp_path, env=dict(env, **changes),
                              text=True, capture_output=True, timeout=5)

    info = {"CFBundleIdentifier": "dev.qqfly.frameviz.viewer", "CFBundlePackageType": "APPL",
            "CFBundleExecutable": "FrameViz", "CFBundleShortVersionString": "0.5.7"}
    plist.write_bytes(plistlib.dumps(info, fmt=plistlib.FMT_BINARY))
    assert find().stdout.strip() == str(binary)
    info["CFBundleShortVersionString"] = "0.4.0"
    plist.write_bytes(plistlib.dumps(info))
    assert find().stdout.strip() not in ("", str(binary))
    explicit = find(FRAMEVIZ_TAURI_APP=str(app))
    assert explicit.returncode == 1 and "0.4.0" in explicit.stderr
    info["CFBundleShortVersionString"] = "0.5.0"
    info["CFBundleIdentifier"] = "org.example.different-app"
    plist.write_bytes(plistlib.dumps(info))
    assert find().stdout.strip() not in ("", str(binary))
