# FrameViz 0.5.0 PyPI publication plan

The initial public release will cover Apple Silicon and Linux x86_64 together under the personal PyPI account `qqfly`. One `pip install frameviz` will install the Python SDK and the matching native runtime on those platforms. Prepare both wheels before opening the release window.

## Publication sequence

| Order | Version and files | Destination and owner actions |
| --- | --- | --- |
| 1. Prepare the account | Proposed project name `frameviz`. Its public PyPI JSON returned HTTP 404 on 2026-11-17. Availability is confirmed by PyPI when establishing the project. | The owner selected personal account `qqfly`. Verify publisher access and project quota as part of release preparation. |
| 2. Finish the independent Linux checks | Re-run platform checks after closing the library-inheritance problem. Use the existing test ZIP for native Ubuntu review. Confirm the result against the final runtime; if the scoped compatibility fix affects the trial, rerun the same smoke on its successor. | An x86_64 Windows PC booted directly into Ubuntu 24.04 LTS from a live USB can supply the native desktop evidence if its log identifies the real GPU and driver. Save the rendering, click and Gizmo logs. |
| 3. Check the final Linux size | Current Linux candidate size is 114,089,026 bytes. Check the exact final wheel against the account's per-file limit. The draft request is 150 MB. | If the limit is sufficient, prepare the paired uploads. If the wheel still exceeds the limit, resolve the quota route before the first upload. The documented increase process requires an existing under-limit release. Seek an official first-release option or an explicit owner decision on any change to the paired-first-release plan. |
| 4. Publish both stable wheels | `frameviz-0.5.0-py3-none-macosx_11_0_arm64.whl` and, if the platform review closes, `frameviz-0.5.0-py3-none-manylinux_2_35_x86_64.whl`. Freeze exact hashes and attestations. Existing accepted Mac bytes can be reused if still applicable. | With authorization, make the Linux source delivery and checksum records publicly accessible alongside the matching downloadable wheel. Upload both wheels to the same PyPI version in one release window. The proposed location for downloadable release assets is a separate public `qqfly/frameviz-dist` release `v0.5.0`, subject to owner approval and repository creation or selection. Confirm `python -m pip install frameviz==0.5.0` and native startup on both platforms before announcing the release. |

The proposed stable release page should include the matching Linux wheel, corresponding-source tar archive, SHA-256 list and release notes. Refresh the build receipt if the Linux wheel or AppDir bytes change. The current Ubuntu source set can be reused for unchanged dependencies. The existing private source repository can remain private. On PyPI, publish the platform runtime wheels without a generic SDK-only wheel or sdist for this release so unsupported platforms report no matching distribution. TestPyPI is optional for rehearsals and has a separate quota. The current candidate workflow builds an archive and lacks an upload job; if using Trusted Publishing, approve and configure a specific workflow and protected publish environment first.

PyPI's default file limits are 100 MB for individual projects and 200 MB for organization-owned projects. A size-limit request requires an under-limit release already uploaded to the project; a prerelease qualifies. A pending Trusted Publisher does not reserve the name. [PyPI size limits](https://docs.pypi.org/project-management/storage-limits/) · [Pending Trusted Publishing](https://docs.pypi.org/trusted-publishers/creating-a-project-through-oidc/) · [Python version specification](https://packaging.python.org/en/latest/specifications/version-specifiers/).

## Final release checklist

| State | Item |
| --- | --- |
| Complete | Final Linux local wheel fingerprint, 399-file ELF audit, exact ABI floor, published tag syntax review and concrete Fedora interoperability reproduction. Existing corresponding-source material and hashes. Prior Mac stable notarization, install and startup evidence. |
| Linux technical work | Close host-launch library inheritance and the PEP 600 SONAME rule; complete baseline CPU evidence if needed. Produce a correctly tagged candidate and verify its exact final bytes. [Platform review](PYTHON_LINUX_RELEASE.md#platform-tag-verdict-for-the-frozen-wheel). |
| Device pending | Native Ubuntu x86_64 default desktop, real driver and interaction review using the current package or its relevant successor. [Review instructions](PYTHON_LINUX_NATIVE_REVIEW.md). |
| Account pending | Owner confirmed. Verify publisher access and effective quota against final Linux bytes. |
| Authorization pending | Approve the paired public upload, the chosen public release asset location and any required quota route. PR merge also requires approval. |
