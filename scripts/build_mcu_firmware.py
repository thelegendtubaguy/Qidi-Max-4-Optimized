#!/usr/bin/env python3
"""Generate the hash-locked Max 4 mainboard closed-loop reply fix from a stock mainboard image."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if __package__:
    from .build_box_firmware import apply_patches
else:
    from build_box_firmware import apply_patches

PATCH_MANIFEST = Path(__file__).resolve().parents[1] / "firmware/max4-mcu-closed-loop-replies-v1.json"


def load_manifest(path: Path = PATCH_MANIFEST) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def patch_mcu(stock: bytes, manifest: dict) -> bytes:
    return apply_patches(stock, manifest["mcu"], "mainboard")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stock-image", type=Path, required=True, help="QD_MAX4_MCU_02.01.01.12 application image")
    parser.add_argument("--output", type=Path, required=True, help="new file; must not exist")
    args = parser.parse_args()
    try:
        if args.output.exists() or args.output.is_symlink():
            raise ValueError("Output already exists; choose a new destination")
        manifest = load_manifest()
        patched = patch_mcu(args.stock_image.read_bytes(), manifest)
        with args.output.open("xb") as handle:
            handle.write(patched)
    except (OSError, ValueError) as error:
        print(f"Mainboard firmware generation failed: {error}", file=sys.stderr)
        return 1
    print(f"Generated {args.output} ({manifest['mcu']['patched_version']}, SHA-256 {manifest['mcu']['patched_sha256']}). Nothing was flashed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
