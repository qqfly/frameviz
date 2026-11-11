# Compatibility

Host, SDK and Viewer are compatible within one **major.minor** protocol series: for example, `0.5.0` and `0.5.9` interoperate. Patch releases must preserve commands and their semantics. A different major or minor is rejected before a command can change state. The error identifies which side to upgrade: an older Host requires a runtime upgrade, and an older SDK/Viewer requires a client upgrade.

Versions use canonical `major.minor.patch` numeric strings, with each component at most nine digits. Missing values, leading zeroes, prerelease/build suffixes and malformed values are rejected. The discovery record keeps the exact Host version, while discovery reuse and authentication use the same series rule. A live but incompatible Host's discovery file is preserved; it is not stale merely because its version differs.

Package version fields follow `version.json`; the minimum compatible version is the start of the current series (`major.minor.0`). Public Python/npm package names and a remote repository URL are not reserved by this source tree.

Scenes and views recover across viewer reconnects only while the same Host is alive. The revision is a Host-wide state sequence; equal revisions or gaps across different scenes are not a per-stream loss detector. Host restart persistence and full interaction-state persistence are not implemented.

A single buffer is limited to 256 MiB, total buffer storage to 512 MiB, and upload chunks to 16 MiB. The viewer transport uses self-describing base64 chunks. Shared memory is disabled with an explicit unsupported error. These limits do not provide a complete budget for every model, texture, object, event, and zero-byte allocation.

C++ synchronous query replies have a separate bounded inbox, consumed by correlation ID. Ordinary subscribed events still require polling/consumption. A disconnected or unavailable viewer must not be replaced by fabricated camera/pick results. Model cancellation prevents resurrection of removed objects; it does not promise that every underlying download is aborted.

Default state is under `~/.local/share/qqfly/frameviz` on macOS/Linux and `%LOCALAPPDATA%/qqfly/FrameViz` on Windows. `FRAMEVIZ_HOME` selects an explicit state root, and `FRAMEVIZ_DISCOVERY_PATH`, `FRAMEVIZ_LOG_DIR`, and `FRAMEVIZ_RUNTIME_MANIFEST` override individual paths. Template Python uses `FRAMEVIZ_PYTHON`, then PATH. No internal interpreter or tool installation is searched.

Automatic startup uses an explicit executable (`FRAMEVIZ_HOST_PATH` / `FRAMEVIZ_TAURI_APP`), a known platform installation, or a binary built in this source tree. macOS searches the validated FrameViz application bundle in the user/system Applications directories. Linux checks the `.deb` executable `/usr/bin/frameviz` before source builds, and requires an executable file. Arbitrary commands named `frameviz` in `PATH` and global macOS application names are not searched. See [installation](INSTALLATION.md#linux-runtime-discovery).

## Python callback execution

After authentication, Python clients dispatch callbacks serially on a dedicated background thread, separate from WebSocket reception. Callbacks may issue synchronous SDK commands and correlated Viewer queries. `FrameVizClient(auto_events=False)`, `fv.open(auto_events=False)` and `fv.connect(auto_events=False)` select the existing manual polling path. In automatic mode `poll_events()` does not take work away from the callback thread; `spin()` keeps the caller alive. Handler registration/removal is safe across these threads; a handler list is captured for each dispatched event.

`wait_for_event` does not execute callbacks on the receiving thread or steal work from automatic dispatch. Correlated query results remain separate. Automatic mode retains up to the latest 4096 ordinary event observations for synchronous waits; matching waits consume observations, while callback delivery still occurs once through its own bounded queue. Waiting is not a recording API. Filters run in the waiting caller, outside internal locks. Manual mode preserves queue-driven waiting and polling.

Closing stops new callback dispatch and wakes pending waits. Closing within a callback is supported. A callback already executing cannot be forcibly interrupted; a reconnect is refused while a prior callback thread is still running. Application state shared with callbacks needs the application's own synchronization.

A Python callback exception writes its complete traceback to standard error and does not stop later handlers/events. Closing during a callback stops any remaining callbacks for that event and subsequent queued events. Application-requested shutdown takes precedence over continuing dispatch.

`viz.keep_running()` keeps a standalone Python script alive until the connection closes or Ctrl+C is pressed, then closes that Viz and its connection. Automatic callbacks stay on the dispatcher; `auto_events=False` uses manual dispatch in the calling thread. Closing a browser tab does not itself terminate the Host session. `spin()` remains available for applications managing their own cleanup.
