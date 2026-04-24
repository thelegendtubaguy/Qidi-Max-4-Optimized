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

mode="install"
plain_arg=""
debug_arg=""
dry_run_arg=""
demo_tui_arg=""
yes_arg=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --uninstall)
      if [ "$mode" != "install" ]; then
        echo "Unsupported argument combination." >&2
        exit 1
      fi
      mode="uninstall"
      ;;
    --clear-recovery-sentinel)
      if [ "$mode" != "install" ]; then
        echo "Unsupported argument combination." >&2
        exit 1
      fi
      mode="clear-recovery-sentinel"
      ;;
    --plain)
      plain_arg="--plain"
      ;;
    --debug)
      debug_arg="--debug"
      ;;
    --dry-run)
      dry_run_arg="--dry-run"
      ;;
    --demo-tui)
      demo_tui_arg="--demo-tui"
      ;;
    --yes)
      yes_arg="--yes"
      ;;
    *)
      echo "Unsupported argument: $1" >&2
      exit 1
      ;;
  esac
  shift
done

set -- python3 -I -S installer/runtime/bootstrap.py "$mode"
if [ -n "$plain_arg" ]; then
  set -- "$@" "$plain_arg"
fi
if [ -n "$debug_arg" ]; then
  set -- "$@" "$debug_arg"
fi
if [ -n "$dry_run_arg" ]; then
  set -- "$@" "$dry_run_arg"
fi
if [ -n "$demo_tui_arg" ]; then
  set -- "$@" "$demo_tui_arg"
fi
if [ -n "$yes_arg" ]; then
  set -- "$@" "$yes_arg"
fi
exec "$@"
