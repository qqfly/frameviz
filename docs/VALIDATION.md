# Validation

Run checks from this source tree after dependency installation. Report passing, failing, skipped, disabled, and unrun tests separately. A zero exit code from a script that records failures in JSON is not sufficient evidence.

```sh
node scripts/sync-version.mjs --check
python3 scripts/check_source.py
pnpm test
.venv/bin/python -m pytest packages/frameviz-py/tests tests/acceptance/test_portable.py tests/acceptance/test_standalone.py tests/acceptance/test_host_contracts.py tests/acceptance/test_host_boundaries.py tests/acceptance/test_maintenance.py -q
cargo test --locked --manifest-path packages/frameviz-server/Cargo.toml
ctest --test-dir .cache/cpp-release --output-on-failure
```

Real Host/browser acceptance lives under `tests/acceptance`. It covers SDK-to-Host-to-viewer transport, synthetic model loading, physical mouse camera/pick/Gizmo interaction, refresh, and Vue mounting. Installed consumers must come from independently built wheels, C++ install prefixes, and JS tarballs. A source-linked demo is not a substitute for package consumption.

Use a temporary HOME, independent ports, and an explicit discovery path for every Host/native run. Never attach test tools to an installed app by name. The manual demo and Host fixtures use local synthetic data. A native programmatic window/camera check does not replace visual/interactive native acceptance.

Record source and actual binary hashes, commands, dependency environment, actual execution counts, and necessary failure evidence. Reuse build caches by toolchain, cap ordinary new evidence at 256 MiB and this validation task at 2 GiB, and stop rather than silently discarding failures. Detailed local validation receipts belong outside distributable source. CI definitions are execution entry points; only an actual CI run provides platform evidence.

The optional C++ model HTTP harness is built from `tests/acceptance/cpp`. Set `FRAMEVIZ_ASSET_TEST_BINARY` to `asset_harness` when running `test_cpp_assets.py`; absent harnesses are reported as skips. It checks the explicit model root, hidden and encoded-hidden paths, sibling/symlink escapes, private file types, local CORS, and foreign Origin rejection.

Set `FRAMEVIZ_CPP_FIND_HOST` to the installed SDK `find_host` executable when running `test_cpp_root.py`. This regression checks that missing, unrelated, and legacy project identities cannot be selected for automatic startup; the matching standalone tree remains discoverable. The source scanner allows a newly initialized Git repository; the source exporter always excludes Git metadata and history.

For explicit packaged-App startup/native/embedded-viewer checks on macOS, see [MACOS.md](MACOS.md). A visible startup window and headless behavior are checked separately, and actual native interaction is not inferred from a successful build.


Develop and test on a task branch, then open a pull request targeting `main`. Ubuntu contracts run when that PR opens, receives new commits or reopens. At the candidate stage, dispatch the full **CI** matrix and **Ubuntu runtime preview** for the candidate ref. **Candidate source archive** also calls the full matrix before producing its archive. Compare the run's SHA with the candidate before reviewing the results. Keep the original test failure and any later rerun together.
