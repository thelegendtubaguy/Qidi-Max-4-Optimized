from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .errors import FirmwareDetectionError


def detect_firmware_version(path: Path) -> str:
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise FirmwareDetectionError() from exc

    try:
        version = raw["SOC"]["version"]
    except (KeyError, TypeError) as exc:
        raise FirmwareDetectionError() from exc
    if not isinstance(version, str) or not version:
        raise FirmwareDetectionError()
    return version


def detect_firmware_version_best_effort(path: Path) -> Optional[str]:
    try:
        return detect_firmware_version(path)
    except FirmwareDetectionError:
        return None
