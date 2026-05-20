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

for tool in curl tar mktemp rm mkdir mv grep find; do
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
  echo "Missing required tool: sha256sum or shasum" >&2
  exit 1
fi

MEMBERS_FILE="$TMP_DIR/archive.members"
LISTING_FILE="$TMP_DIR/archive.listing"
tar -tzf "$TMP_DIR/$ARCHIVE_NAME" > "$MEMBERS_FILE"
tar -tvzf "$TMP_DIR/$ARCHIVE_NAME" > "$LISTING_FILE"
if grep -E '(^/|(^|/)\.\.(/|$))' "$MEMBERS_FILE" >/dev/null 2>&1; then
  echo "Archive contains unsafe member paths." >&2
  exit 1
fi
if grep -Ev '^tltg-optimized-macros(/|$)' "$MEMBERS_FILE" >/dev/null 2>&1; then
  echo "Archive does not use the expected tltg-optimized-macros/ root." >&2
  exit 1
fi
if ! grep -Fx 'tltg-optimized-macros/install.sh' "$MEMBERS_FILE" >/dev/null 2>&1; then
  echo "Archive is missing tltg-optimized-macros/install.sh." >&2
  exit 1
fi
if grep -Ev '^[-d]' "$LISTING_FILE" >/dev/null 2>&1; then
  echo "Archive contains unsupported member types." >&2
  exit 1
fi

STAGE_DIR="$TMP_DIR/extract"
mkdir -p "$STAGE_DIR"
tar -xzf "$TMP_DIR/$ARCHIVE_NAME" -C "$STAGE_DIR"
if find "$STAGE_DIR/tltg-optimized-macros" -type l | grep . >/dev/null 2>&1; then
  echo "Archive contains symbolic links." >&2
  exit 1
fi
if [ ! -f "$STAGE_DIR/tltg-optimized-macros/install.sh" ]; then
  echo "Archive is missing tltg-optimized-macros/install.sh." >&2
  exit 1
fi

rm -rf "$INSTALL_DIR"
mkdir -p "$INSTALL_PARENT"
mv "$STAGE_DIR/tltg-optimized-macros" "$INSTALL_DIR"

cd "$INSTALL_DIR"
./install.sh "$@"
