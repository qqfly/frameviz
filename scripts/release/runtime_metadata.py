"""Build-time metadata checks for FrameViz runtime artifacts."""

import ast
import hashlib
import json
import re
import subprocess

from packaging.version import Version


def sha256(stream):
    digest = hashlib.sha256()
    for chunk in iter(lambda: stream.read(1024 * 1024), b''):
        digest.update(chunk)
    return digest.hexdigest()


def file_hash(path):
    with path.open('rb') as stream:
        return sha256(stream)


def protocol(value):
    if not isinstance(value, str) or not re.fullmatch(r'(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)', value):
        raise ValueError(f'Expected a numeric protocol version, got {value!r}')
    return tuple(int(part) for part in value.split('.'))


def sdk_protocol(source):
    values = [ast.literal_eval(node.value) for node in ast.parse(source).body
              if isinstance(node, ast.Assign) and any(
                  isinstance(target, ast.Name) and target.id == 'PROTOCOL_VERSION'
                  for target in node.targets)]
    if len(values) != 1:
        raise ValueError('The SDK wheel must declare one protocol version')
    protocol(values[0])
    return values[0]


def build_info(binary, role):
    # Older desktop builds ignore unknown flags. --version makes those builds
    # exit without opening a native window. Only newer builds return JSON.
    result = subprocess.run([binary, '--build-info', '--version'], capture_output=True, text=True,
                            check=True, timeout=10)
    try:
        info = json.loads(result.stdout)
        if info['role'] != role:
            raise ValueError(f'Expected a {role} runtime, got {info["role"]}')
        Version(info['release'])
        protocol(info['protocol'])
        return {key: info[key] for key in ('role', 'release', 'protocol')}
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(f'Invalid --build-info from {binary}: {error}') from error


def check_pair(sdk_release, sdk_wire, native):
    role = native['role']
    if Version(native['release']) != Version(sdk_release):
        raise ValueError(f'{role} release {native["release"]} does not match SDK release {sdk_release}')
    if protocol(native['protocol'])[:2] != protocol(sdk_wire)[:2]:
        raise ValueError(f'{role} protocol {native["protocol"]} is not compatible with SDK protocol {sdk_wire}')
