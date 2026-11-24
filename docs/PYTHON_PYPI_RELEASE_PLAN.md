# FrameViz 0.5.0 Python release plan

Apple Silicon macOS and Ubuntu 22.04 or 24.04 x86-64 use the same setup. `python -m pip install frameviz` installs the Python SDK. `python -m frameviz install-host` installs the matching native runtime into the user's account. Ubuntu without a desktop uses the standalone Host. The installed runtime can start offline.

## Publication sequence

1. Freeze one `0.5.0` SDK wheel and the three matching runtime archives. Verify hashes, supported platforms and version matching. Verify the installed Mac App's signature, stapled ticket and Gatekeeper behavior. Verify the Ubuntu desktop, pointer and graphics-driver behavior on native hardware.
2. With publication approval, prepare the `v0.5.0` GitHub Release with `FrameViz-0.5.0-macos-arm64-desktop.tar.xz`, the Ubuntu `linux-x86_64-desktop` and `linux-x86_64-standalone` archives, and corresponding Linux source, checksums, standalone installers, SDKs and examples as applicable. Verify that all pinned runtime assets are accessible at their final URLs.
3. Publish the single `frameviz-0.5.0-py3-none-any.whl` on PyPI. The wheel contains the SDK and hashes for the exact runtime archives. From clean environments run both quick-start commands and confirm native startup and offline reuse on each supported desktop platform before announcing the release.

The [Apple Silicon `0.5.0rc1` preview](https://pypi.org/project/frameviz/0.5.0rc1/) embeds the App in its wheel. Its original installation path is documented separately. The [Linux bundled-wheel audit](PYTHON_LINUX_RELEASE.md#platform-tag-verdict-for-the-frozen-wheel) and [150 MiB PyPI request](https://github.com/pypi/support/issues/13176) record the previous distribution work. The SDK-only stable wheel fits the ordinary quota. The Linux runtime archives are GitHub Release files and use the documented Ubuntu support range.

See the [build and verification commands](RELEASING.md) and [native Ubuntu device review](PYTHON_LINUX_NATIVE_REVIEW.md). The Linux corresponding source and its build receipt must match the Linux native archive. Reused native builds keep their own source revisions in the SDK's runtime manifest.
