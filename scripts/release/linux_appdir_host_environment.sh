# Keep this list in step with the variables set by linux_appdir_launcher.sh.
frameviz_runtime_variables='LD_LIBRARY_PATH WEBKIT_INJECTED_BUNDLE_PATH
    GIO_EXTRA_MODULES GTK_PATH GSETTINGS_SCHEMA_DIR XDG_DATA_DIRS
    GST_PLUGIN_SYSTEM_PATH_1_0 GST_PLUGIN_SCANNER_1_0 GST_PLUGIN_SCANNER
    LIBGL_DRIVERS_PATH __EGL_VENDOR_LIBRARY_DIRS PATH'

save_frameviz_host_environment() {
    for name in $frameviz_runtime_variables; do
        saved=FRAMEVIZ_APPDIR_HOST_$name
        # Only the fixed variable names above are interpolated into shell code.
        eval "present=\${$name+x}; value=\${$name-}"
        if [ -n "$present" ]; then
            export "$saved=$value"
        else
            unset "$saved"
        fi
    done
    export FRAMEVIZ_APPDIR_HOST_CWD="$(pwd -P)"
}

restore_frameviz_host_environment() {
    for name in $frameviz_runtime_variables; do
        saved=FRAMEVIZ_APPDIR_HOST_$name
        eval "present=\${$saved+x}; value=\${$saved-}"
        if [ -n "$present" ]; then
            export "$name=$value"
        else
            unset "$name"
        fi
        unset "$saved"
    done
    # The caller's directory may disappear after the managed Host starts.
    CDPATH= cd -- "$FRAMEVIZ_APPDIR_HOST_CWD" 2>/dev/null || :
    unset FRAMEVIZ_APPDIR_HOST_CWD
}
