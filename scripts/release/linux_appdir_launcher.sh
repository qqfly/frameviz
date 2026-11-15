#!/bin/sh
set -eu
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
lib="$root/usr/lib/x86_64-linux-gnu"
# PulseAudio's Jammy libraries have an absolute RUNPATH for their private ABI.
export LD_LIBRARY_PATH="$lib:$root/lib/x86_64-linux-gnu:$lib/pulseaudio"
export WEBKIT_INJECTED_BUNDLE_PATH="$lib/webkit2gtk-4.1/injected-bundle"
export GIO_EXTRA_MODULES="$lib/gio/modules"
export GTK_PATH="$lib/gtk-3.0${GTK_PATH:+:$GTK_PATH}"
export GSETTINGS_SCHEMA_DIR="$root/usr/share/glib-2.0/schemas"
export XDG_DATA_DIRS="$root/usr/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
export GST_PLUGIN_SYSTEM_PATH_1_0="$lib/gstreamer-1.0"
export GST_PLUGIN_SCANNER_1_0="$lib/gstreamer1.0/gstreamer-1.0/gst-plugin-scanner"
export GST_PLUGIN_SCANNER="$GST_PLUGIN_SCANNER_1_0"
export LIBGL_DRIVERS_PATH="$lib/dri"
export __EGL_VENDOR_LIBRARY_DIRS="$root/usr/share/glvnd/egl_vendor.d"
export PATH="$root/bin:$PATH"
cd "$root"
exec "$root/bin/frameviz-real" "$@"
