# Native Ubuntu review of the FrameViz wheel

On an x86_64 Ubuntu 22.04 or 24.04 desktop, sign in to your usual graphical session with an ordinary user account. Download `FrameViz-Linux-Native-Review.zip` and save it in Downloads. The bundle includes the Linux wheel, Python dependencies for both Ubuntu versions, the review script and a test-only observer for WebKitGTK. If your live session lacks virtual environment support or `unzip`, install `python3-venv` or `unzip` through Ubuntu before disconnecting.

On an Intel or AMD Windows PC, a bootable Ubuntu 24.04 LTS Desktop (AMD64) USB and the **Try Ubuntu** session can be used for this review. Save the log somewhere persistent before rebooting. WSL 2 with WSLg or a regular VM can provide an early functional check of install, rendering and interaction. Record it as virtualized evidence and use the live USB or a direct Ubuntu installation for the real GPU and driver check. [Ubuntu USB guide](https://ubuntu.com/desktop/docs/en/latest/how-to/create-a-bootable-usb-stick/) · [Microsoft WSLg guide](https://learn.microsoft.com/en-us/windows/wsl/tutorials/gui-apps).

```bash
cd "$HOME/Downloads"
unzip -q FrameViz-Linux-Native-Review.zip
cd FrameViz-Linux-Native-Review
sha256sum -c SHA256SUMS
python3 -m venv .venv
.venv/bin/python -m pip install --no-index --find-links ./deps ./frameviz-0.5.0-py3-none-linux_x86_64.whl
.venv/bin/python -m pip check
set -o pipefail
env -u WEBKIT_FORCE_SANDBOX -u WEBKIT_DISABLE_SANDBOX_THIS_IS_DANGEROUS \
  -u LIBGL_ALWAYS_SOFTWARE -u WEBKIT_DISABLE_COMPOSITING_MODE \
  -u FRAMEVIZ_TAURI_APP -u FRAMEVIZ_HOST_PATH \
  .venv/bin/python ./verify_linux_desktop.py --webkit-probe ./linux-webkit-probe.so \
  2>&1 | tee frameviz-native-review.log
```

You can disconnect from the network after the installation step. The review uses a fresh local runtime directory and loopback ports. It observes the rendering and sandbox settings without changing them. The observer is used by this test run only.

1. A standalone FrameViz window should show a blue cube. Click the cube. Return to the terminal and press Enter. The terminal should print `PASS native pointer pick`.
2. Drag the red X handle to the right in FrameViz. Return to the terminal and press Enter. The terminal should print `PASS Gizmo move` and a changed X position.
3. Return `frameviz-native-review.log` and, if convenient, a screenshot after the drag. The log records the actual WebGL renderer, DRM devices opened by the native processes, and the WebContext sandbox setting, namespaces and seccomp counts. The current default is `sandbox_enabled=0`. A renderer such as llvmpipe indicates software rendering. If only a generic renderer is available or process details were unreadable, keep those observations in the log.

Keep the log even if a step fails. Include which window or prompt you reached. When recording a hardware graphics pass, require the actual renderer to identify the GPU or its hardware driver.
