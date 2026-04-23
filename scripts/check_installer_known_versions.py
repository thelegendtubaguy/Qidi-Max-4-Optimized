#!/usr/bin/env python3
from __future__ import annotations

import sys
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
    print("installer compatibility metadata validated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
