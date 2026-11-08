#!/bin/bash
# This file is sourced, not executed directly.

section() {
  echo
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "$1"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
}

note() {
  echo "[${LOG_PREFIX}] $1"
}

warn() {
  echo "[${LOG_PREFIX}][WARN] $1" >&2
}

fail() {
  echo "[${LOG_PREFIX}][ERROR] $1" >&2
  exit 1
}
