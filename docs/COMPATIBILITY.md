# Compatibility

Protocol 0.4.0 is the only supported Host/SDK/viewer combination. Package version fields follow `version.json`; mixed installations, missing command versions, and unsupported versions are rejected. Public Python/npm package names and a remote repository URL are not reserved by this source tree.

Scenes and views recover across viewer reconnects only while the same Host is alive. The revision is a Host-wide state sequence; equal revisions or gaps across different scenes are not a per-stream loss detector. Host restart persistence and full interaction-state persistence are not implemented.

A single buffer is limited to 256 MiB, total buffer storage to 512 MiB, and upload chunks to 16 MiB. The viewer transport uses self-describing base64 chunks. Shared memory is disabled with an explicit unsupported error. These limits do not provide a complete budget for every model, texture, object, event, and zero-byte allocation.

C++ synchronous query replies have a separate bounded inbox, consumed by correlation ID. Ordinary subscribed events still require polling/consumption. A disconnected or unavailable viewer must not be replaced by fabricated camera/pick results. Model cancellation prevents resurrection of removed objects; it does not promise that every underlying download is aborted.

Default state is under `~/.local/share/qqfly/frameviz` on macOS/Linux and `%LOCALAPPDATA%/qqfly/FrameViz` on Windows. `FRAMEVIZ_HOME` selects an explicit state root, and `FRAMEVIZ_DISCOVERY_PATH`, `FRAMEVIZ_LOG_DIR`, and `FRAMEVIZ_RUNTIME_MANIFEST` override individual paths. Template Python uses `FRAMEVIZ_PYTHON`, then PATH. No internal interpreter or tool installation is searched.

Automatic startup uses only an explicit executable (`FRAMEVIZ_HOST_PATH` / `FRAMEVIZ_TAURI_APP`) or a binary built in this source tree. Generic PATH/system application locations are not guessed, so an unrelated installation is not launched.
