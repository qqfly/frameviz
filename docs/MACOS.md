# macOS Apple Silicon preview

The current native preview targets Apple Silicon (M-series) Macs. Its executable and bundle declare macOS 11.0 as the minimum deployment target; runtime acceptance has been executed on the maintainer's macOS 27.2 machine. That declaration is not independent testing on every older macOS version. The other Mac remains a separate acceptance environment.

## Install and start

1. Verify the downloaded DMG's SHA-256 against the accompanying checksums.
2. Open the DMG and drag FrameViz.app to Applications. If an installation already exists, preserve it separately before replacing it.
3. Launch FrameViz. The startup window shows the local service endpoint and a Python example. The standalone App embeds its viewer and does not require Node, Rust, Python or the source checkout just to run.
4. Python/C++ programs create scenes in separate viewer windows. Use the App menu to quit; scenes belong to the current Host session and are not persisted across Host restart.

The current private preview uses an ad-hoc local signature and has not been submitted for Apple notarization. Downloaded copies can be blocked by Gatekeeper. After checking the source and checksum, if you choose to allow this preview, first attempt to open the App, then use System Settings → Privacy & Security → Open Anyway for this App. Managed Macs may not permit this exception. See [Apple's instructions](https://support.apple.com/en-us/102445).

## Python

Python development requires Python 3.9 or newer and the two third-party dependencies declared by the wheel. Installation can require internet access; the SDK folder is not a complete offline Python distribution.

Create a dedicated environment in your own project, then install the explicit wheel from the SDK/Python folder:

```sh
python3 -m venv .venv
.venv/bin/python -m pip install /path/to/SDK/Python/frameviz-0.4.0-py3-none-any.whl
```

Keep the App running and use:

```python
import frameviz as fv

viz = fv.open(title="My scene")
viz.add_box(color=(0.2, 0.7, 0.9))
try:
    viz.spin()
finally:
    viz.close()
```

The SDK reads the current user's matching discovery record. If an executable must be configured explicitly, use FRAMEVIZ_TAURI_APP=/Applications/FrameViz.app. Do not mix the 0.4.0 Host with older SDKs.

## C++ and Vue

Copy SDK/Cpp out of the mounted image before unmounting it. Configure a C++17 project with CMAKE_PREFIX_PATH pointing to that copied directory, use `find_package(frameviz 0.4.0 EXACT CONFIG REQUIRED)`, and link `frameviz::cpp`. The preview SDK bundles its pinned IXWebSocket static transport without TLS/zlib; it is for this local WS deployment and requires no Homebrew runtime libraries. A compiler/Xcode Command Line Tools and CMake are development prerequisites.

SDK/JavaScript contains the local protocol/core/Vue tarballs. Vue embedding still requires its third-party dependencies and a backend to provide the Host session credential; never hardcode credentials in source. See the Vue README and external app template.

## Reproduce the native App

Install source development dependencies as described in the root README. The preview builder intentionally uses ad-hoc signing and does not read a personal signing identity or submit anything to Apple:

```sh
bash scripts/release/build-macos-preview.sh /new/absolute/output
```

It builds the native App, collects the Cargo normal dependency graph for Apple Silicon, copies license notices and complete MPL component source, and verifies the local signature. Missing packaged license texts are read from the exact upstream commits recorded in published crates, using public GitHub endpoints. This can require network access even when compilation caches are complete. A notice inventory is not a vulnerability scan or legal approval.

C++ SDK builders that bundle IXWebSocket v11.4.5 can run `scripts/release/fix_cpp_sdk_metadata.py --ix-version 11.4.5 <sdk-prefix>` after installation. This removes the upstream generated absolute prefix and records the actual dependency tag rather than an inherited parent-project version. SDK versions must match the actual selected source.

Native startup acceptance requires an explicit bundle and a logged-in desktop:

```sh
FRAMEVIZ_APP_EXECUTABLE=/path/to/FrameViz.app/Contents/MacOS/frameviz \
python3 -m pytest tests/acceptance/test_macos_app.py -q
```

The observer uses public CoreGraphics window metadata filtered by the launched PID. It does not attach to installed apps by name. Use a temporary HOME/discovery/log path for every additional runtime check. `native_acceptance.py` accepts FRAMEVIZ_NATIVE_APP_EXECUTABLE; `browser_acceptance.py` accepts FRAMEVIZ_ACCEPTANCE_APP_EXECUTABLE to exercise the packaged Host and embedded HTTP viewer with Node absent from its PATH. Full native pointer/keyboard use and the other Mac's installation remain separate manual checks.

## Open source and signing

MIT controls reuse of the project's first-party source; it does not bypass macOS distribution checks. Users can build from source without owning the maintainer's Developer ID certificate. Local/ad-hoc signatures provide code integrity without a verified developer identity.

Developer ID signing identifies the developer and exposes the certificate's registered identity. Apple notarization is a separate check; Developer ID signing alone does not ensure Gatekeeper will accept a downloaded App. An organization can sign with its own identity, while an individual's certificate can reveal their legal name. Keep all private keys, signing configuration and notarization credentials outside the repository.

For ordinary end-user distribution, use Developer ID signing plus notarization after the maintainer selects that workflow. See [Tauri signing](https://v2.tauri.app/distribute/sign/macos/) and [Apple notarization](https://developer.apple.com/documentation/security/notarizing-macos-software-before-distribution). The local preview remains an explicitly unnotarized test build.
