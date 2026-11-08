# Releasing

Version 0.4.0 is unreleased. Local candidate builds and manual CI produce reviewable artifacts; they do not push tags, publish packages, upload releases, or rewrite history.

1. Run source/privacy, license, version, contract, and installed-consumer checks against the exact source manifest.
2. Build source, wheel, JS SDK, and C++ archives into a new output directory. Include LICENSE, NOTICE, dependency license files, source identity, and artifact hashes.
3. Generate a dependency inventory for the exact build. A lockfile-based source SBOM is not a full binary linkage, vulnerability, or redistribution audit; separately identify system libraries and platform/signing assets.
4. Verify every archive's paths, required icons/resources, notices, and absence of caches, credentials, local paths, internal tools, and historical Git data.
5. Install on clean target environments, exercise real Python/C++/Vue consumers, and verify uninstall/upgrade ownership. Native packaging, signing, and platform support require actual target evidence.
6. The maintainer decides the final repository URL, registry namespaces, security contact, platform support, and publication. No links are fabricated before these destinations are configured.

`python3 scripts/release/export_source.py /new/output/source` works without Git and uses an explicit source manifest. The manifest is refreshed by `python3 scripts/update_source_manifest.py` after intentional source changes. `local-release.sh` requires a new output directory and fails on build errors. The repository has no inherited commit history; old project provenance stays in the private transition records, not the new distributable history.
