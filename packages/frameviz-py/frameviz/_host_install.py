"""Install the native runtime explicitly and discover it without network access."""

from importlib.metadata import PackageNotFoundError, version
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import subprocess
import sys
import tarfile
from tempfile import TemporaryDirectory
from urllib.parse import quote
from urllib.request import urlopen

from ._internal import _get_macos_app_executable
from ._linux_runtime import _unpack
from .client import PROTOCOL_VERSION
from .version import host_version_error

_ASSET_MANIFEST = Path(__file__).with_name('runtime-assets.json')
_RELEASES = 'https://github.com/qqfly/frameviz/releases/download'


def _sdk_release():
    try:
        return version('frameviz')
    except PackageNotFoundError:
        return None


def _platform_key(role):
    arch = platform.machine().lower()
    if sys.platform == 'darwin' and arch == 'arm64' and role == 'desktop':
        return 'macos-arm64-desktop'
    if sys.platform == 'linux' and arch == 'x86_64':
        try:
            system = dict(line.split('=', 1) for line in Path('/etc/os-release').read_text().splitlines() if '=' in line)
        except OSError:
            return None
        if system.get('ID', '').strip('"') == 'ubuntu' and system.get('VERSION_ID', '').strip('"') in ('22.04', '24.04'):
            return f'linux-x86_64-{role}'
    return None


def _runtime_root():
    override = os.environ.get('FRAMEVIZ_HOME')
    if override:
        return Path(override).expanduser().absolute() / 'installed-runtimes'
    if sys.platform == 'darwin':
        return Path.home() / 'Library/Application Support/FrameViz/Runtime'
    data = os.environ.get('XDG_DATA_HOME')
    base = Path(data).expanduser() if data else Path.home() / '.local/share'
    return base / 'qqfly/frameviz/installed-runtimes'


def _asset(role):
    key = _platform_key(role)
    if key is None or not _ASSET_MANIFEST.exists():
        return None
    try:
        manifest = json.loads(_ASSET_MANIFEST.read_text(encoding='utf-8'))
        entry = manifest['assets'][key]
        release = manifest['release']
        if (release != _sdk_release() or not re.fullmatch(r'[a-zA-Z0-9.+!-]+', release)
                or not re.fullmatch(r'[a-f0-9]{64}', entry['sha256'])
                or type(entry['size']) is not int or entry['size'] <= 0
                or host_version_error(entry['protocol'], PROTOCOL_VERSION)):
            raise ValueError('invalid release, archive checksum, size or protocol')
    except (OSError, ValueError, TypeError, KeyError) as error:
        raise RuntimeError(f'Invalid FrameViz runtime manifest. Reinstall the SDK. {error}') from error
    return release, key, entry


def has_release_manifest():
    return _ASSET_MANIFEST.is_file()


def can_install(role):
    """Return whether this SDK has release assets for this platform and role."""
    return has_release_manifest() and _platform_key(role) is not None


def _binary(path):
    if path.suffix == '.app':
        return _get_macos_app_executable(path)
    return path if path.is_file() and os.access(path, os.X_OK) else None


def _probe(binary):
    try:
        result = subprocess.run([binary, '--build-info', '--version'], stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, check=True, timeout=10)
        info = json.loads(result.stdout)
        if info['role'] not in ('desktop', 'standalone') or not isinstance(info['release'], str):
            raise ValueError('invalid role or release')
        if error := host_version_error(info['protocol'], PROTOCOL_VERSION):
            raise ValueError(error)
        return info
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as error:
        raise ValueError(f'Could not verify FrameViz runtime {binary}. {error}') from error


def _registration(role):
    # Explicit local builds belong to this SDK installation or source checkout.
    scope = f'{_ASSET_MANIFEST.resolve().parent}\n{_sdk_release() or PROTOCOL_VERSION}'
    identity = hashlib.sha256(os.fsencode(scope)).hexdigest()
    return _runtime_root() / 'local' / identity / f'{role}.json'


def _registered(role):
    record = _registration(role)
    try:
        path = Path(json.loads(record.read_text(encoding='utf-8'))['path'])
    except FileNotFoundError:
        return None
    except (OSError, ValueError, KeyError, TypeError) as error:
        raise RuntimeError(f'Cannot read the registered FrameViz runtime. Run python -m frameviz install-host --path again. {error}') from error
    binary = _binary(path)
    if binary is None:
        return None
    if _probe(binary)['role'] != role:
        raise RuntimeError(f'The registered FrameViz runtime has changed roles. Register {binary} again.')
    return binary


def _register(path):
    binary = _binary(path)
    if binary is None:
        raise ValueError(f'Expected a FrameViz executable or .app at {path}')
    role = _probe(binary)['role']
    record = _registration(role)
    record.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with TemporaryDirectory(dir=record.parent) as stage:
        staged = Path(stage) / record.name
        staged.write_text(json.dumps({'path': str(path)}) + '\n', encoding='utf-8')
        staged.replace(record)
    return binary


def _destination(asset):
    release, key, entry = asset
    return _runtime_root() / release / f"{key}-{entry['sha256']}"


def _archive_app(directory, key):
    if key.startswith('macos-'):
        return directory / 'FrameViz.app'
    return directory / ('frameviz-server' if key.endswith('-standalone') else 'bin/frameviz')


def installed_runtime(role):
    """Find a registered or previously installed runtime on disk."""
    if binary := _registered(role):
        return binary
    if asset := _asset(role):
        return _binary(_archive_app(_destination(asset), asset[1]))
    return None


def _copy_verified(source, target, entry):
    size = 0
    digest = hashlib.sha256()
    with target.open('xb') as stream:
        for block in iter(lambda: source.read(1024 * 1024), b''):
            size += len(block)
            if size > entry['size']:
                raise ValueError('FrameViz runtime archive exceeds its expected size')
            stream.write(block)
            digest.update(block)
    if size != entry['size'] or digest.hexdigest() != entry['sha256']:
        raise ValueError('FrameViz runtime archive size or SHA-256 does not match the SDK manifest')


def _verify_mac_app(app, source):
    if source is not None:
        attribute = subprocess.run(['/usr/bin/xattr', '-px', 'com.apple.quarantine', source],
                                   capture_output=True, text=True, timeout=10)
        if attribute.returncode == 0:
            subprocess.run(['/usr/bin/xattr', '-wx', 'com.apple.quarantine', attribute.stdout, app],
                           check=True, timeout=10)
    subprocess.run(['/usr/bin/codesign', '--verify', '--deep', '--strict', app], check=True, timeout=20)


def _install_asset(asset, path):
    release, key, entry = asset
    destination = _destination(asset)
    destination.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
    with TemporaryDirectory(prefix='.install-', dir=destination.parent) as directory:
        directory = Path(directory)
        archive = directory / 'runtime.tar.xz'
        if path is not None:
            with path.open('rb') as source:
                _copy_verified(source, archive, entry)
        else:
            name = f'FrameViz-{release}-{key}.tar.xz'
            url = f'{_RELEASES}/v{quote(release, safe="")}/{quote(name, safe="")}'
            print(f"Downloading FrameViz {release} runtime ({entry['size'] / 2**20:.1f} MiB)", file=sys.stderr)
            with urlopen(url, timeout=30) as source:
                _copy_verified(source, archive, entry)
        if binary := _binary(_archive_app(destination, key)):
            return binary
        stage = directory / 'contents'
        stage.mkdir()
        _unpack(archive, stage)
        app = _archive_app(stage, key)
        if not (binary := _binary(app)):
            raise ValueError(f'FrameViz runtime archive does not contain {app.relative_to(stage)}')
        if key.startswith('macos-'):
            _verify_mac_app(app, path)
        info = _probe(binary)
        if (info['role'] != key.rsplit('-', 1)[-1] or info['release'] != entry['release']
                or info['protocol'] != entry['protocol']):
            raise ValueError('FrameViz runtime build info does not match the SDK manifest')
        try:
            stage.rename(destination)
        except OSError:
            if not _binary(_archive_app(destination, key)):
                raise
        return _binary(_archive_app(destination, key))


def install_host(path=None):
    """Install the matching runtime once, or register a local build by path.

    Pass a matching release archive to install offline. Existing compatible
    installations are reused when no path is supplied. This never starts a Host.
    """
    from . import host

    role = 'desktop' if host._desktop_available() else 'standalone'
    if path is not None:
        path = Path(path).expanduser().resolve()
        if not path.name.endswith('.tar.xz'):
            return _register(path)
    else:
        prefer_browser = role == 'standalone'
        if binary := host.find_host_executable(prefer_browser=prefer_browser, native_only=not prefer_browser):
            return binary
    if not has_release_manifest():
        raise RuntimeError('This SDK has no release runtime manifest. Build FrameViz from this source tree or register a local build with python -m frameviz install-host --path. See docs/INSTALLATION.md.')
    if not (asset := _asset(role)):
        raise RuntimeError('No downloadable FrameViz runtime for this platform. See docs/INSTALLATION.md for supported platforms and local builds.')
    try:
        return _install_asset(asset, path)
    except (OSError, ValueError, tarfile.TarError, subprocess.SubprocessError) as error:
        raise RuntimeError(f'FrameViz runtime installation failed. {error}') from error
