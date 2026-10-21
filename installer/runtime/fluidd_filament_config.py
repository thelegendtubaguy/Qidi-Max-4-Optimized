"""Expose the QIDI touchscreen filament database in Fluidd's config file browser."""
from __future__ import annotations

import os
from pathlib import Path

OPERATION = "fluidd_filament_config_link"

CURRENT = "current"
ABSENT = "absent"
CONFLICT = "conflict"
TARGET_MISSING = "target_missing"


def link_state(link: Path, *, target: str, target_present: bool) -> str:
    """Classify the config entry; anything other than our own link is operator-owned."""
    if link.is_symlink():
        return CURRENT if os.readlink(link) == target else CONFLICT
    if link.exists():
        return CONFLICT
    return ABSENT if target_present else TARGET_MISSING


def create_link(link: Path, *, target: str) -> None:
    os.symlink(target, link)


def remove_link(link: Path, *, target: str) -> bool:
    """Remove only the installer's link; report whether the entry is now absent."""
    if link.is_symlink() and os.readlink(link) == target:
        link.unlink()
        return True
    return not link.exists() and not link.is_symlink()
