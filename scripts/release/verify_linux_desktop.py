#!/usr/bin/env python3
"""Verify an installed Linux FrameViz wheel in an isolated local desktop session."""

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import socket
from tempfile import TemporaryDirectory
import time
import webbrowser


def local_ports():
    with socket.socket() as ws, socket.socket() as control:
        ws.bind(("127.0.0.1", 0))
        control.bind(("127.0.0.1", 0))
        return ws.getsockname()[1], control.getsockname()[1]


def read_link(path):
    try:
        return os.readlink(path)
    except OSError:
        return None


def status(process):
    try:
        return dict(line.split(":\t", 1) for line in (process / "status").read_text().splitlines()
                    if ":\t" in line)
    except OSError:
        return {}


def process_name(path, fallback):
    try:
        # The kernel executable can be the emulator for translated Linux binaries.
        name = (path / "cmdline").read_bytes().split(b"\0", 1)[0].decode(errors="replace")
    except OSError:
        name = read_link(path / "exe")
    return Path(name).name if name else fallback


def process_evidence(host_pid):
    proc = Path("/proc")
    processes = {}
    for path in proc.iterdir():
        if path.name.isdigit() and (info := status(path)) and "PPid" in info:
            processes[int(path.name)] = info
    children = {host_pid} & processes.keys()
    while True:
        family = children | {pid for pid, info in processes.items() if int(info["PPid"]) in children}
        if family == children:
            break
        children = family

    rows = []
    for pid in sorted(children):
        path = proc / str(pid)
        info = processes[pid]
        try:
            gpu_devices = sorted({target for fd in (path / "fd").iterdir()
                                  if (target := read_link(fd)) and target.startswith("/dev/dri/")})
        except OSError:
            gpu_devices = None
        rows.append({"pid": pid, "ppid": int(info["PPid"]),
                     "name": process_name(path, info.get("Name")),
                     "namespaces": {name: read_link(path / "ns" / name)
                                    for name in ("mnt", "pid", "user", "net")},
                     "seccomp_mode": info.get("Seccomp"), "seccomp_filters": info.get("Seccomp_filters"),
                     "namespace_pids": info.get("NSpid"), "open_drm_devices": gpu_devices})
    return rows


def viewer_log(host):
    path = host._started_host_log_path
    if path:
        # Other Host log lines can contain private session values.
        for line in Path(path).read_text(errors="replace").splitlines():
            if line.startswith("[FrameViz QA] "):
                print(line, flush=True)


def fail_browser(*args, **kwargs):
    raise RuntimeError("This check requires the packaged native window")


def picked_box(viz, box):
    for _ in range(20):
        if viz.get_picked_info()["handle"] == box:
            return True
        time.sleep(.05)
    return False


def box_position_after_drag(viz, box):
    for _ in range(20):
        position = viz.get_transform(box)["position"]
        if abs(position[0]) >= .05:
            break
        time.sleep(.05)
    return position


def run(args, root):
    import frameviz as fv
    from frameviz import host

    ws, control = local_ports()
    os.environ.update(FRAMEVIZ_HOME=str(root / "state"), XDG_CACHE_HOME=str(root / "cache"),
                      FRAMEVIZ_HOST=f"ws://127.0.0.1:{ws}", FRAMEVIZ_TAURI_CONTROL_PORT=str(control))
    sandbox_overrides = {name: os.environ.get(name) for name in
                         ("WEBKIT_FORCE_SANDBOX", "WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS")}
    if args.webkit_probe:
        probe = str(root / "webkit-observer.so")
        shutil.copyfile(args.webkit_probe, probe)
        os.environ["LD_PRELOAD"] = " ".join(filter(None, (probe, os.environ.get("LD_PRELOAD"))))
    print(json.dumps({"arch": platform.machine(), "glibc": platform.libc_ver(),
                      "distribution": platform.freedesktop_os_release().get("PRETTY_NAME"),
                      "wayland": bool(os.environ.get("WAYLAND_DISPLAY")),
                      "x11": bool(os.environ.get("DISPLAY")), "uid": os.getuid(),
                      "session_type": os.environ.get("XDG_SESSION_TYPE"),
                      "sandbox_env": sandbox_overrides}), flush=True)
    webbrowser.open = fail_browser
    viz = None
    try:
        viz = fv.open(title="FrameViz packaged native review", width=800, height=600, timeout=30)
        if not viz._opened_via_tauri or not viz.wait_for_viewer():
            raise RuntimeError("Expected the wheel's native Tauri Viewer")
        proc = host._started_host_proc
        if not proc or not Path(proc.args[0]).is_relative_to(root / "cache"):
            raise RuntimeError("Expected the wheel's own extracted desktop runtime")
        box = viz.add_box(size=[.45, .45, .45], color="#4078da")
        viz.set_camera_pose(eye=[0, -5, 0], target=[0, 0, 0], up=[0, 0, 1])
        viz.set_view_config(show_axes=False, show_grid=False)
        viz.set_pick_config(enabled=True, mode="object", button=0, ctrl_modifier=False)
        print("PASS packaged Tauri Viewer connected", flush=True)
        if not args.diagnostics_only:
            input("Click the blue box in FrameViz, then return here and press Enter. ")
            if not picked_box(viz, box):
                raise RuntimeError("The blue box was not picked")
            print("PASS native pointer pick", flush=True)
            viz.attach_gizmo(box, size=1.2, mask=1, scale_mode="world")
            input("Drag the red X handle right, then return here and press Enter. ")
            position = box_position_after_drag(viz, box)
            if abs(position[0]) < .05:
                raise RuntimeError(f"The Gizmo did not move the box on X: {position}")
            print(f"PASS Gizmo move {position}", flush=True)
        else:
            time.sleep(1)
        evidence = process_evidence(proc.pid)
        print(json.dumps({"host_pid": proc.pid, "native_processes": evidence}, indent=2), flush=True)
        if not any((row["name"] or "").startswith("WebKitWebProces") for row in evidence):
            raise RuntimeError("No WebKit WebProcess appeared in the packaged Host's process tree")
    finally:
        viewer_log(host)
        if viz is not None:
            viz.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--webkit-probe", type=Path, help="Optional test-only WebKitGTK probe .so")
    parser.add_argument("--diagnostics-only", action="store_true", help="Skip manual pointer checks")
    args = parser.parse_args()
    if os.geteuid() == 0:
        parser.error("Run as your ordinary desktop user")
    with TemporaryDirectory(prefix="frameviz-native-review-") as directory:
        run(args, Path(directory))


if __name__ == "__main__":
    main()
