#!/bin/sh
set -eu
# Use shell builtins here so the first external executable sees the host environment.
case "$0" in */*) bin=${0%/*} ;; *) bin=. ;; esac
libexec=$(CDPATH= cd -- "$bin/../libexec" && pwd -P)
. "$libexec/frameviz-host-environment.sh"
if [ "${FRAMEVIZ_APPDIR_HOST_CWD+x}" = x ]; then
    restore_frameviz_host_environment
fi
exec "$libexec/xdg-open" "$@"
