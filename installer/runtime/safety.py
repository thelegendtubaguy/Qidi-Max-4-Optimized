from __future__ import annotations

import json
import shutil
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Callable

from .errors import ActivePrintError, FreeSpaceError, InstallerError, PrinterStateError, RecoveryRequiredError

DiskUsageFn = Callable[[Path], object]
UrlOpenFn = Callable[..., object]


THR_RECOVERY_MARKER = ".tltg_thr_firmware_pending.json"


def ensure_no_pending_thr_firmware(path: Path) -> None:
    marker = path.parent / THR_RECOVERY_MARKER
    if marker.exists() or marker.is_symlink():
        raise InstallerError("Unresolved THR firmware operation; recover and verify the board before continuing: " + str(marker))


def ensure_no_recovery_sentinel(path: Path) -> None:
    ensure_no_pending_thr_firmware(path)
    if path.exists():
        raise RecoveryRequiredError()


def query_printer_state(
    url: str,
    *,
    timeout: int = 5,
    urlopen: UrlOpenFn = urllib.request.urlopen,
) -> str:
    try:
        with urlopen(url, timeout=timeout) as response:
            payload = json.load(response)
    except (OSError, urllib.error.URLError, json.JSONDecodeError, TypeError, ValueError) as exc:
        raise PrinterStateError() from exc
    try:
        state = payload["result"]["status"]["print_stats"]["state"]
    except (KeyError, TypeError) as exc:
        raise PrinterStateError() from exc
    if not isinstance(state, str) or not state:
        raise PrinterStateError()
    return state


def ensure_printer_idle(
    url: str,
    *,
    timeout: int = 5,
    urlopen: UrlOpenFn = urllib.request.urlopen,
    wait_seconds: float = 0.0,
) -> str:
    """Return the idle printer state; an unknown state is retried for wait_seconds, as while Moonraker restarts."""
    deadline = time.monotonic() + wait_seconds
    while True:
        try:
            state = query_printer_state(url, timeout=timeout, urlopen=urlopen)
            break
        except PrinterStateError:
            # A Klipper halted on an error has no print state and cannot be printing.
            if klipper_halted(url, urlopen=urlopen):
                return "error"
            if time.monotonic() >= deadline:
                raise
            time.sleep(2.0)
    if state in {"printing", "paused"}:
        raise ActivePrintError()
    return state


def klipper_halted(url: str, *, urlopen: UrlOpenFn = urllib.request.urlopen) -> bool:
    """Return True when Moonraker reports Klipper stopped with an error, such as a config error."""
    from .process_restart import ProcessRestartError, read_printer_info

    try:
        _, state = read_printer_info(url, urlopen=urlopen)
    except ProcessRestartError:
        return False
    return state == "error"


def current_free_bytes(
    root: Path, disk_usage: DiskUsageFn = shutil.disk_usage
) -> int:
    usage = disk_usage(root)
    free = getattr(usage, "free", None)
    if free is None:
        free = usage[2]
    return int(free)


def ensure_sufficient_free_space(
    root: Path,
    required_bytes: int,
    *,
    disk_usage: DiskUsageFn = shutil.disk_usage,
) -> int:
    free = current_free_bytes(root, disk_usage=disk_usage)
    if free < required_bytes:
        raise FreeSpaceError()
    return free


def total_tree_size(path: Path) -> int:
    if not path.exists():
        return 0
    if path.is_file():
        return path.stat().st_size
    total = 0
    for item in path.rglob("*"):
        if item.is_file():
            total += item.stat().st_size
    return total


def file_size(path: Path) -> int:
    return path.stat().st_size if path.exists() and path.is_file() else 0


def required_free_bytes(
    *, backup_reserve: int, rollback_reserve: int, write_reserve: int
) -> int:
    subtotal = backup_reserve + rollback_reserve + write_reserve
    safety_margin = max(64 * 1024 * 1024, int(subtotal * 0.2))
    return subtotal + safety_margin
