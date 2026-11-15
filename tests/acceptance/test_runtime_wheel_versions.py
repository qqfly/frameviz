"""The runtime assembler rejects incompatible inputs before writing an output."""

from pathlib import Path
import sys

import pytest
from wheel.wheelfile import WheelFile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/release'))
from build_linux_appdir import copy_payload
from build_runtime_wheel import build_wheel
from runtime_metadata import build_info

REVISION = 'a' * 40


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
