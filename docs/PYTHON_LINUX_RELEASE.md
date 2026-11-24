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

Check the effective file limit for the selected personal PyPI account against the final Linux wheel. Warehouse defaults to 100 MiB (104,857,600 bytes) per file for individual projects. The documented increase process requires an existing under-limit release. Record the project URL, exact size, requested cap and the reason for bundling the runtime. A pending publisher does not reserve a name. [Warehouse byte constants](https://github.com/pypi/warehouse/blob/99b93c6f8b54e739cc35742f585d1b18a7bbc3f4/warehouse/constants.py) · [PyPI storage limits](https://docs.pypi.org/project-management/storage-limits/) · [Pending Trusted Publishers](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

The lossless size trial used the same previous AppDir tar each time. Its `xz -6` wheel was 114,048,634 bytes. The smallest wheel tested was 106,546,926 bytes using the x86 filter and a 256 MiB dictionary, still 1,689,326 bytes over the limit. Its first unpack peaked at 296,676 KiB RSS, versus 41,264 KiB for `-6` in the translated Ubuntu container. The current candidate retains `xz -6`, and the rebuilt desktop wheel is 113,530,830 bytes.

## Platform-tag verdict for the frozen wheel

The current wheel stays `linux_x86_64` for local installation. The SDK and both native executables were built from `47c0f532f15435af6e9d1d170ce51b6d264cb80a`. The wheel SHA-256 is `319c0026728d6685ca138ea86d883604241aea4efe1d34590c4d2ecc11da28b2`.

- Comparing all 399 ELF files, including `desktop.tar.xz` and the standalone Host, with the auditwheel 6.8.2 policy passes the system-library allowlist and symbol-version checks for `manylinux_2_35_x86_64`. `GLIBC_2.35` and `GLIBCXX_3.4.30` both exclude `manylinux_2_34_x86_64`. Ubuntu 22.04's installer accepts `manylinux_2_35_x86_64`. Tagging at `manylinux_2_36_x86_64` would exclude that baseline.
- With the previous wheel's launcher in a Fedora 43 container, a controlled `firefox` handler calling system RPM inherited the AppDir search path and failed on `OPENSSL_3.4.0`. The Linux desktop build now omits the unused Tauri shell plugin, which could launch a named program directly. The new packaged desktop binary has no shell open command. The retained `xdg-open` wrapper restored the original environment and working directory before invoking the controlled RPM handler on Fedora. The SDK browser path launches from the Python process, and WebKit and GStreamer helpers run as private runtime children.
- The final wheel's standalone Host returned HTTP 200 from its Viewer route under a checked x86-64 baseline CPUID model in QEMU. The Tauri binary resolved its shared libraries with eager binding and returned build info on the same model. Full WebKit rendering and graphics-driver behavior on a baseline CPU remain outside that probe.
- The AppDir still uses 363 distinct bundled ELF SONAMEs, including system-style names such as `libcrypto.so.3` and `libglib-2.0.so.0`. The app runs in a separate process from Python, but the archive does not meet PEP 600's globally unique bundled library naming requirement. A public manylinux build needs to address both ELF references and libraries discovered by name at runtime.

`manylinux_2_35_x86_64` is the lowest viable **ABI target**. Keep the local tag until the bundled library naming requirement is addressed. Separately, complete the native Ubuntu review of physical GPU and pointer interaction before the formal Linux release. Enabling the optional WebKit sandbox remains a separate enhancement. [PEP 600 compatibility contract](https://peps.python.org/pep-0600/#core-definition).

See the [PyPI publication sequence and checklist](PYTHON_PYPI_RELEASE_PLAN.md) for the Mac prerelease and paired stable release.
