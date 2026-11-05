from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .errors import FirmwareDetectionError, UnsupportedFirmwareError
from .models import Manifest, PrinterSpec


@dataclass(frozen=True)
class DetectedFirmware:
    version: str
    soc_file: str | None


def detect_firmware(path: Path) -> DetectedFirmware:
    try:
        with path.open("r", encoding="utf-8") as handle:
            raw = json.load(handle)
    except (OSError, json.JSONDecodeError) as exc:
        raise FirmwareDetectionError() from exc

    try:
        soc = raw["SOC"]
        version = soc["version"]
    except (KeyError, TypeError) as exc:
        raise FirmwareDetectionError() from exc
    if not isinstance(version, str) or not version:
        raise FirmwareDetectionError()
    soc_file = soc.get("file")
    return DetectedFirmware(version=version, soc_file=soc_file if isinstance(soc_file, str) else None)


def detect_firmware_version(path: Path) -> str:
    return detect_firmware(path).version


def detect_firmware_version_best_effort(path: Path) -> Optional[str]:
    try:
        return detect_firmware_version(path)
    except FirmwareDetectionError:
        return None


def supported_printer(manifest: Manifest, detected: DetectedFirmware) -> PrinterSpec | None:
    printer = manifest.printer_for_firmware(detected.version)
    if printer is None:
        return None
    if detected.soc_file is not None and not detected.soc_file.startswith(printer.soc_file_prefix):
        return None
    return printer


def detect_supported_firmware(path: Path, manifest: Manifest) -> tuple[PrinterSpec, str]:
    detected = detect_firmware(path)
    printer = supported_printer(manifest, detected)
    if printer is None:
        raise UnsupportedFirmwareError()
    return printer, detected.version
