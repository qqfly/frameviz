"""Exercise Host-owned rigid frames in two actual Viewer pages."""
import base64
import math
import os
import struct

import pytest

from frameviz.client import FrameVizClient
from frameviz.viz import Viz
from test_standalone_viewer import standalone


def frames(page):
    page.evaluate("() => new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")


def world(page, handle):
    return page.evaluate(
        "h => {const o=window.__FRAMEVIZ_CORE__.objects.get(h);return o.getWorldPosition(o.position.clone()).toArray();}",
        handle,
    )


def screen(page, point):
    return page.evaluate("""point => {
      const m=window.__FRAMEVIZ_CORE__.getSceneManager();
      const rect=m.renderer.domElement.getBoundingClientRect();
      const p=m.camera.position.clone().fromArray(point).project(m.camera);
      return [rect.x+(p.x+1)*rect.width/2,rect.y+(1-p.y)*rect.height/2];
    }""", point)


def wait_drawable(page, handle):
    page.wait_for_function("h => window.__FRAMEVIZ_CORE__?.objects.has(h)", arg=handle)
    frames(page)


def test_rigid_frames_drag_pick_reload_and_independent_cameras(standalone):
    from playwright.sync_api import sync_playwright

    info, *_ = standalone
    client = FrameVizClient(info["ws_url"], token=info["token"])
    client.connect()
    scene = {"scene_id": "hierarchy"}
    def command(command_name, **args):
        return client.send_command(command_name, args)

    try:
        a = command("create_view", **scene)["view_id"]
        b = command("create_view", **scene)["view_id"]
        first, second = (Viz(client, scene["scene_id"], view, owns_view=False) for view in (a, b))
        s = math.sqrt(0.5)
        parent = command(
            "add_primitive", **scene, type="box", params={"size": [0.25, 0.25, 0.25]},
            pose=[0, 0, 0, 0, 0, s, s], geometry_scale=[4, 1, 1],
            name="rotating parent", tags={"source": "fixture"},
        )["handle"]
        child = command(
            "add_primitive", **scene, type="box", params={"size": [0.6, 0.6, 0.6]},
            parent=parent, pose=[2, 0, 0, 0, 0, 0, 1], name="child",
        )["handle"]
        with sync_playwright() as pw:
            options = {"headless": True, "args": [
                "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
            ]}
            if os.environ.get("FRAMEVIZ_TEST_CHROME"):
                options["executable_path"] = os.environ["FRAMEVIZ_TEST_CHROME"]
            browser = pw.chromium.launch(**options)
            errors = []
            try:
                pages = [browser.new_page(viewport={"width": 920, "height": 660}) for _ in (a, b)]
                for page, view in zip(pages, (a, b)):
                    page.on("pageerror", lambda error: errors.append(str(error)))
                    page.goto(f"{info['viewer_url']}?view_id={view}&ws_port={info['port']}#token={info['token']}")
                    wait_drawable(page, child)
                    assert world(page, child) == pytest.approx([0, 2, 0], abs=1e-7)

                p, q = pages
                first.set_camera_pose((0, -7, 6), (0, 1, 0), up=(0, 0, 1))
                second.set_camera_pose((6, -8, 4), (0, 1, 0), up=(0, 0, 1))
                first.set_camera_controls(fov=42)
                second.set_camera_controls(fov=57)
                first.set_pick_config(enabled=True, mode="object", button=0, ctrl_modifier=False)
                frames(p)
                frames(q)
                assert first.get_camera_pose()["eye"] == pytest.approx([0, -7, 6])
                assert second.get_camera_pose()["eye"] == pytest.approx([6, -8, 4])
                assert p.evaluate("window.__FRAMEVIZ_CORE__.getSceneManager().camera.fov") == 42
                assert q.evaluate("window.__FRAMEVIZ_CORE__.getSceneManager().camera.fov") == 57

                p.mouse.click(*screen(p, world(p, child)))
                picked = client.wait_for_event("picked", timeout=3, filter_fn=lambda d: d.get("handle") == child)
                assert picked and picked["name"] == "child"
                assert picked["ancestors"] == [
                    {"handle": parent, "name": "rotating parent", "tags": {"source": "fixture"}},
                ]

                first.attach_gizmo(child, mask=1)
                foreign = command("add_primitive", scene_id="foreign-gizmo", type="box")["handle"]
                for handle, error in (("missing", "ERR_NOT_FOUND"), (foreign, "ERR_INVALID_SCOPE")):
                    with pytest.raises(RuntimeError, match=error):
                        first.attach_gizmo(handle, mask=1)
                frames(p)
                assert p.evaluate("window.__FRAMEVIZ_CORE__.gizmoManager.getAttachedHandle()") == child
                x, y = p.evaluate("""() => {
                  const c=window.__FRAMEVIZ_CORE__,m=c.getSceneManager();
                  const rect=m.renderer.domElement.getBoundingClientRect();
                  const locations=[];
                  c.gizmoManager.controls._gizmo.picker.traverse(o=>{
                    if(o.name==='TR_X'&&o.geometry){
                      o.geometry.computeBoundingBox();
                      const v=o.geometry.boundingBox.getCenter(o.position.clone()).applyMatrix4(o.matrixWorld).project(m.camera);
                      locations.push([rect.x+(v.x+1)*rect.width/2,rect.y+(1-v.y)*rect.height/2]);
                    }
                  });
                  return locations.sort((a,b)=>b[0]-a[0])[0];
                }""")
                origin = world(p, child)
                start_screen = screen(p, origin)
                # The parent's 90-degree Z rotation maps the child's local X onto world Y.
                tip_screen = screen(p, [origin[0], origin[1] + 1, origin[2]])
                dx, dy = (b - a for a, b in zip(start_screen, tip_screen))
                length = math.hypot(dx, dy)
                p.mouse.move(x, y)
                p.mouse.down()
                p.mouse.move(x + 65 * dx / length, y + 65 * dy / length, steps=12)
                p.mouse.up()
                transformed = client.wait_for_event("transformed", timeout=3, filter_fn=lambda d: d.get("handle") == child)
                assert transformed
                lx, ly, lz = transformed["local_transform"]["position"]
                assert transformed["world_transform"]["position"] == pytest.approx([-ly, lx, lz])
                frames(p)
                after = command("get_transform", handle=child, space="world")["transform"]["position"]
                assert math.dist(after, [0, 2, 0]) > .1
                assert [after[0], after[2]] == pytest.approx([0, 0], abs=1e-6)
                for page in pages:
                    page.wait_for_function("""([h, p]) => {
                      const o=window.__FRAMEVIZ_CORE__.objects.get(h);
                      return o && o.getWorldPosition(o.position.clone()).distanceTo(o.position.clone().fromArray(p)) < 1e-6;
                    }""", arg=[child, after])
                first.detach_gizmo()
                command("set_parent", handle=child, parent=None)
                q.reload()
                wait_drawable(q, child)
                assert world(q, child) == pytest.approx(after)
                assert second.get_camera_pose()["eye"] == pytest.approx([6, -8, 4])
                assert q.evaluate("window.__FRAMEVIZ_CORE__.getSceneManager().camera.fov") == 57
                assert not errors
            finally:
                browser.close()
    finally:
        client.close()


def test_point_pick_reports_global_index_for_second_render_chunk(standalone):
    from playwright.sync_api import sync_playwright

    info, *_ = standalone
    client = FrameVizClient(info["ws_url"], token=info["token"])
    client.connect()
    try:
        view = client.send_command("create_view", {})
        viz = Viz(client, view["scene_id"], view["view_id"], owns_view=False)
        chunks = []
        for row in ((-2, 0, 0, -1, 0, 0), (1, 0, 0, 2, 0, 0)):
            binary = struct.pack("<6f", *row)
            args = {"dtype": "f32", "shape": [2, 3]}
            buffer_id = client.send_command("create_buffer", {"size_bytes": len(binary), **args})["buffer_id"]
            client.send_command("upload_buffer_chunk", {
                "buffer_id": buffer_id, "offset_bytes": 0, "chunk_bytes": len(binary),
                "data_base64": base64.b64encode(binary).decode(),
            })
            chunks.append({"positions": {"buffer_id": buffer_id, **args}})
        handle = client.send_command("add_points", {
            "scene_id": view["scene_id"], "chunks": chunks, "size": 11,
        })["handle"]
        assert [item["handle"] for item in viz.list_objects()] == [handle]
        with sync_playwright() as pw:
            options = {"headless": True, "args": [
                "--use-gl=angle", "--use-angle=swiftshader", "--enable-unsafe-swiftshader",
            ]}
            if os.environ.get("FRAMEVIZ_TEST_CHROME"):
                options["executable_path"] = os.environ["FRAMEVIZ_TEST_CHROME"]
            browser = pw.chromium.launch(**options)
            try:
                page = browser.new_page(viewport={"width": 920, "height": 660})
                page.goto(f"{info['viewer_url']}?view_id={view['view_id']}&ws_port={info['port']}#token={info['token']}")
                wait_drawable(page, handle)
                viz.set_camera_pose((0, -8, 5), (0, 0, 0), up=(0, 0, 1))
                viz.set_pick_config(enabled=True, mode="point", button=0, ctrl_modifier=False, point_threshold=.08)
                frames(page)
                page.mouse.click(*screen(page, [2, 0, 0]))
                picked = client.wait_for_event("picked", timeout=3, filter_fn=lambda d: d.get("handle") == handle)
                assert picked and picked["hit_type"] == "point"
                assert picked["point_index"] == 3
                assert picked["point_world"] == pytest.approx([2, 0, 0])
                sizes = "h => window.__FRAMEVIZ_CORE__.objects.get(h).children.map(c => c.material.size)"
                base = page.evaluate(sizes, handle)
                viz.set_pick_config(enabled=True, mode="object", button=0, ctrl_modifier=False, point_threshold=.08)
                frames(page)
                page.mouse.click(*screen(page, [2, 0, 0]))
                selected = client.wait_for_event("picked", timeout=3, filter_fn=lambda d: d.get("handle") == handle)
                assert selected["point_index"] == 3
                assert page.evaluate(sizes, handle) == [size * 1.5 for size in base]
                viz.clear_pick_highlight()
                frames(page)
                assert page.evaluate(sizes, handle) == base
            finally:
                browser.close()
    finally:
        client.close()
