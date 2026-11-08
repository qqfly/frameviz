# FrameViz C++ SDK

Protocol and package version: `0.4.0`. The SDK is C++17, uses IXWebSocket for transport, and includes nlohmann/json. First-party source is MIT, copyright qqfly; preserve bundled third-party notices.

See [source installation](../../docs/INSTALLATION.md). Configure consumers with `-DCMAKE_PREFIX_PATH=/your/frameviz-sdk`, `find_package(frameviz CONFIG REQUIRED)`, and `target_link_libraries(app PRIVATE frameviz::cpp)`.

The client obtains a token only from explicit configuration or a matching discovery endpoint. `FRAMEVIZ_AUTH_TOKEN` provides a session token and `FRAMEVIZ_DISCOVERY_PATH` selects an explicit discovery record. All components must use 0.4.0. Camera/pick queries require a live viewer and return errors when unavailable. Ordinary event subscriptions need consumption; synchronous query replies do not require a hidden polling loop.

The public headers are under `include/frameviz`. Use a dedicated Host and synthetic data for integration tests; regular gtest counts include skipped and disabled cases, which must be reported separately. See [validation](../../docs/VALIDATION.md) and [API](../../docs/API_Definition.md).
