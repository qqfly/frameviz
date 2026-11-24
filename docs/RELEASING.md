# Releasing

The Apple Silicon `0.5.0rc1` wheel is available on [PyPI](https://pypi.org/project/frameviz/0.5.0rc1/). The stable 0.5.0 release is in preparation. Local candidate builds and manual CI produce artifacts for review.

1. Review the [changelog](../CHANGELOG.md) for user-facing features, compatibility changes, fixes, and known limitations. Keep candidate changes under Unreleased until publication. Run source/privacy, license, version, contract, and installed-consumer checks against the exact source manifest.
2. Build source, wheel, JS SDK, and C++ archives into a new output directory. Include LICENSE, NOTICE, dependency license files, source identity, and artifact hashes.
3. Generate a dependency inventory for the exact build. A lockfile-based source SBOM is not a full binary linkage, vulnerability, or redistribution audit; separately identify system libraries and platform/signing assets.
4. Verify every archive's paths, required icons/resources, notices, and absence of caches, credentials, local paths, internal tools, and historical Git data.
5. Install on clean target environments, exercise real Python/C++/Vue consumers, and verify uninstall/upgrade ownership. Native packaging, signing, and platform support require actual target evidence.
6. The maintainer decides the final repository URL, registry namespaces, security contact, platform support, and publication. No links are fabricated before these destinations are configured.

`python3 scripts/release/export_source.py /new/output/source` works without Git and uses an explicit source manifest. The manifest is refreshed by `python3 scripts/update_source_manifest.py` after intentional source changes. `local-release.sh` requires a new output directory and fails on build errors. The repository has no inherited commit history; old project provenance stays in the private transition records, not the new distributable history.

From a clean candidate checkout, run `python3 scripts/release/build_examples_zip.py /new/output/FrameViz-0.5.0-examples.zip` to build the shared Python/C++ examples archive. When building from an exported source tree, pass `--source-ref` with its candidate commit to pin links to repository-only documentation. Extract the produced ZIP to a path with spaces and use the installed SDK to test the documented commands. The [examples guide](../examples/DOWNLOAD.md) lists the required runtime and optional renderer.

For the Apple Silicon platform wheel, build the universal SDK wheel and the App from the same candidate. Use the App produced by the [Developer ID signing workflow](MACOS.md). With the `wheel` Python tool installed, run:

```sh
python scripts/release/build_runtime_wheel.py /new/sdk/frameviz-0.5.0-py3-none-any.whl /new/wheels \
  --mac-app /new/signed/FrameViz.app --source-revision "$(git rev-parse HEAD)"
```

Install this file into a fresh environment. Verify the installed App with `codesign --verify --deep --strict` and, after completing notarization, separately verify its stapled ticket and Gatekeeper assessment. Complete native window checks before making the file available. For the examples command, place the matching ZIP and its `SHA256SUMS` alongside the versioned Release assets.

If an already signed and notarized runtime predates a packaging-only change, use `--runtime-source-revision` with its original build receipt. Verify that the runtime inputs are identical across those revisions. The wheel records the SDK and native runtime revisions separately.

Run `python -m twine check --strict` on the final wheels. Preview the description from the built wheel and check that the demo plays, the example link opens, and the quick start works with the installed package. After publication, verify that PyPI renders the page and plays the demo through its image proxy.

The [Ubuntu AppDir recipe and PyPI checklist](PYTHON_LINUX_RELEASE.md) cover the Linux platform wheel.
