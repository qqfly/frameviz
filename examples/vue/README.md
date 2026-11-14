# Vue embedding example

This page places the real `@frameviz/vue` component inside a small application panel. Python populates its scene. Hide/Show actually unmounts/remounts the component; objects are restored from the same running Host.

From the repository root, after installing source dependencies and building the Vue SDK:

```sh
pnpm --filter @frameviz/vue build
pnpm --filter @frameviz/vue exec vite build --config ../../examples/vue/vite.config.mjs
python3 -m http.server 8000 --bind 127.0.0.1 --directory examples/vue/dist
```

In a second terminal, with the Python SDK installed in your environment and a matching App/Host available:

```sh
python examples/vue/open_scene.py
```

The script opens the page with a per-session credential in the URL fragment. It is not printed or embedded in source. Keep the opened URL private. For a custom local HTTP port, pass `--page http://127.0.0.1:PORT/embedded_viewer.html`.

The `viewId` selects the Python-created view. Your application should supply `authToken` from its trusted bootstrap. `autoStartHost=false` makes the page depend on the existing local Host. This example does not implement remote users or Host-restart persistence. The small `window.showcase` object exposes diagnostics for recording the example; it is not an SDK API.

Source: [page](embedded_viewer.html), [Python bootstrap](open_scene.py), [Vue SDK guide](../../packages/frameviz-vue/README.md).

## C++ scene producer

Build the examples as described in [the example index](../README.md). With
the same local Host running and the same Vue page served, run:

```sh
.cache/cpp-examples/bin/vue/open_vue_scene
```

Pass the page URL as the first argument to use another loopback HTTP port.
Both SDK versions display the same objects. Click Hide viewer and Show
viewer to verify restoration, then press Enter to close the scene.
