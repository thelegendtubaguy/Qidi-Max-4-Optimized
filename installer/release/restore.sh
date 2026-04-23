#!/bin/sh
set -eu

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd "$SCRIPT_DIR"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Missing required tool: python3" >&2
  exit 1
fi

plain_arg=""
debug_arg=""
backup_path=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --plain)
      plain_arg="--plain"
      ;;
    --debug)
      debug_arg="--debug"
      ;;
    --backup)
      shift
      if [ "$#" -eq 0 ]; then
        echo "Missing value for --backup." >&2
        exit 1
      fi
      backup_path="$1"
      ;;
    *)
      echo "Unsupported argument: $1" >&2
      exit 1
      ;;
  esac
  shift
done

set -- python3 -I -S installer/runtime/bootstrap.py restore-backup
if [ -n "$plain_arg" ]; then
  set -- "$@" "$plain_arg"
fi
if [ -n "$debug_arg" ]; then
  set -- "$@" "$debug_arg"
fi
if [ -n "$backup_path" ]; then
  set -- "$@" --backup "$backup_path"
fi
exec "$@"
