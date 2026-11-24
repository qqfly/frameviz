# FrameViz 0.5.0 PyPI publication plan

The stable `0.5.0` release will cover Apple Silicon and Linux x86_64 together under the personal PyPI account `qqfly`. One `pip install frameviz` will install the SDK and matching native runtime. The lossless Linux compression trial missed the personal file quota, so the preparation order is a genuine Mac `0.5.0rc1`, a quota request, and then the dual-platform stable release.

## Publication sequence

| Order | Version and files | Destination and owner actions |
| --- | --- | --- |
| 1. Publish Mac prerelease | The signed and notarized Apple Silicon `0.5.0rc1` wheel is published. The executable release is `0.5.0-rc.1`; the wire protocol is `0.5.0`. | Install `frameviz==0.5.0rc1` from [PyPI](https://pypi.org/project/frameviz/0.5.0rc1/). The downloaded wheel and its native App passed installed verification. |
| 2. Request a larger file limit | The **150 MiB (157,286,400 bytes)** request is [open](https://github.com/pypi/support/issues/13176). The local Linux candidate is 113,530,830 bytes. | Verify the effective limit and the exact final wheel size before upload. |
| 3. Finish the independent Linux checks | The Linux desktop direct shell opener is now removed. The current wheel still uses `linux_x86_64` because its bundled library names need further work for a public manylinux tag. | An x86_64 PC booted directly into Ubuntu 24.04 LTS from a live USB can supply real GPU and driver evidence. Save the rendering, click and Gizmo logs. |
| 4. Publish both stable wheels | `frameviz-0.5.0-py3-none-macosx_11_0_arm64.whl` and, if the platform review closes, `frameviz-0.5.0-py3-none-manylinux_2_35_x86_64.whl`. Freeze exact hashes and release records. The accepted stable Mac artifact can be reused. | With authorization, make the matching Linux source delivery and checksums available alongside the downloadable wheel and upload both wheels to the same PyPI version. Use the `v0.5.0` GitHub Release in `qqfly/frameviz` for standalone installers, SDKs, the shared examples archive and matching source delivery. Confirm `python -m pip install frameviz==0.5.0` and native startup on both platforms before announcing the release. |

The stable release page should include the matching Linux wheel, corresponding-source tar archive, SHA-256 list and release notes. Refresh the build receipt if the Linux wheel or AppDir bytes change. The current Ubuntu source set can be reused for unchanged dependencies. On PyPI, publish the platform runtime wheels without a generic SDK-only wheel or sdist for this release so unsupported platforms report no matching distribution. TestPyPI is optional for rehearsals and has a separate quota. The current candidate workflow builds an archive and lacks an upload job; if using Trusted Publishing, approve and configure a specific workflow and protected publish environment first.

Warehouse defaults to 100 MiB for individual projects and 200 MiB for organization-owned projects. The file-limit request requires an existing under-limit release. A prerelease qualifies. A pending Trusted Publisher does not reserve the name. [Warehouse byte constants](https://github.com/pypi/warehouse/blob/99b93c6f8b54e739cc35742f585d1b18a7bbc3f4/warehouse/constants.py) · [PyPI size limits](https://docs.pypi.org/project-management/storage-limits/) · [Pending Trusted Publishing](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

## Final release checklist

| State | Item |
| --- | --- |
| Complete | Final Linux local wheel fingerprint, 399-file ELF audit, exact ABI floor, published tag syntax review and concrete Fedora interoperability reproduction. Existing corresponding-source material and hashes. Prior Mac stable notarization, install and startup evidence. |
| Linux technical work | Meet the PEP 600 bundled library naming requirement, produce a correctly tagged candidate and verify its exact final bytes. [Platform review](PYTHON_LINUX_RELEASE.md#platform-tag-verdict-for-the-frozen-wheel). |
| Device pending | Native Ubuntu x86_64 default desktop, real driver and interaction review using the current package or its relevant successor. [Review instructions](PYTHON_LINUX_NATIVE_REVIEW.md). |
| Account pending | The personal PyPI project is live. Wait for the file-limit decision and confirm the effective quota against final Linux bytes. |
| Authorization pending | Approve the stable release and paired PyPI upload after verification. |
