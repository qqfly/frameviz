# C++ examples

Install this project's C++ SDK into a chosen prefix and pass that prefix with `CMAKE_PREFIX_PATH`. No global shell profile, company SDK, or internal installer is needed.

Run against a dedicated Host using protocol 0.5.0 with a matching credential and live viewer. Examples demonstrate APIs; they are not performance or platform qualification. See the root installation and validation guides.

Configure from the repository root. The complete [case list](../INVENTORY.md)
links each target to its Python counterpart.

```sh
cmake -S examples/cpp -B .cache/cpp-examples -DCMAKE_PREFIX_PATH="$PWD/.local/sdk"
cmake --build .cache/cpp-examples --parallel
.cache/cpp-examples/bin/01_basic_primitives/hello_world
```

Executables are under `bin/<category>/` in the build directory. To build one
case, pass `--target <name>`. Output cases use the [optional renderer](../../packages/frameviz-cpp/README.md#screenshots-and-offline-html).

Run the compiled example directly after installing the matching runtime.
The SDK reuses a compatible running Host, or starts one from these locations.

- macOS looks in `~/Applications` and `/Applications`.
- Linux uses `/usr/bin/frameviz` on a desktop. The standalone Host is searched
  in `/usr/bin`, `/usr/local/bin` and `~/.local/bin`. With no display, the
  example prints the authenticated local Viewer URL for the current session.
- Windows checks FrameViz's MSI and NSIS registry entries and the FrameViz
  directories under Local AppData and Program Files.

Set `FRAMEVIZ_HOST_PATH` or `FRAMEVIZ_TAURI_APP` for an explicitly chosen
runtime. Rebuild previously compiled examples against the updated SDK.

Press Ctrl+C or follow the example's Enter prompts to close its views. A
Host started by the SDK exits after the launching process and its last
client leave. An App you opened yourself stays available until you quit it.
