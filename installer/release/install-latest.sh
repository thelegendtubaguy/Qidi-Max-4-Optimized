#!/bin/sh
set -eu

ARCHIVE_URL=${TLTG_INSTALLER_ARCHIVE_URL:-https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/releases/latest/download/tltg-optimized-macros.tar.gz}
CHECKSUM_URL=${TLTG_INSTALLER_CHECKSUM_URL:-${ARCHIVE_URL}.sha256}
ARCHIVE_NAME=${ARCHIVE_URL##*/}
ARCHIVE_NAME=${ARCHIVE_NAME%%\?*}
ARCHIVE_NAME=${ARCHIVE_NAME%%#*}
CHECKSUM_NAME=${ARCHIVE_NAME}.sha256

if [ -z "${HOME:-}" ]; then
  echo "HOME is not set." >&2
  exit 1
fi
INSTALL_DIR=${HOME}/tltg-optimized-macros
INSTALL_PARENT=${HOME}

for tool in curl tar mktemp rm mkdir; do
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing required tool: $tool" >&2
    exit 1
  fi
done

TMP_ROOT=${TMPDIR:-/tmp}
TMP_DIR=$(mktemp -d "$TMP_ROOT/tltg-optimized-macros.XXXXXX")
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT
trap 'trap - EXIT; cleanup; exit 130' INT HUP TERM

echo "Downloading TLTG optimized macro installer..."
curl -fL --retry 3 --connect-timeout 15 --progress-bar "$ARCHIVE_URL" -o "$TMP_DIR/$ARCHIVE_NAME"
curl -fsSL --retry 3 --connect-timeout 15 "$CHECKSUM_URL" -o "$TMP_DIR/$CHECKSUM_NAME"

if command -v sha256sum >/dev/null 2>&1; then
  (cd "$TMP_DIR" && sha256sum -c "$CHECKSUM_NAME")
elif command -v shasum >/dev/null 2>&1; then
  (cd "$TMP_DIR" && shasum -a 256 -c "$CHECKSUM_NAME")
else
  echo "Warning: sha256sum or shasum not found; checksum verification skipped." >&2
fi

rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_PARENT"
tar -xzf "$TMP_DIR/$ARCHIVE_NAME" -C "$INSTALL_PARENT"

cd "$INSTALL_DIR"
./install.sh "$@"
