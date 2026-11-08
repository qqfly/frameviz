# C++ tests

Build with `FRAMEVIZ_BUILD_TESTS=ON` and run CTest. Keep ordinary, skipped, disabled, explicitly enabled Host integrations, installed-consumer checks, and browser queries separate in reports.

Host-dependent tests require an explicitly configured isolated endpoint/token and must not launch an installed application. Do not convert connection failures into passing evidence. See the project validation documentation.
