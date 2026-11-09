"""Installed App discovery and launch, without a checkout or path override."""
import pathlib
import plistlib

import pytest

import frameviz._internal as internal
import frameviz.host as host
import frameviz.viz as viz


def bundle(path, *, identity='dev.qqfly.frameviz.viewer', executable='frameviz'):
    contents = path / 'Contents'
    (contents / 'MacOS').mkdir(parents=True)
    (contents / 'Info.plist').write_bytes(plistlib.dumps({
        'CFBundleIdentifier': identity,
        'CFBundlePackageType': 'APPL',
        'CFBundleExecutable': executable,
        'CFBundleShortVersionString': '0.4.0',
    }))
    binary = contents / 'MacOS' / 'frameviz'
    binary.write_text('#!/bin/sh\nexit 0\n')
    binary.chmod(0o755)
    return binary


@pytest.fixture
def installed(tmp_path, monkeypatch):
    monkeypatch.setattr(internal.sys, 'platform', 'darwin')
    monkeypatch.setattr(pathlib.Path, 'home', lambda: tmp_path)
    monkeypatch.setattr(internal, '_get_repo_root', lambda: None)
    monkeypatch.setattr(viz, '_get_repo_root', lambda: None)
    monkeypatch.setattr(host, '_get_repo_root', lambda: None)
    monkeypatch.delenv('FRAMEVIZ_TAURI_APP', raising=False)
    monkeypatch.delenv('FRAMEVIZ_HOST_PATH', raising=False)
    monkeypatch.setattr(viz, '_AUTO_TAURI_PROCS', [])
    return tmp_path / 'Applications/FrameViz.app'


def test_user_installed_app_is_found_without_a_checkout_or_override(installed):
    binary = bundle(installed)
    assert host.find_host_executable() == binary


def test_sdk_launches_installed_app_without_showing_welcome(installed, monkeypatch):
    binary = bundle(installed)
    launched = []
    monkeypatch.setattr(viz, '_run_process', lambda command: launched.append(command) or True)
    assert viz._try_open_tauri()
    assert launched == [[str(binary), '--headless']]


def test_source_bundle_uses_its_declared_lowercase_executable(tmp_path, monkeypatch):
    monkeypatch.setattr(internal.sys, 'platform', 'darwin')
    monkeypatch.setattr(host, '_get_repo_root', lambda: tmp_path)
    app = tmp_path / 'packages/frameviz-host-tauri/src-tauri/target/release/bundle/macos/FrameViz.app'
    binary = bundle(app)
    assert host.find_host_executable() == binary


@pytest.mark.parametrize('identity,executable', [
    ('other.vendor.frameviz', 'frameviz'),
    ('dev.qqfly.frameviz.viewer', '../frameviz'),
])
def test_unrelated_or_malformed_installed_bundle_is_ignored(installed, identity, executable):
    bundle(installed, identity=identity, executable=executable)
    assert installed not in internal._get_tauri_app_candidates(None)


def test_installed_executable_may_not_escape_the_bundle(installed, tmp_path):
    binary = bundle(installed)
    outside = tmp_path / 'outside'
    outside.write_text('#!/bin/sh\nexit 0\n')
    outside.chmod(0o755)
    binary.unlink()
    binary.symlink_to(outside)
    assert installed not in internal._get_tauri_app_candidates(None)


def test_legacy_uppercase_executable_is_supported(installed):
    binary = bundle(installed, executable='FrameViz')
    renamed = binary.with_name('FrameViz')
    binary.rename(renamed)
    assert host.find_host_executable() == renamed


def test_installed_app_needs_an_executable_file(installed):
    binary = bundle(installed)
    binary.chmod(0o644)
    assert installed not in internal._get_tauri_app_candidates(None)


def test_system_install_location_is_considered(installed, monkeypatch):
    system_app = pathlib.Path('/Applications/FrameViz.app')
    binary = pathlib.Path('/Applications/FrameViz.app/Contents/MacOS/frameviz')
    resolve = lambda p: binary if p == system_app else None
    monkeypatch.setattr(internal, '_get_macos_app_executable', resolve)
    monkeypatch.setattr(host, '_get_macos_app_executable', resolve)
    assert host.find_host_executable() == binary


def test_control_socket_startup_does_not_launch_a_second_owned_app(installed, monkeypatch):
    class Running:
        def poll(self):
            return None
    monkeypatch.setattr(viz, '_AUTO_TAURI_PROCS', [Running()])
    monkeypatch.setattr(viz, '_run_process', lambda command: pytest.fail('Second App launched'))
    assert viz._try_open_tauri()
