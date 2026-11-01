#!/usr/bin/env python3
"""Generate the hash-locked QIDI Box shutdown fix from a stock Box image."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

PATCH_MANIFEST = Path(__file__).resolve().parents[1] / "firmware/max4-box-shutdown-fix-v1.json"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load_manifest(path: Path = PATCH_MANIFEST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def patch_box(stock: bytes, manifest: dict) -> bytes:
    box = manifest["box"]
    if len(stock) != box["size"] or sha256(stock) != box["stock_sha256"]:
        raise ValueError("Unrecognized stock Box image; no patch applied")
    patched = bytearray(stock)
    for patch in box["patches"]:
        offset = int(patch["offset"], 0)
        after = bytes.fromhex(patch["after"])
        current = stock[offset:offset + len(after)]
        if "before" in patch:
            before = bytes.fromhex(patch["before"])
            if len(before) != len(after) or current != before:
                raise ValueError(f"Box preimage mismatch at {patch['offset']}")
        elif sha256(current) != patch["before_sha256"]:
            raise ValueError(f"Box preimage mismatch at {patch['offset']}")
        patched[offset:offset + len(after)] = after
    if sha256(patched) != box["patched_sha256"]:
        raise ValueError("Patched Box checksum mismatch; no image generated")
    return bytes(patched)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock-image", type=Path, required=True, help="QD_MAX4_BOX_02.03.01.21 application image")
    parser.add_argument("--output", type=Path, required=True, help="new file; must not exist")
    args = parser.parse_args()
    try:
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("Output already exists; choose a new destination")
        manifest = load_manifest()
        patched = patch_box(args.stock_image.read_bytes(), manifest)
        with args.output.open("xb") as handle:
            handle.write(patched)
    except (OSError, ValueError) as error:
        print(f"Box firmware generation failed: {error}", file=sys.stderr)
        return 1
    print(f"Generated {args.output} ({manifest['box']['patched_version']}, SHA-256 {manifest['box']['patched_sha256']}). Nothing was flashed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
