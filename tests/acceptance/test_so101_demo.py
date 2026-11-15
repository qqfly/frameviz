"""SO-101 cache contracts and opt-in external-model acceptance."""
import hashlib
import io
import os
from pathlib import Path
import re
import runpy
import xml.etree.ElementTree as ET

import numpy as np
import pytest

from test_python_scene_tree import standalone, tree_viz
from test_widget_browser import widget_pages


@pytest.fixture
def model_cache(monkeypatch):
    root = Path(__file__).resolve().parents[2]
    ensure = runpy.run_path(str(root / "examples/python/04_robotics/extra/so101_model.py"))[
        "ensure_so101_model"
    ]
    files = {
        "LICENSE": b"license",
        "assets/link.stl": b"mesh",
        "so101.xml": b"<mujoco/>",
    }
    downloads = []
    monkeypatch.setitem(ensure.__globals__, "MODEL_FILES", {
        name: (len(data), hashlib.sha256(data).hexdigest())
        for name, data in files.items()
    })

    def fetch(url, *, timeout):
        prefix = ensure.__globals__["MODEL_URL"] + "/"
        assert url.startswith(prefix)
        name = url.removeprefix(prefix)
        downloads.append(name)
        return io.BytesIO(files[name])

    monkeypatch.setitem(ensure.__globals__, "urlopen", fetch)
    return ensure, files, downloads


def test_so101_cache_downloads_once_and_repairs_only_invalid_files(tmp_path, model_cache):
    ensure, files, downloads = model_cache
    model = ensure(tmp_path)
    assert model.name == "so101.xml"
    assert {name: (model.parent / name).read_bytes() for name in files} == files
    assert downloads == list(files)

    downloads.clear()
    assert ensure(tmp_path) == model
    assert downloads == []

    (model.parent / "LICENSE").unlink()
    (model.parent / "assets/link.stl").write_bytes(b"junk")
    assert ensure(tmp_path) == model
    assert downloads == ["LICENSE", "assets/link.stl"]
    assert {name: (model.parent / name).read_bytes() for name in files} == files


def test_so101_cache_rejects_invalid_download_and_can_retry(tmp_path, model_cache):
    ensure, files, downloads = model_cache
    correct_xml = files["so101.xml"]
    files["so101.xml"] = b"corrupted"
    with pytest.raises(RuntimeError, match="so101.xml"):
        ensure(tmp_path)
    assert not list(tmp_path.rglob("so101.xml"))
    assert not list(tmp_path.rglob("*.part"))

    files["so101.xml"] = correct_xml
    downloads.clear()
    assert ensure(tmp_path).read_bytes() == correct_xml
    assert downloads == ["so101.xml"]


def test_so101_cache_reports_progress_and_reuse(tmp_path, model_cache, capsys):
    ensure, _, downloads = model_cache
    model = ensure(tmp_path, show_progress=True)
    progress = capsys.readouterr().err
    assert "[1/3] LICENSE" in progress
    assert "[3/3] so101.xml" in progress
    assert re.search(r"\b100%", progress)
    assert str(model) in progress

    downloads.clear()
    assert ensure(tmp_path, show_progress=True) == model
    assert "Using cached" in capsys.readouterr().err
    assert downloads == []


def test_so101_cache_reports_timeout_before_a_file_exists(tmp_path, model_cache, monkeypatch, capsys):
    ensure, _, _ = model_cache

    def stalled(url, *, timeout):
        raise TimeoutError("timed out")

    monkeypatch.setitem(ensure.__globals__, "urlopen", stalled)
    with pytest.raises(RuntimeError, match="LICENSE.*timed out"):
        ensure(tmp_path, show_progress=True)
    assert "[1/3] LICENSE" in capsys.readouterr().err
    assert not list(tmp_path.rglob("LICENSE"))


@pytest.fixture
def so101(tree_viz, monkeypatch):
    path = os.environ.get("FRAMEVIZ_SO101_MODEL")
    if not path:
        pytest.skip("Set FRAMEVIZ_SO101_MODEL to the external SO-101 MJCF file")
    viz, _ = tree_viz
    directory = Path(__file__).resolve().parents[2] / "examples/python/04_robotics/extra"
    monkeypatch.syspath_prepend(str(directory))
    demo = runpy.run_path(str(directory / "so101_display.py"))
    robot = demo["So101"](viz, path)
    return viz, robot, Path(path), demo


def test_so101_display_follows_mujoco_world_frames(so101):
    mj = pytest.importorskip("mujoco")
    viz, robot, path, demo = so101
    model = mj.MjModel.from_xml_path(str(path))
    data = mj.MjData(model)
    assert len(robot.bodies) == 8
    assert len(robot.geometry) == 20
    assert [joint.name for joint in robot.joints] == [model.joint(i).name for i in range(model.njnt)]

    for values in (np.zeros(model.nq), np.array([.3, -.3, .5, .2, -.4, .8]), model.jnt_range[:, 0]):
        data.qpos[:] = values
        mj.mj_forward(model, data)
        for joint, value in zip(robot.joints, values):
            joint.angle = value
        robot.update()
        for name, handle in robot.bodies.items():
            body = model.body(name).id
            frame = viz.get_transform(handle, space="world", matrix=True)
            matrix = np.array(frame["matrix"]).reshape((4, 4), order="F")
            np.testing.assert_allclose(matrix[:3, 3], data.xpos[body], atol=2e-7)
            np.testing.assert_allclose(matrix[:3, :3], data.xmat[body].reshape(3, 3), atol=2e-7)

    visual = [geom for body in ET.parse(path).iter("body") for geom in body.findall("geom")
              if geom.get("class") == "visual" or geom.get("group") in ("1", "2")]
    reference = np.flatnonzero(np.isin(model.geom_group, (1, 2)))
    assert len(reference) == len(visual) == len(robot.geometry)
    for (body, handle), geom, ref in zip(robot.geometry, visual, reference):
        assert body == model.body(model.geom_bodyid[ref]).name
        frame = viz.get_transform(handle, space="world", matrix=True)
        matrix = np.array(frame["matrix"]).reshape((4, 4), order="F")
        if geom.get("type") != "mesh":
            np.testing.assert_allclose(matrix[:3, 3], data.geom_xpos[ref], atol=2e-7)
            np.testing.assert_allclose(matrix[:3, :3], data.geom_xmat[ref].reshape(3, 3), atol=2e-7)
            continue
        raw, _ = demo["read_stl"](path.parent / "assets" / (geom.attrib["mesh"] + ".stl"))
        mesh = model.geom_dataid[ref]
        start, count = model.mesh_vertadr[mesh], model.mesh_vertnum[mesh]
        compiled = model.mesh_vert[start:start + count]
        actual = raw @ matrix[:3, :3].T + matrix[:3, 3]
        expected = compiled @ data.geom_xmat[ref].reshape(3, 3).T + data.geom_xpos[ref]
        np.testing.assert_allclose(actual.min(axis=0), expected.min(axis=0), atol=2e-7)
        np.testing.assert_allclose(actual.max(axis=0), expected.max(axis=0), atol=2e-7)
        for points, comparison in ((actual, expected), (expected, actual)):
            sample = points[np.linspace(0, len(points) - 1, 12, dtype=int)]
            nearest = np.linalg.norm(sample[:, None] - comparison, axis=2).min(axis=1)
            np.testing.assert_allclose(nearest, 0, atol=2e-7)


def test_real_slider_pick_and_reset_use_scene_handles(so101, widget_pages):
    from playwright.sync_api import expect
    from test_scene_tree_browser import screen, wait_drawable, world

    viz, robot, _, _ = so101
    _, _, (page, second) = widget_pages
    controls = robot.add_controls()
    jaw = robot.bodies["moving_jaw_so101_v1"]
    original = viz.get_transform(jaw, space="world")["quaternion"]
    slider = page.get_by_role("slider", name="gripper (rad) slider")
    expect(slider).to_be_visible()
    bounds = slider.bounding_box()
    y = bounds["y"] + bounds["height"] / 2
    page.mouse.move(bounds["x"] + bounds["width"] * .1, y)
    page.mouse.down()
    page.mouse.move(bounds["x"] + bounds["width"] * .82, y, steps=15)
    desired = float(slider.input_value())
    page.mouse.up()
    commit = viz._client.wait_for_event("widget_changed", timeout=3,
        filter_fn=lambda e: e.get("widget_id") == controls["gripper"] and e.get("phase") == "commit")
    assert commit and commit["value"] == pytest.approx(desired)
    page.wait_for_function("""([handle, start]) => {
      const frame = window.__FRAMEVIZ_CORE__.frames.get(handle);
      const q = frame.getWorldQuaternion(frame.quaternion.clone());
      return Math.abs(q.dot(q.clone().fromArray(start))) < .99;
    }""", arg=[jaw, original])
    assert desired > .8
    assert viz.get_widget_value(controls["gripper"]) == pytest.approx(desired)

    base_geometry = next(handle for body, handle in robot.geometry if body == "base")
    wait_drawable(page, base_geometry)
    page.mouse.click(*screen(page, world(page, base_geometry)))
    picked = viz._client.wait_for_event("picked", timeout=3)
    assert picked and picked["name"] == "base"

    page.get_by_role("button", name="Reset pose").click()
    expect(second.get_by_role("spinbutton", name="gripper (rad)")).to_have_value("0")
    page.wait_for_function("""([handle, start]) => {
      const frame = window.__FRAMEVIZ_CORE__.frames.get(handle);
      const q = frame.getWorldQuaternion(frame.quaternion.clone());
      return Math.abs(q.dot(q.clone().fromArray(start))) > .999999;
    }""", arg=[jaw, original])
    assert all(joint.angle == 0 for joint in robot.joints)
