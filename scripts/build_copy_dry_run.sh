#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/build_copy_dry_run.sh --host <printer-host> [--user <ssh-user>] [--password <ssh-password>] [--debug] [--no-smoke-test]

Environment:
  PRINTER_HOST       Printer hostname or IP. Required if --host is not passed.
  PRINTER_USER       SSH user. Default: qidi
  PRINTER_PASSWORD   SSH password. Optional. Requires sshpass when set.
  BUILD_ID           Dev bundle build id. Default: local

This script:
  1. Builds dist/tltg-optimized-macros-dev.tar.gz
  2. Copies it to the printer home directory
  3. Extracts ~/tltg-optimized-macros on the printer
  4. Runs ./install.sh --dry-run --plain
EOF
}

die() {
  printf '%s\n' "$1" >&2
  exit 1
}

require_value() {
  local flag="$1"
  local value="${2-}"
  [ -n "$value" ] || die "Missing value for $flag"
}

SCRIPT_DIR=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
REPO_ROOT=$(CDPATH= cd -- "$SCRIPT_DIR/.." && pwd)

PRINTER_HOST=${PRINTER_HOST:-}
PRINTER_USER=${PRINTER_USER:-qidi}
PRINTER_PASSWORD=${PRINTER_PASSWORD:-}
BUILD_ID=${BUILD_ID:-local}
DEBUG_INSTALL=0
SMOKE_TEST=1

while [ "$#" -gt 0 ]; do
  case "$1" in
    --host)
      shift
      require_value "--host" "${1-}"
      PRINTER_HOST="$1"
      ;;
    --user)
      shift
      require_value "--user" "${1-}"
      PRINTER_USER="$1"
      ;;
    --password)
      shift
      require_value "--password" "${1-}"
      PRINTER_PASSWORD="$1"
      ;;
    --build-id)
      shift
      require_value "--build-id" "${1-}"
      BUILD_ID="$1"
      ;;
    --debug)
      DEBUG_INSTALL=1
      ;;
    --no-smoke-test)
      SMOKE_TEST=0
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      die "Unsupported argument: $1"
      ;;
  esac
  shift
done

[ -n "$PRINTER_HOST" ] || die "Missing printer host. Use --host or PRINTER_HOST."

for tool in python3 ssh scp; do
  command -v "$tool" >/dev/null 2>&1 || die "Missing required tool: $tool"
done

SSH_CMD=(ssh)
SCP_CMD=(scp)
if [ -n "$PRINTER_PASSWORD" ]; then
  command -v sshpass >/dev/null 2>&1 || die "sshpass is required when --password or PRINTER_PASSWORD is set."
  SSH_CMD=(sshpass -p "$PRINTER_PASSWORD" ssh -o PreferredAuthentications=password,keyboard-interactive -o PubkeyAuthentication=no)
  SCP_CMD=(sshpass -p "$PRINTER_PASSWORD" scp -o PreferredAuthentications=password,keyboard-interactive -o PubkeyAuthentication=no)
fi

cd "$REPO_ROOT"

BUILD_CMD=(python3 scripts/build_installer_bundle.py --output-dir dist --channel dev --build-id "$BUILD_ID")
if [ "$SMOKE_TEST" -eq 1 ]; then
  BUILD_CMD+=(--smoke-test)
fi

printf 'Building dev installer bundle...\n'
"${BUILD_CMD[@]}"

BUNDLE_PATH="$REPO_ROOT/dist/tltg-optimized-macros-dev.tar.gz"
[ -f "$BUNDLE_PATH" ] || die "Expected bundle not found: $BUNDLE_PATH"

SSH_TARGET="${PRINTER_USER}@${PRINTER_HOST}"
REMOTE_BUNDLE='~/tltg-optimized-macros-dev.tar.gz'
REMOTE_DIR='~/tltg-optimized-macros'

printf 'Copying bundle to %s...\n' "$SSH_TARGET"
"${SCP_CMD[@]}" "$BUNDLE_PATH" "$SSH_TARGET:$REMOTE_BUNDLE"

printf 'Extracting bundle on %s...\n' "$SSH_TARGET"
"${SSH_CMD[@]}" "$SSH_TARGET" "rm -rf $REMOTE_DIR && tar -xzf $REMOTE_BUNDLE -C ~/"

REMOTE_INSTALL_CMD='cd ~/tltg-optimized-macros && ./install.sh --dry-run --plain'
if [ "$DEBUG_INSTALL" -eq 1 ]; then
  REMOTE_INSTALL_CMD="$REMOTE_INSTALL_CMD --debug"
fi

printf 'Running remote dry-run on %s...\n' "$SSH_TARGET"
"${SSH_CMD[@]}" "$SSH_TARGET" "$REMOTE_INSTALL_CMD"
