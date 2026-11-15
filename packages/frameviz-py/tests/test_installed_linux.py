"""Linux runtime discovery, independent of a checkout and arbitrary PATH entries."""
import json
import pathlib

import pytest

import frameviz._internal as internal
import frameviz.host as host
import frameviz.viz as viz


@pytest.fixture
def installation(tmp_path, monkeypatch):
    """Map only the standard package path into a disposable filesystem."""
    binary = tmp_path / 'usr/bin/frameviz'
    binary.parent.mkdir(parents=True)
    binary.write_text('#!/bin/sh\nexit 0\n')
    binary.chmod(0o755)
    real_path = pathlib.Path
    monkeypatch.setattr(internal.sys, 'platform', 'linux')
    monkeypatch.setattr(internal, 'Path', lambda value: binary if str(value) == '/usr/bin/frameviz' else real_path(value))
    for module in [internal, host, viz]:
        monkeypatch.setattr(module, '_get_repo_root', lambda: None)
    for key in ['FRAMEVIZ_HOST_PATH', 'FRAMEVIZ_TAURI_APP']:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setattr(viz, '_AUTO_TAURI_PROCS', [])
    return binary


def test_find_installed_runtime_without_checkout_or_override(installation):
    assert host.find_host_executable() == installation


def test_headless_wheel_host_is_preferred_only_for_the_headless_path(installation, tmp_path, monkeypatch):
    runtime = tmp_path / "wheel"
    runtime.mkdir()
    standalone = runtime / "frameviz-server"
    standalone.write_text("#!/bin/sh\nprintf 'FrameViz Host v0.5.0\\n'\n")
    standalone.chmod(0o755)
    monkeypatch.setattr(host, "_RUNTIME_DIRECTORY", runtime)
    monkeypatch.setenv("DISPLAY", ":8")
    assert host.find_host_executable() == installation
    assert host.find_host_executable(native_only=True) == installation
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    assert host.find_host_executable(prefer_browser=True) == standalone


def test_open_bootstraps_installed_runtime_without_welcome(installation, monkeypatch):
    commands = []
    monkeypatch.setattr(viz, '_run_process', lambda cmd: commands.append(cmd) or True)
    assert viz._try_open_tauri()
    assert commands == [[str(installation), '--headless']]


def test_installed_runtime_precedes_source_build(installation, tmp_path, monkeypatch):
    source = tmp_path / 'checkout'
    built = source / 'packages/frameviz-host-tauri/src-tauri/target/release/frameviz'
    built.parent.mkdir(parents=True)
    built.write_text('#!/bin/sh\nexit 0\n')
    built.chmod(0o755)
    for module in [host, viz]:
        monkeypatch.setattr(module, '_get_repo_root', lambda: source)
    assert host.find_host_executable() == installation
    commands = []
    monkeypatch.setattr(viz, '_run_process', lambda cmd: commands.append(cmd) or True)
    assert viz._try_open_tauri()
    assert commands == [[str(installation), '--headless']]


@pytest.mark.parametrize('condition', ['missing', 'directory', 'non_executable'])
def test_unusable_installed_runtime_falls_back_to_source(installation, tmp_path, monkeypatch, condition):
    if condition == 'non_executable':
        installation.chmod(0o644)
    else:
        installation.unlink()
        if condition == 'directory':
            installation.mkdir()
    source = tmp_path / 'checkout'
    built = source / 'packages/frameviz-host-tauri/src-tauri/target/release/frameviz'
    built.parent.mkdir(parents=True)
    built.write_text('#!/bin/sh\nexit 0\n')
    built.chmod(0o755)
    monkeypatch.setattr(host, '_get_repo_root', lambda: source)
    assert host.find_host_executable() == built


def test_explicit_paths_override_installed_runtime(installation, tmp_path, monkeypatch):
    custom = tmp_path / 'custom-frameviz'
    custom.write_text('#!/bin/sh\nexit 0\n')
    custom.chmod(0o755)
    monkeypatch.setenv('FRAMEVIZ_HOST_PATH', str(custom))
    monkeypatch.setenv('FRAMEVIZ_TAURI_APP', str(custom))
    assert host.find_host_executable() == custom
    commands = []
    monkeypatch.setattr(viz, '_run_process', lambda cmd: commands.append(cmd) or True)
    assert viz._try_open_tauri()
    assert commands == [[str(custom), '--headless']]


def test_bootstrap_executes_installed_file_with_headless_argument(installation, tmp_path, monkeypatch):
    """Real child process, not a mocked successful process launch."""
    receipt = tmp_path / 'launch.json'
    installation.write_text('#!/bin/sh\nprintf \'{"argument":"%s"}\\n\' "$1" > "$FRAMEVIZ_TEST_LAUNCH_RECEIPT"\n')
    monkeypatch.setenv('FRAMEVIZ_TEST_LAUNCH_RECEIPT', str(receipt))
    assert viz._try_open_tauri()
    process = viz._AUTO_TAURI_PROCS[-1]
    try:
        assert process.wait(timeout=5) == 0
        assert json.loads(receipt.read_text()) == {'argument': '--headless'}
    finally:
        if process.poll() is None:
            process.terminate()
            process.wait(timeout=5)


def test_uninstalled_system_does_not_select_arbitrary_path_command(installation, tmp_path, monkeypatch):
    installation.unlink()
    shadow = tmp_path / 'frameviz'
    shadow.write_text('#!/bin/sh\nexit 0\n')
    shadow.chmod(0o755)
    monkeypatch.setenv('PATH', str(tmp_path))
    assert host.find_host_executable() is None
    assert not viz._try_open_tauri()
