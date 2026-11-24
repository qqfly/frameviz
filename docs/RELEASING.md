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

For stable Python distribution, build the pure SDK wheel, the App from the [Developer ID signing workflow](MACOS.md), and the two native Linux runtimes from the [Ubuntu AppDir recipe](PYTHON_LINUX_RELEASE.md). On the Mac with `wheel` installed, run:

```sh
revision=$(git rev-parse HEAD)
python scripts/release/build_host_distribution.py /new/sdk/frameviz-0.5.0-py3-none-any.whl /new/distribution \
  --source-revision "$revision" \
  --mac-app /new/signed/FrameViz.app --mac-source-revision "$revision" \
  --linux-desktop /new/runtime/desktop.tar.xz --linux-host /new/runtime/frameviz-server \
  --linux-host-notices /new/preview/standalone/notices --linux-source-revision "$revision"
```

The distribution contains one `py3-none-any` wheel with runtime hashes and three archives. Install that wheel into fresh environments and test `python -m frameviz install-host --path ARCHIVE`, repeating with the other platform and Linux standalone role. Verify the installed Mac App with `codesign --verify --deep --strict`, `xcrun stapler validate`, and a Gatekeeper assessment. Complete native window checks before making the files available. Include all three archives, the matching Linux corresponding source, the examples ZIP and their checksums in the versioned GitHub Release. With publication approval, confirm that the exact pinned assets are accessible before publishing the SDK wheel on PyPI.

When reusing verified native builds, supply their original source revisions with `--mac-source-revision` and `--linux-source-revision`. Record which checks carry forward and rerun installation checks on the new distribution files.

Run `python -m twine check --strict` on the final wheels. Preview the description from the built wheel and check that the demo plays, the example link opens, and the quick start works with the installed package. After publication, verify that PyPI renders the page and plays the demo through its image proxy.

The [Ubuntu AppDir recipe](PYTHON_LINUX_RELEASE.md) also records the bundled Linux wheel experiment and its platform-tag requirements.
