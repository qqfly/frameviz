"""The runtime assembler rejects incompatible inputs before writing an output."""

from pathlib import Path
import shutil
import subprocess
import sys

import pytest
from wheel.wheelfile import WheelFile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/release'))
from audit_linux_runtime import installed_dependencies
from build_linux_appdir import copy_payload, source_index
from build_runtime_wheel import build_wheel
from runtime_metadata import build_info

REVISION = 'a' * 40


def test_can_stamp_a_release_candidate_without_changing_the_protocol(tmp_path):
    if not shutil.which('node'):
        pytest.skip('Node.js is required for the version tool')
    repo = Path(__file__).resolve().parents[2]
    files = [
        'version.json', 'scripts/sync-version.mjs',
        'packages/frameviz-protocol/src/constants.ts',
        'packages/frameviz-py/frameviz/client.py', 'packages/frameviz-py/pyproject.toml',
        'packages/frameviz-server/src/websocket.rs',
        'packages/frameviz-server/Cargo.toml', 'packages/frameviz-server/Cargo.lock',
        'packages/frameviz-host-tauri/src-tauri/Cargo.toml',
        'packages/frameviz-host-tauri/src-tauri/Cargo.lock',
        'packages/frameviz-host-tauri/src-tauri/tauri.conf.json',
        'packages/frameviz-cpp/include/frameviz/types.hpp', 'packages/frameviz-cpp/CMakeLists.txt',
        'packages/frameviz-web-viewer/index.html',
    ]
    files += [str(p.relative_to(repo)) for p in (repo / 'packages/frameviz-protocol/schemas').glob('envelope-*.json')]
    for file in files:
        destination = tmp_path / file
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(repo / file, destination)
    sync = ['node', 'scripts/sync-version.mjs']
    subprocess.run([*sync, '--release', '0.5.0-rc.1'], cwd=tmp_path, check=True)
    subprocess.run([*sync, '--check'], cwd=tmp_path, check=True)
    assert 'version = "0.5.0rc1"' in (tmp_path / 'packages/frameviz-py/pyproject.toml').read_text()
    assert 'PROTOCOL_VERSION = "0.5.0"' in (tmp_path / 'packages/frameviz-py/frameviz/client.py').read_text()
    host = tmp_path / 'packages/frameviz-host-tauri/src-tauri'
    assert '"version": "0.5.0-rc.1"' in (host / 'tauri.conf.json').read_text()
    assert 'name = "frameviz-server"\nversion = "0.5.0-rc.1"' in (host / 'Cargo.lock').read_text()


def sdk_wheel(directory):
    path = directory / 'frameviz-0.5.0rc1-py3-none-any.whl'
    with WheelFile(path, 'w') as wheel:
        wheel.writestr('frameviz-0.5.0rc1.dist-info/METADATA',
                       'Metadata-Version: 2.1\nName: frameviz\nVersion: 0.5.0rc1\n')
        wheel.writestr('frameviz-0.5.0rc1.dist-info/WHEEL',
                       'Wheel-Version: 1.0\nRoot-Is-Purelib: true\nTag: py3-none-any\n')
        wheel.writestr('frameviz/client.py', 'PROTOCOL_VERSION = "0.5.0"\n')
    return path


@pytest.mark.parametrize(('release', 'wire', 'message'), [
    ('0.4.0', '0.4.0', 'desktop release 0.4.0'),
    ('0.5.0-rc.2', '0.5.0', 'desktop release 0.5.0-rc.2'),
    ('0.5.0-rc.1', '0.4.0', 'desktop protocol 0.4.0'),
])
def test_rejects_wrong_runtime_before_creating_output(tmp_path, release, wire, message):
    output = tmp_path / 'new wheel output'
    native = [{'role': 'desktop', 'release': release, 'protocol': wire}]
    with pytest.raises(ValueError, match=message):
        build_wheel(sdk_wheel(tmp_path), output, 'macosx_11_0_arm64', {}, native, REVISION)
    assert not output.exists()


def test_normalizes_prerelease_and_creates_new_directory(tmp_path):
    output = tmp_path / 'parent with spaces' / 'new wheel output'
    native = [{'role': 'desktop', 'release': '0.5.0-rc.1', 'protocol': '0.5.7'}]
    result = build_wheel(sdk_wheel(tmp_path), output, 'macosx_11_0_arm64', {}, native, REVISION)
    with WheelFile(result) as completed:
        assert b'"sdk_release": "0.5.0rc1"' in completed.read('frameviz/_binaries/build.json')
        assert b'"sdk_protocol": "0.5.0"' in completed.read('frameviz/_binaries/build.json')


def test_legacy_desktop_version_probe_does_not_launch_window(tmp_path):
    binary = tmp_path / 'legacy'
    binary.write_text('#!/bin/sh\n[ "$2" = --version ] || exit 2\necho "FrameViz Host v0.4.0"\n')
    binary.chmod(0o755)
    with pytest.raises(ValueError, match='Invalid --build-info'):
        build_info(binary, 'desktop')


def test_ubuntu_payload_keeps_default_icons_without_external_theme_links(tmp_path):
    sysroot, appdir = tmp_path / 'system', tmp_path / 'appdir'
    icons = sysroot / 'usr/share/icons'
    (icons / 'Adwaita').mkdir(parents=True)
    (icons / 'Humanity').mkdir()
    (icons / 'Adwaita/tool.svg').write_text('icon fixture')
    (icons / 'Humanity/external.svg').symlink_to('/places/16/start-here.svg')
    (sysroot / 'usr/bin').mkdir(parents=True)
    for helper in ('bwrap', 'xdg-dbus-proxy', 'xdg-open'):
        (sysroot / 'usr/bin' / helper).write_text('helper fixture')
    (appdir / 'bin').mkdir(parents=True)
    copy_payload(sysroot, appdir)
    assert (appdir / 'usr/share/icons/Adwaita/tool.svg').read_text() == 'icon fixture'
    assert not (appdir / 'usr/share/icons/Humanity').exists()


def test_ubuntu_payload_keeps_pulseaudio_and_cuts_unused_audio_and_terminal_plugins(tmp_path):
    sysroot, appdir = tmp_path / 'system', tmp_path / 'appdir'
    relative = Path('usr/lib/x86_64-linux-gnu/gstreamer-1.0')
    (sysroot / relative).mkdir(parents=True)
    (sysroot / 'usr/bin').mkdir(parents=True)
    (appdir / 'bin').mkdir(parents=True)
    for helper in ('bwrap', 'xdg-dbus-proxy', 'xdg-open'):
        (sysroot / 'usr/bin' / helper).touch()
    for plugin in ('libgstaasink.so', 'libgstcacasink.so', 'libgstjack.so', 'libgstpulseaudio.so'):
        (sysroot / relative / plugin).touch()
    copy_payload(sysroot, appdir)
    assert [path.name for path in (appdir / relative).iterdir()] == ['libgstpulseaudio.so']


@pytest.mark.parametrize('host_library_path', [None, '', '/user lib:$literal'])
def test_linux_xdg_open_keeps_the_callers_environment(tmp_path, host_library_path):
    sysroot, appdir = tmp_path / 'system', tmp_path / 'App Dir'
    host_bin = tmp_path / 'host bin'
    system_bin = sysroot / 'usr/bin'
    system_bin.mkdir(parents=True)
    (appdir / 'bin').mkdir(parents=True)
    host_bin.mkdir()
    for helper in ('bwrap', 'xdg-dbus-proxy'):
        (system_bin / helper).touch()
    xdg_open = system_bin / 'xdg-open'
    xdg_open.write_text('#!/bin/sh\nexec system-handler "$@"\n')
    xdg_open.chmod(0o755)
    host_probe = (
        '#!/bin/sh\n'
        'printf "%s\\0" "${LD_LIBRARY_PATH-unset}" "${XDG_DATA_DIRS-unset}" '
        '"${GTK_PATH-unset}" "${GIO_EXTRA_MODULES-unset}" "${GST_PLUGIN_SCANNER-unset}" '
        '"$PATH" "$PWD" "$@"\n'
    )
    handler = host_bin / 'system-handler'
    handler.write_text(host_probe)
    handler.chmod(0o755)
    copy_payload(sysroot, appdir)
    executable = appdir / 'bin/frameviz-real'
    executable.write_text(
        '#!/bin/sh\n'
        'case "$LD_LIBRARY_PATH" in "$PWD"/*) ;; *) exit 1 ;; esac\n'
        'exec "$@"\n'
    )
    executable.chmod(0o755)
    launcher = appdir / 'bin/frameviz'
    shutil.copy2(Path(sys.path[0]) / 'linux_appdir_launcher.sh', launcher)
    launcher.chmod(0o755)
    env = {
        'PATH': f'{host_bin}:/usr/bin:/bin',
        'XDG_DATA_DIRS': '/user share:/other\nshare',
        'GTK_PATH': '',
    }
    if host_library_path is not None:
        env['LD_LIBRARY_PATH'] = host_library_path
    output = subprocess.check_output([launcher, 'xdg-open', 'https://example.invalid/?a=1&b=2'],
                                     env=env, cwd=tmp_path, text=True)
    assert output.split('\0') == [env.get('LD_LIBRARY_PATH', 'unset'), env['XDG_DATA_DIRS'], '', 'unset', 'unset',
                                  env['PATH'], str(tmp_path.resolve()), 'https://example.invalid/?a=1&b=2', '']


def test_elf_providers_must_be_on_the_consumer_search_path(tmp_path):
    private = tmp_path / 'lib/pulseaudio'
    private.mkdir(parents=True)
    (private / 'libpulse-private.so').touch()
    item = {'needed': ['libpulse-private.so'], 'search_paths': {'RUNPATH': '/usr/lib/pulseaudio'}}
    assert not installed_dependencies(item, tmp_path, tmp_path, [private.parent])['libpulse-private.so']
    assert installed_dependencies(item, tmp_path, tmp_path, [private.parent, private]) == {
        'libpulse-private.so': ['lib/pulseaudio/libpulse-private.so'],
    }


def test_ubuntu_source_index_tracks_binary_version_exceptions():
    lock = Path(__file__).resolve().parents[2] / 'scripts/release/ubuntu-runtime-packages.txt'
    packages = [(*line.split('\t')[:3], line.split('\t')[-1], None)
                for line in lock.read_text().splitlines() if line and not line.startswith('#')]
    sources = {entry['source']: entry for entry in source_index(packages)['sources']}
    assert sources['lvm2']['version'] != next(row[1] for row in packages if row[0] == 'libdevmapper1.02.1')
    assert sources['webkit2gtk']['pool_directory'] == 'pool/main/w/webkit2gtk'
    assert len(sources['webkit2gtk']['files_sha256']) == 4
