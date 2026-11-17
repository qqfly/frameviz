# FrameViz 0.5.0 PyPI publication plan

The stable `0.5.0` release will cover Apple Silicon and Linux x86_64 together under the personal PyPI account `qqfly`. One `pip install frameviz` will install the SDK and matching native runtime. The lossless Linux compression trial missed the personal file quota, so the preparation order is a genuine Mac `0.5.0rc1`, a quota request, and then the dual-platform stable release.

## Publication sequence

| Order | Version and files | Destination and owner actions |
| --- | --- | --- |
| 1. Prepare the account | Proposed project name `frameviz`. Its public PyPI JSON returned HTTP 404 on 2026-11-17. Availability is confirmed by PyPI when establishing the project. | The owner selected personal account `qqfly`. Verify publisher access and project quota as part of release preparation. |
| 2. Publish the Mac prerelease after approval | `frameviz-0.5.0rc1-py3-none-macosx_11_0_arm64.whl`. Executable release `0.5.0-rc.1` and wire protocol `0.5.0`. | Upload the exact signed and notarized wheel to PyPI after owner approval. Testers can install `frameviz==0.5.0rc1`. |
| 3. Request the file quota after the RC is downloadable | Draft request **150 MiB (157,286,400 bytes)** for PyPI. The retained Linux trial wheel is 114,048,634 bytes, above the 104,857,600-byte default. Update final measurements when the Linux release file is ready. | Use the PyPI Support file-limit form, supply the real project link, explain what the Linux wheel bundles, and wait for confirmation before uploading Linux. |
| 4. Finish the independent Linux checks | Review platform tagging after closing the remaining host-program boundary and evaluating unique SONAMEs. Keep the native Ubuntu test against the final wheel. | An x86_64 PC booted directly into Ubuntu 24.04 LTS from a live USB can supply real GPU and driver evidence. Save the rendering, click and Gizmo logs. |
| 5. Publish both stable wheels | `frameviz-0.5.0-py3-none-macosx_11_0_arm64.whl` and, if the platform review closes, `frameviz-0.5.0-py3-none-manylinux_2_35_x86_64.whl`. Freeze exact hashes and release records. The accepted stable Mac artifact can be reused. | With authorization, make the matching Linux source delivery and checksums available alongside the downloadable wheel and upload both wheels to the same PyPI version. The proposed release-asset location is a separate public `qqfly/frameviz-dist` release `v0.5.0`, subject to owner approval. Confirm `python -m pip install frameviz==0.5.0` and native startup on both platforms before announcing the release. |

The proposed stable release page should include the matching Linux wheel, corresponding-source tar archive, SHA-256 list and release notes. Refresh the build receipt if the Linux wheel or AppDir bytes change. The current Ubuntu source set can be reused for unchanged dependencies. The existing private source repository can remain private. On PyPI, publish the platform runtime wheels without a generic SDK-only wheel or sdist for this release so unsupported platforms report no matching distribution. TestPyPI is optional for rehearsals and has a separate quota. The current candidate workflow builds an archive and lacks an upload job; if using Trusted Publishing, approve and configure a specific workflow and protected publish environment first.

Warehouse defaults to 100 MiB for individual projects and 200 MiB for organization-owned projects. The file-limit request requires an existing under-limit release. A prerelease qualifies. A pending Trusted Publisher does not reserve the name. [Warehouse byte constants](https://github.com/pypi/warehouse/blob/99b93c6f8b54e739cc35742f585d1b18a7bbc3f4/warehouse/constants.py) · [PyPI size limits](https://docs.pypi.org/project-management/storage-limits/) · [Pending Trusted Publishing](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/).

## Final release checklist

| State | Item |
| --- | --- |
| Complete | Final Linux local wheel fingerprint, 399-file ELF audit, exact ABI floor, published tag syntax review and concrete Fedora interoperability reproduction. Existing corresponding-source material and hashes. Prior Mac stable notarization, install and startup evidence. |
| Linux technical work | Close host-launch library inheritance and the PEP 600 SONAME rule; complete baseline CPU evidence if needed. Produce a correctly tagged candidate and verify its exact final bytes. [Platform review](PYTHON_LINUX_RELEASE.md#platform-tag-verdict-for-the-frozen-wheel). |
| Device pending | Native Ubuntu x86_64 default desktop, real driver and interaction review using the current package or its relevant successor. [Review instructions](PYTHON_LINUX_NATIVE_REVIEW.md). |
| Account pending | Owner confirmed. Verify publisher access, submit the quota request after the eligible RC release, and confirm the effective quota against final Linux bytes. |
| Authorization pending | Approve the Mac RC upload, the file-limit request, the chosen release asset location and the paired stable upload. PR merge also requires approval. |
