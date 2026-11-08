# Architecture

> Version: v0.4.0

FrameViz separates command ownership from rendering. The Rust Host owns scenes, views, objects, uploaded buffers, and authoritative mutations. SDKs send versioned commands and receive responses/events. Web, Vue, and native shells render the same scene contract through the TypeScript core.

| Component | Responsibility | Boundary |
|---|---|---|
| frameviz-protocol | Envelope constants, schemas, validation | Wire compatibility, not rendering |
| frameviz-server | Authentication, routing, state, uploads | Loopback; one authoritative process |
| frameviz-core | Three.js geometry, model loading, camera, picking, Gizmo | Browser and GPU lifecycle |
| frameviz-py / frameviz-cpp | Synchronous client API and event correlation | Transport errors remain errors |
| frameviz-vue | One scoped connection/core per component | Timers and connections end on unmount |
| frameviz-web-viewer | Standalone authenticated browser shell | Bundled assets; no runtime CDN |
| frameviz-host-tauri | Native shell and local control | Separate native-platform acceptance |

Views select scenes; multiple authenticated viewer connections may mirror a view. Camera and interaction state belong to a view, while object transforms belong to a scene. Rebinding restores every allowed mirror. Host mutations validate before sync; failed display batches leave business state and revision unchanged. Diagnostic logs may still record failed requests.

Object and buffer identifiers are process-scoped. Referenced buffers are immutable; geometry updates upload replacement buffers. The last object reference releases replaced or removed data. Async model handles can exist before geometry is ready, and expose readiness/failure events.

The current Host and core contain large command dispatchers. Avoid broad rewrites while stabilizing this contract; extract validation, routing, buffer ownership, and lifecycle modules behind contract tests. Their size remains an architecture maintenance concern, not evidence of missing runtime tests.
