"""Installation must preserve the version, source and offline startup boundaries."""

import io
import json
import tarfile
from hashlib import sha256

import pytest

import frameviz as fv
from frameviz import host


def test_local_host_can_be_registered_for_later_discovery(tmp_path, monkeypatch):
    monkeypatch.setenv('FRAMEVIZ_HOME', str(tmp_path / 'state'))
    monkeypatch.setenv('DISPLAY', ':8')
    for variable in ('FRAMEVIZ_HOST_PATH', 'FRAMEVIZ_TAURI_APP'):
        monkeypatch.delenv(variable, raising=False)
    monkeypatch.setattr(host, '_get_repo_root', lambda: None)
    binary = tmp_path / 'custom-frameviz'
    binary.write_text('#!/bin/sh\n' "echo '{\"role\":\"desktop\",\"release\":\"0.5.0\",\"protocol\":\"0.5.0\"}'\n")
    binary.chmod(0o755)
    assert fv.install_host(path=binary) == binary
    assert host.find_host_executable(native_only=True) == binary


def test_editable_sdk_reuses_its_checkout_and_does_not_fetch_same_version(tmp_path, monkeypatch):
    from frameviz import _host_install as installer

    monkeypatch.setenv('FRAMEVIZ_HOME', str(tmp_path / 'state'))
    monkeypatch.setattr(host, '_desktop_available', lambda: True)
    checkout = tmp_path / 'checkout'
    checkout.mkdir()
    monkeypatch.setattr(host, '_get_repo_root', lambda: checkout)
    monkeypatch.setattr(host, '_source_sdk', lambda path: path == checkout)
    monkeypatch.setattr(host, '_get_tauri_app_candidates', lambda _: [])
    monkeypatch.setattr(host, '_get_appimage_candidates', lambda _: [])
    monkeypatch.setattr(host, '_bundled_runtime', lambda **kwargs: None)
    monkeypatch.setattr(installer, '_ASSET_MANIFEST', tmp_path / 'no-public-manifest.json')
    monkeypatch.setattr(installer, 'urlopen', lambda *a, **k: pytest.fail('Source SDK tried a release URL'))
    built = checkout / 'frameviz'
    system = tmp_path / 'system-frameviz'
    for path in (built, system):
        path.write_text("#!/bin/sh\necho 'FrameViz Host v0.5.0'\n")
        path.chmod(0o755)
    monkeypatch.setattr(host, '_get_tauri_exec_candidates', lambda _: [system, built])
    assert fv.install_host() == built
    built.unlink()
    with pytest.raises(RuntimeError, match='Build FrameViz from this source tree'):
        fv.install_host()


def test_published_host_install_is_explicit_and_reusable(tmp_path, monkeypatch):
    from frameviz import _host_install as installer

    monkeypatch.setenv('FRAMEVIZ_HOME', str(tmp_path / 'state'))
    monkeypatch.setattr(host, '_desktop_available', lambda: False)
    monkeypatch.setattr(host, '_get_repo_root', lambda: None)
    monkeypatch.setattr(host, '_standalone_candidates', lambda _: [])
    monkeypatch.setattr(host, '_bundled_runtime', lambda **kwargs: None)
    monkeypatch.setattr(installer, '_platform_key', lambda role: 'linux-x86_64-standalone')
    monkeypatch.setattr(installer, '_sdk_release', lambda: '0.5.0')
    for variable in ('FRAMEVIZ_HOST_PATH', 'FRAMEVIZ_TAURI_APP', 'FRAMEVIZ_WS_SERVER_CMD'):
        monkeypatch.delenv(variable, raising=False)

    binary = b'#!/bin/sh\n' b"echo '{\"role\":\"standalone\",\"release\":\"0.5.0\",\"protocol\":\"0.5.0\"}'\n"
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode='w:xz') as archive:
        entry = tarfile.TarInfo('frameviz-server')
        entry.mode, entry.size = 0o755, len(binary)
        archive.addfile(entry, io.BytesIO(binary))
    data = stream.getvalue()
    manifest = tmp_path / 'runtime-assets.json'
    monkeypatch.setattr(installer, '_ASSET_MANIFEST', manifest)
    manifest.write_text(json.dumps({'release': '0.5.0', 'assets': {'linux-x86_64-standalone': {
        'sha256': sha256(data).hexdigest(), 'size': len(data), 'release': '0.5.0', 'protocol': '0.5.0',
    }}}))
    with pytest.raises(RuntimeError, match='python -m frameviz install-host'):
        host.start_host(timeout=.1, prefer_browser=True)
    bad_archive = tmp_path / 'bad.tar.xz'
    bad_archive.write_bytes(bytes(len(data)))
    with pytest.raises(RuntimeError, match='SHA-256'):
        fv.install_host(path=bad_archive)
    assert host.find_host_executable(prefer_browser=True) is None
    calls = []
    monkeypatch.setattr(installer, 'urlopen', lambda url, **kwargs: calls.append(url) or io.BytesIO(data))
    path = fv.install_host()
    assert path.read_bytes() == binary
    assert host.find_host_executable(prefer_browser=True) == path
    assert fv.install_host() == path
    with pytest.raises(RuntimeError, match='SHA-256'):
        fv.install_host(path=bad_archive)
    assert calls == ['https://github.com/qqfly/frameviz/releases/download/v0.5.0/FrameViz-0.5.0-linux-x86_64-standalone.tar.xz']
