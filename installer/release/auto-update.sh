#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

for tool in python3; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing required tool: $tool" >&2
    exit 1
  fi
done

plain_arg="--plain"
debug_arg=""
mode=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --run)
      if [ -n "$mode" ]; then
        echo "Unsupported argument combination." >&2
        exit 1
      fi
      mode="auto-update-check"
      ;;
    --enable-systemd)
      if [ -n "$mode" ]; then
        echo "Unsupported argument combination." >&2
        exit 1
      fi
      mode="enable-auto-updates"
      ;;
    --disable-systemd)
      if [ -n "$mode" ]; then
        echo "Unsupported argument combination." >&2
        exit 1
      fi
      mode="disable-auto-updates"
      ;;
    --debug)
      debug_arg="--debug"
      ;;
    *)
      echo "Unsupported argument: $1" >&2
      exit 1
      ;;
  esac
  shift
done

if [ -z "$mode" ]; then
  echo "Usage: $0 --run|--enable-systemd|--disable-systemd [--debug]" >&2
  exit 1
fi

set -- python3 -I -S installer/runtime/bootstrap.py "$mode" "$plain_arg"
if [ -n "$debug_arg" ]; then
  set -- "$@" "$debug_arg"
fi
exec "$@"
