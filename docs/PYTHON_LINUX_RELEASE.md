# Ubuntu runtime build and PyPI readiness

## Build the local Ubuntu candidate

Use a clean FrameViz checkout on Ubuntu 22.04 x86-64. Install the build tools and Tauri prerequisites listed in the Ubuntu preview workflow, plus `binutils`, `xz-utils` and `libglib2.0-bin`. In the build Python environment install `build` and `wheel`. Build the same revision used for the SDK. The release and protocol are read separately from the actual desktop and standalone binaries using `--build-info`.

```sh
pnpm install --frozen-lockfile
revision=$(git rev-parse HEAD)
scripts/release/build-linux-preview.sh /new/preview
deb=/new/preview/FrameViz_0.5.0_amd64.deb
sha=$(sha256sum "$deb" | cut -d' ' -f1)
python scripts/release/build_linux_appdir.py "$deb" /new/runtime \
  --preview-sha256 "$sha" --source-revision "$revision" --cache /new/deb-cache
python scripts/release/build_runtime_wheel.py /new/preview/frameviz-0.5.0-py3-none-any.whl /new/wheels \
  --linux-desktop /new/runtime/desktop.tar.xz --linux-host /new/runtime/frameviz-server \
  --source-revision "$revision"
python scripts/release/audit_linux_runtime.py --check \
  /new/wheels/frameviz-0.5.0-py3-none-linux_x86_64.whl /new/runtime/elf-audit.json
```

Use the actual preview filename. Verify its checksum against the preview's receipt before assembling a separately obtained file. Keep that source commit and file with the output receipt. The [Ubuntu package lock](../scripts/release/ubuntu-runtime-packages.txt) records the binary version, source package or source version, SHA-256 and archive path. The builder fetches from Ubuntu's archive or its dated snapshot. It checks the hash before extracting each package. A verified local package cache works offline. Review the lock, helper paths, and native behavior when refreshing WebKitGTK or its libraries.

The builder excludes system glibc, developer files, MiniBrowser and the PAM session module. It omits the GStreamer ASCII-art, libcaca and JACK modules. WebGL, standard audio discovery and PulseAudio remain available. GnuTLS and its library dependencies are bundled for the GIO TLS module and GTK's CUPS backend. HTTPS uses the operating system's CA trust store. PulseAudio's private library directory is part of the launcher's search path because the Ubuntu libraries also carry an absolute system RUNPATH. The builder deduplicates identical Mesa DRI binaries, retains Adwaita and hicolor, rejects escaping symlinks and compiles GLib schemas.

For Ubuntu desktop acceptance use an ordinary user with the default sandbox and test actual pointer interaction. The launcher leaves WebKit's sandbox environment alone. WebKitGTK's active Bubblewrap path still references `/usr/bin/bwrap` and `/usr/bin/xdg-dbus-proxy`. Its startup logic also binds resources within the sandbox. A container run with default environment values does not exercise that path unless WebKit actually uses it. Record which helper and subprocess paths were executed, together with Xvfb, software rendering and CPU translation where applicable. Treat the extracted cache as disk usage and container launch timing as environment-specific.

## Native license and source records

`desktop.tar.xz` includes the runtime receipt, Ubuntu binary lock, a source package and version index, and per-package copyright notices under `usr/share/doc`. The preview supplies FrameViz and Rust notices. `frameviz-server` is the independent Host. The output directory includes the receipt, both package indexes and a SHA-256 list. A previous native preview can be reused when native sources are unchanged. Record the native source in the AppDir receipt and pass its SHA with `--runtime-source-revision` when assembling the new SDK wheel.

Fetch Ubuntu sources by exact package and source version from the signed Jammy snapshot in `ubuntu-runtime-sources.json`. Enable the corresponding `deb-src` entries for `jammy`, `jammy-updates` and `jammy-security` with the Ubuntu archive keyring, then use `apt-get source --download-only --only-source <source>=<version>`. The index includes the component paths of the binary inputs, which can differ from the path of their source. For WebKitGTK use the exact [source file lock](../scripts/release/ubuntu-webkit-source.json). Its `pool_directory` works under the Ubuntu archive and the pinned snapshot. The recipe replaces two occurrences of the fixed helper path byte string, keeps the length unchanged, and records the original and modified library hashes and byte strings in `runtime-build.json`. The AppDir includes the exact modifying recipe under `usr/share/doc/frameviz`.

Before public distribution, provide the corresponding source files and required build and modification materials for the native licenses alongside the wheel. The package indexes and WebKit source hashes identify what to publish and let reviewers verify an offline copy.

## Public PyPI checklist

The local wheel uses `linux_x86_64`. PyPI Warehouse accepts the defined `manylinux` tags for this glibc platform. A `manylinux_2_35_x86_64` candidate includes a compatibility promise across mainstream eligible glibc distributions. First audit all ELF files in the wheel, including the AppDir and standalone Host. Then check the required system sonames, loader paths, CPU ISA and runtime-loaded GTK/GStreamer modules, WebKit subprocess and sandbox dependencies, and GL/EGL on approved targets. Run independent headless and desktop acceptance on the baseline and a newer system. Keep the local tag until these checks support a public tag. `auditwheel show` alone cannot inspect the compressed AppDir and does not cover libraries loaded dynamically. [Warehouse tag validation](https://github.com/pypi/warehouse/blob/main/warehouse/utils/wheel.py) · [PEP 600](https://peps.python.org/pep-0600/) · [auditwheel limitations](https://github.com/pypa/auditwheel#limitations).

For the final size, check the project account's actual limit. Default single-file limits are 100 MB for an individual project and 200 MB for an organization-owned project. If still over the relevant limit, prepare an increase request for PyPI with the project URL, measured candidate size, requested cap, and an explanation that a single package includes the native WebKitGTK/Mesa closure for an offline first launch and the headless Host. PyPI asks for an existing smaller release before filing. If the project is new, plan a genuine smaller first release, such as the approved Apple Silicon build, only after publication is separately authorized. Prepare the account, 2FA and Trusted Publishing configuration for the actual project/workflow. A pending publisher does not reserve a name. [PyPI storage limits](https://docs.pypi.org/project-management/storage-limits/) · [Pending Trusted Publishers](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

Keep the current wheel tagged `linux_x86_64` for local installation. Before assigning a public tag, verify active sandbox startup using relocatable helper paths and read-only bindings for the extracted runtime and its resources. Validate native desktop rendering, the system integration paths and the standalone Host on the actual final artifact.
