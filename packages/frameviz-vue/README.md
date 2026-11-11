# FrameViz Vue

Build `@frameviz/protocol`, `@frameviz/core`, and `@frameviz/vue` from the same 0.5.0 source. Use locally packed SDK tarballs until public package publication is approved.

```vue
<FrameVizViewer name="main" :auth-token="sessionToken" />
```

Provide a Host session credential from your application's trusted local bootstrap. Each component owns a scoped connection and core; unmount clears timers, pending requests, listeners, renderer resources, and the socket. Reconnection restores process-local Host state. This is not remote multi-user authorization or persistence across Host restart.


## Scene controls

`FrameVizViewer` keeps the Host's scene controls hidden by default so an
application can use its own UI. Pass `:show-widget-panel="true"` to render the
shared controls. Scene control reads, writes and events work with either setting.
The Host can hide the panel for a specific View through its view configuration.
