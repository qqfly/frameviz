"""Serialize a renderer capture as a browser-only lesson."""
from __future__ import annotations

import json
import math
from pathlib import Path
import re

from ._capture import _capture_view, _with_page
from ._scene_tree import rigid_pose

_HTML = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; script-src 'unsafe-inline'; style-src 'unsafe-inline'; img-src data: blob:">
<title>FrameViz tutorial</title>
<style>
html, body { margin: 0; height: 100%; }
body { display: flex; flex-direction: column; color: #18212d; font: 14px system-ui, sans-serif; }
#viewer { position: relative; flex: 1; min-height: 0; overflow: hidden; }
#overlay { position: absolute; inset: 0; pointer-events: none; }
#status { position: absolute; top: 12px; left: 12px; z-index: 1; margin: 0; }
#player:not([hidden]) { display: flex; align-items: center; gap: 12px; padding: 8px 12px; background: #eef2f5; }
#seek { flex: 1; min-width: 4rem; }
#time { font-variant-numeric: tabular-nums; }
</style>
</head>
<body>
<main id="viewer"><div id="overlay"></div></main>
<p id="status" role="status">Loading 3D scene…</p>
<div id="player" hidden>
<button id="play" type="button">Play</button>
<input id="seek" type="range" min="0" step="0.001" value="0" aria-label="Animation progress">
<output id="time"></output>
</div>
<script id="frameviz-data" type="application/json">__DATA__</script>
<script>__SCRIPT__</script>
</body>
</html>
"""


def _animation_tracks(animation):
    if animation is None:
        return {}
    if not isinstance(animation, dict):
        raise ValueError("animation must map object IDs to keyframes")
    tracks = {}
    for handle, keys in animation.items():
        if not isinstance(handle, str) or not handle or not isinstance(keys, (list, tuple)) or not keys:
            raise ValueError("Each animation track needs an object ID and at least one keyframe")
        track = []
        previous = -1.0
        for key in keys:
            if not isinstance(key, dict) or key.get("pose") is None:
                raise ValueError("Each keyframe needs time and a rigid pose")
            time = key.get("time")
            if (isinstance(time, bool) or not isinstance(time, (int, float))
                    or not math.isfinite(time) or time < 0 or time <= previous):
                raise ValueError("Animation times must be finite, nonnegative and strictly increasing")
            track.append({"time": time, "pose": rigid_pose(key["pose"])})
            previous = time
        tracks[handle] = track
    return tracks


def export_html(viz, path, *, animation=None):
    tracks = _animation_tracks(animation)

    def read_tutorial(page):
        return page.evaluate("""async () => {
            const snapshot = window.__FRAMEVIZ_CORE__.prepareTutorialSnapshot(window.__FRAMEVIZ_CAPTURE_SNAPSHOT__);
            const script = await fetch(new URL('./tutorial.js', location.href), {redirect: 'error'});
            if (!script.ok) throw new Error('The installed runtime does not contain the tutorial player');
            return {snapshot, script: await script.text()};
        }""")

    with _capture_view(viz) as (url, token, w, h):
        result = _with_page(url, token, w, h, read_tutorial)
    handles = {item["handle"] for item in result["snapshot"]["objects"]}
    missing = tracks.keys() - handles
    if missing:
        raise ValueError("Animation tracks refer to missing objects: " + ", ".join(sorted(missing)))
    data = json.dumps({"snapshot": result["snapshot"], "animation": tracks},
                      ensure_ascii=True, allow_nan=False, separators=(",", ":")).replace("<", "\\u003c")
    script = re.sub(r"</script", lambda match: r"<\/" + match.group()[2:],
                    result["script"], flags=re.IGNORECASE)
    # Substitute in one pass so scene text resembling a marker stays data.
    parts = {"__DATA__": data, "__SCRIPT__": script}
    html = re.sub(r"__DATA__|__SCRIPT__", lambda match: parts[match.group()], _HTML)
    Path(path).write_text(html, encoding="utf-8")
