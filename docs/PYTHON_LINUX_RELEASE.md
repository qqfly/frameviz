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

The Linux native Viewer uses the WebKitGTK 4.1 context as created by Wry. FrameViz leaves the context and sandbox environment settings at their defaults. The running contexts in the Ubuntu 22.04 and 24.04 wheel checks had Bubblewrap sandboxing disabled by default. The WebProcess shared its Host's namespaces and did not acquire an additional seccomp filter. The ordinary desktop path does not use the Bubblewrap helpers. Headless Host and external-browser modes do not create a packaged WebKitGTK Viewer.

An upstream `WEBKIT_FORCE_SANDBOX=1` diagnostic selects a different path. The shipped WebKitGTK still has compiled-in `/usr/bin/bwrap` and `/usr/bin/xdg-dbus-proxy` references for that path. FrameViz does not expose a sandbox-enabled mode in this version. A future opt-in or default-on feature would require a WebKit build with relocatable helpers, read-only mounts for the AppDir libraries and resources, and effective confinement validation on supported desktop hosts. That work would limit WebProcess access to the host system. It is tracked separately from the default-mode wheel checks.

Use the [native Ubuntu acceptance procedure](PYTHON_LINUX_NATIVE_REVIEW.md) from a regular desktop account. Record actual pointer interaction, renderer and process evidence. Report Xvfb, software rendering and CPU translation when applicable. Treat the extracted cache as disk usage and container launch timing as environment-specific.

## Native license and source records

`desktop.tar.xz` includes the runtime receipt, Ubuntu binary lock, a source package and version index, and per-package copyright notices under `usr/share/doc`. The preview supplies FrameViz and Rust notices. `frameviz-server` is the independent Host. The output directory includes the receipt, both package indexes and a SHA-256 list. A previous native preview can be reused when native sources are unchanged. Record the native source in the AppDir receipt and pass its SHA with `--runtime-source-revision` when assembling the new SDK wheel.

Fetch Ubuntu sources by exact package and source version from the signed Jammy snapshot in `ubuntu-runtime-sources.json`. Enable the corresponding `deb-src` entries for `jammy`, `jammy-updates` and `jammy-security` with the Ubuntu archive keyring, then use `apt-get source --download-only --only-source <source>=<version>`. The index includes the component paths of the binary inputs, which can differ from the path of their source. For WebKitGTK use the exact [source file lock](../scripts/release/ubuntu-webkit-source.json). Its `pool_directory` works under the Ubuntu archive and the pinned snapshot. The recipe replaces two occurrences of the fixed helper path byte string, keeps the length unchanged, and records the original and modified library hashes and byte strings in `runtime-build.json`. The AppDir includes the exact modifying recipe under `usr/share/doc/frameviz`.

Use the standalone collector with a trusted Ubuntu archive keyring to prepare the source delivery. It checks signatures on the three historical `InRelease` records and SHA-256 on their source indexes, then downloads every exact source version in the AppDir index. The output includes the signed metadata, per-file checksums and source receipt.

```sh
python scripts/release/collect_ubuntu_sources.py /new/runtime/ubuntu-runtime-sources.json /new/source/ubuntu \
  --keyring /usr/share/keyrings/ubuntu-archive-keyring.gpg
(cd /new/source/ubuntu && sha256sum -c SHA256SUMS)
```

Make this source collection available alongside the wheel, together with the exact FrameViz source revisions, build scripts, notices and the WebKit modification record. The [matching source delivery instructions](PYTHON_LINUX_CORRESPONDING_SOURCE.md) explain the bundle layout, extraction and rebuild inputs.

## Public PyPI checklist

The local wheel uses `linux_x86_64`. PyPI Warehouse accepts the defined `manylinux` tags for this glibc platform. A `manylinux_2_35_x86_64` candidate includes a compatibility promise across mainstream eligible glibc distributions. First audit all ELF files in the wheel, including the AppDir and standalone Host. Then check the required system sonames, loader paths, CPU ISA and runtime-loaded GTK/GStreamer modules, WebKit subprocess and sandbox dependencies, and GL/EGL on approved targets. Run independent headless and desktop acceptance on the baseline and a newer system. Keep the local tag until these checks support a public tag. `auditwheel show` alone cannot inspect the compressed AppDir and does not cover libraries loaded dynamically. [Warehouse tag validation](https://github.com/pypi/warehouse/blob/main/warehouse/utils/wheel.py) · [PEP 600](https://peps.python.org/pep-0600/) · [auditwheel limitations](https://github.com/pypa/auditwheel#limitations).

Check the effective file limit for the selected personal PyPI account against the final Linux wheel. The default is 100 MB per file. The documented increase process requires an existing smaller release. The paired first-release plan calls for resolving any shortfall before uploading either wheel. Record the project URL, exact size, requested cap, and the reason for bundling the runtime for a quota discussion. A pending publisher does not reserve a name. [PyPI storage limits](https://docs.pypi.org/project-management/storage-limits/) · [Pending Trusted Publishers](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

## Platform-tag verdict for the frozen wheel

The current wheel stays `linux_x86_64` for local installation. The candidate build is `61733589651f3b36123e18806adb0c2510143c8c` and its wheel SHA-256 is `10601986246f8de7a18778fd2bfcb797517741bf533ee39cf1fd5d0f48e14250`.

- `auditwheel 6.8.2 show` reports `manylinux_2_34_x86_64` from the visible standalone Host. That result omits `desktop.tar.xz`. Comparing the version requirements of all 399 ELF files with the auditwheel x86_64 policy passes the SONAME and version checks for `manylinux_2_35_x86_64`. Cairo, JavaScriptCore and WebKitGTK need `GLIBC_2.35`; LLVM, JavaScriptCore and WebKitGTK also need `GLIBCXX_3.4.30`. Both requirements exclude `manylinux_2_34_x86_64`. Ubuntu 22.04's installer accepts `manylinux_2_35_x86_64`; jumping to `manylinux_2_36_x86_64` would exclude that baseline.
- On an offline Fedora 43 test container, a controlled `BROWSER` handler invoked the host's `rpm --version` through the wheel's bundled `xdg-open`. It worked with a clean environment. With the shipped AppDir library search path inherited, the same command failed because the bundled `libcrypto.so.3` lacked the host's `OPENSSL_3.4.0`. This reproduces a library collision at the host-program boundary. The bundled GnuTLS separately loaded Fedora's system trust roots successfully.
- For a public tag, scope the packaged loader environment to its runtime processes and keep host launchers and handlers on their own libraries. Replay the same external-program probe and regression-test the default desktop and headless modes on the resulting wheel. The AppDir's shared libraries use ordinary SONAMEs, and the PEP 600 uniqueness rule still needs an explicit compatibility resolution for the private executable payload. The ISA notes only declare x86-64 baseline for the files that carry them. Verify the baseline build flags or run a baseline-CPU execution check if the proof remains incomplete.

`manylinux_2_35_x86_64` is the lowest viable **ABI target**. The current wheel has a concrete PEP 600 interoperability blocker even if the native Ubuntu review passes. Separately, run the existing native Ubuntu review before the formal Linux release. It covers physical GPU and pointer interaction. The review remains pending while hardware is unavailable. Enabling the optional WebKit sandbox remains a separate enhancement. [PEP 600 compatibility contract](https://peps.python.org/pep-0600/#core-definition).

See the [PyPI publication sequence and checklist](PYTHON_PYPI_RELEASE_PLAN.md) for the paired first release and handling the personal account's file quota.
