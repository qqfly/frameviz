# FrameViz C++ SDK

Protocol and package version: `0.5.0`. The SDK is C++17, uses IXWebSocket for transport, and includes nlohmann/json. First-party source is MIT, copyright qqfly; preserve bundled third-party notices.

See [source installation](../../docs/INSTALLATION.md). Configure consumers with `-DCMAKE_PREFIX_PATH=/your/frameviz-sdk`, `find_package(frameviz CONFIG REQUIRED)`, and `target_link_libraries(app PRIVATE frameviz::cpp)`.

The client obtains a token only from explicit configuration or a matching discovery endpoint. `FRAMEVIZ_AUTH_TOKEN` provides a session token and `FRAMEVIZ_DISCOVERY_PATH` selects an explicit discovery record. All components must use 0.5.0. Camera/pick queries require a live viewer and return errors when unavailable. Ordinary event subscriptions need consumption; synchronous query replies do not require a hidden polling loop.

The public headers are under `include/frameviz`. Use a dedicated Host and synthetic data for integration tests; regular gtest counts include skipped and disabled cases, which must be reported separately. See [validation](../../docs/VALIDATION.md) and [API](../../docs/API_Definition.md).


## Scene controls and display queries

`Viz::open` and `Viz::connect` dispatch callbacks serially on a background
thread by default. Pass `false` for their last argument when an application
dispatches callbacks on its own loop with `pollEvents()`. Keep application
state shared between callbacks and other threads synchronized.

```cpp
auto number = viz->addWidget("number", "X", 0, {{"minimum", -2}, {"maximum", 2}});
viz->onWidgetChange(number, [&, box](const frameviz::json &event) {
  viz->setTransform(box, frameviz::RigidPose{{event.at("value").get<float>(), 0, 0}});
});
viz->setWidgetValue(number, 0);         // Update the views silently.
auto camera = viz->getCameraView();     // Same JSON fields as Python.
auto scene = viz->getDisplayState(true); // Include available bounds.
```

Pass `true` to `setWidgetValue` to emit a program event. Rebinding
`onWidgetChange` replaces the previous handler unless you explicitly append.
