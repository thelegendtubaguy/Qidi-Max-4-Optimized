#!/usr/bin/env python3
from __future__ import annotations

import sys
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from installer.runtime.compatibility import load_supported_upgrade_sources, validate_manifest_compatibility
from installer.runtime.manifest import load_manifest


def main() -> int:
    manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
    compatibility = load_supported_upgrade_sources(
        REPO_ROOT / "installer/supported_upgrade_sources.yaml"
    )
    validate_manifest_compatibility(manifest, compatibility)
    globals_text = (REPO_ROOT / "installer/klipper/tltg-optimized-macros/globals.cfg").read_text(
        encoding="utf-8"
    )
    match = re.search(r'^variable_package_version:\s*["\']?([^"\'\n]+)["\']?\s*$', globals_text, re.MULTILINE)
    if match is None:
        raise SystemExit("Missing variable_package_version in optimized globals.cfg")
    if match.group(1) != manifest.package.version:
        raise SystemExit(
            "Optimized globals package version does not match installer/package.yaml: "
            f"{match.group(1)} != {manifest.package.version}"
        )
    print("installer compatibility metadata validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
