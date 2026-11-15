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
python scripts/release/audit_linux_runtime.py \
  /new/runtime/desktop.tar.xz /new/runtime/frameviz-server /new/runtime/elf-audit.json
python scripts/release/build_runtime_wheel.py /new/preview/frameviz-0.5.0-py3-none-any.whl /new/wheels \
  --linux-desktop /new/runtime/desktop.tar.xz --linux-host /new/runtime/frameviz-server \
  --source-revision "$revision"
```

Use the actual preview filename. Verify its checksum against the preview's receipt before assembling a separately obtained file. Keep that source commit and file with the output receipt. The [Ubuntu package lock](../scripts/release/ubuntu-runtime-packages.txt) records the binary version, source package or source version, SHA-256 and archive path. The builder fetches from Ubuntu's archive or its dated snapshot. It checks the hash before extracting each package. A verified local package cache works offline. Review the lock, helper paths, and native behavior when refreshing WebKitGTK or its libraries.

The builder copies the runtime directories and helper binaries, excludes host glibc, removes static/developer files and the debugging MiniBrowser, and deduplicates byte-identical Mesa DRI drivers. It keeps the default Adwaita and hicolor icon themes and rejects symlinks escaping the AppDir. It relocates the two locked WebKitGTK helper path strings and writes before/after hashes. It generates GLib schemas and installs a launcher with an AppDir-relative library search path. The launcher leaves WebKit's sandbox settings alone. For restricted containers, record any test-only sandbox override. For Linux desktop acceptance use an ordinary user with the default sandbox and test actual pointer interaction. Document the Xvfb, software renderer and CPU translation used in container results.

`desktop.tar.xz` contains the AppDir, build receipt, Ubuntu package lock and copyright notices under `usr/share/doc`, including FrameViz/Rust notices from the preview. `frameviz-server` is the standalone payload. The output directory has a sidecar build receipt, lock and SHA-256 list. For redistribution also provide the corresponding sources or other required license materials for the shipped native dependencies, including the WebKit relocation modification. The manifest and package notices support that review. Archive extraction size is disk use. Container startup time measures the test environment only.

## Public PyPI checklist

The local wheel uses `linux_x86_64`. PyPI Warehouse accepts the defined `manylinux` tags for this glibc platform. A `manylinux_2_35_x86_64` candidate includes a compatibility promise across mainstream eligible glibc distributions. First audit all ELF files in the wheel, including the AppDir and standalone Host. Then check the required system sonames, loader paths, CPU ISA and runtime-loaded GTK/GStreamer modules, WebKit subprocess and sandbox dependencies, and GL/EGL on approved targets. Run independent headless and desktop acceptance on the baseline and a newer system. Keep the local tag until these checks support a public tag. `auditwheel show` alone cannot inspect the compressed AppDir and does not cover libraries loaded dynamically. [Warehouse tag validation](https://github.com/pypi/warehouse/blob/main/warehouse/utils/wheel.py) · [PEP 600](https://peps.python.org/pep-0600/) · [auditwheel limitations](https://github.com/pypa/auditwheel#limitations).

For the final size, check the project account's actual limit. Default single-file limits are 100 MB for an individual project and 200 MB for an organization-owned project. If still over the relevant limit, prepare an increase request for PyPI with the project URL, measured candidate size, requested cap, and an explanation that a single package includes the native WebKitGTK/Mesa closure for an offline first launch and the headless Host. PyPI asks for an existing smaller release before filing. If the project is new, plan a genuine smaller first release, such as the approved Apple Silicon build, only after publication is separately authorized. Prepare the account, 2FA and Trusted Publishing configuration for the actual project/workflow. A pending publisher does not reserve a name. [PyPI storage limits](https://docs.pypi.org/project-management/storage-limits/) · [Pending Trusted Publishers](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

If only Ubuntu compatibility can be supported, keep the wheel on an Ubuntu-specific local/private index and use its index URL or explicit file path. Public PyPI with the simple command requires the supported platform tag. A separate first-run download would retain the dependency and sandbox work, while adding a network requirement to first use.
