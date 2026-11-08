# Validation entry points

See [validation](../docs/VALIDATION.md) for automated commands and evidence boundaries. Python/C++ Host tests need an isolated loopback service, independent discovery path and disposable data. Browser checks need the built viewer, a compatible Chromium installation, and actual installed SDK consumers. Native programmatic checks and manual interaction are separate acceptance tasks.

`tests/acceptance/demo.py` starts a temporary Host, synthetic model/point-cloud scene and optional Vue page. Build the viewer and Vue acceptance page as described in the root README, then stop the demo with Ctrl+C. Credentials stay in the disposable session.

`interactive_test.py`, `web_viewer/` and `issue_regressions/` are manual tools. Numbered regression filenames identify inherited test cases; they do not imply a public issue tracker exists. Run each only with an explicit new Host, view and synthetic inputs. Their presence does not count as executed coverage.

Automated source, Host boundary, portable installer, model HTTP, root isolation and maintenance checks are under `acceptance/`. Report skipped or disabled cases separately. Store reports outside distributable source; do not delete historical evidence using the maintenance helpers, which only inspect local build paths.
