"""The runtime assembler rejects incompatible inputs before writing an output."""

from pathlib import Path
import sys

import pytest
from wheel.wheelfile import WheelFile

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts/release'))
from build_runtime_wheel import build_wheel

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
