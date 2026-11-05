from __future__ import annotations

import json
import math
import shutil
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Callable

from .errors import ActivePrintError, FreeSpaceError, InstallerError, KlipperBusyError, PrinterStateError, RecoveryRequiredError

DiskUsageFn = Callable[[Path], object]
UrlOpenFn = Callable[..., object]


THR_RECOVERY_MARKER = ".tltg_thr_firmware_pending.json"
BOX_RECOVERY_MARKER = ".tltg_box_firmware_pending.json"


def ensure_no_pending_firmware(path: Path, *, allow_box: bool = False) -> None:
    marker = path.parent / THR_RECOVERY_MARKER
    if marker.exists() or marker.is_symlink():
        raise InstallerError("Unresolved THR firmware operation; recover and verify the board before continuing: " + str(marker))
    marker = path.parent / BOX_RECOVERY_MARKER
    if not allow_box and (marker.exists() or marker.is_symlink()):
        raise InstallerError("Unresolved Box firmware operation; run ./box-firmware.sh rescue before continuing: " + str(marker))


def ensure_no_recovery_sentinel(path: Path) -> None:
    ensure_no_pending_firmware(path)
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


def ensure_klipper_idle(
    url: str,
    *,
    idle_seconds: float,
    timeout: int = 5,
    urlopen: UrlOpenFn = urllib.request.urlopen,
) -> None:
    """Raise unless Klipper is ready, nothing prints, every heater target is 0, and the toolhead has not moved for idle_seconds."""
    try:
        heaters = _query_objects(url, ("heaters",), timeout=timeout, urlopen=urlopen)["heaters"]["available_heaters"]
        if not isinstance(heaters, list) or not all(isinstance(name, str) and name for name in heaters):
            raise PrinterStateError()
        status = _query_objects(
            url,
            ("print_stats", "webhooks", "idle_timeout", "toolhead", *heaters),
            timeout=timeout,
            urlopen=urlopen,
        )
        if status["print_stats"]["state"] in {"printing", "paused"}:
            raise ActivePrintError()
        if status["webhooks"]["state"] != "ready":
            raise PrinterStateError()
        heating = any(_finite(status[name]["target"]) != 0 for name in heaters)
        # Klipper advances print_time only for motion and timed commands, so this is how long the toolhead has been still.
        still_for = _finite(status["toolhead"]["estimated_print_time"]) - _finite(status["toolhead"]["print_time"])
        running_command = status["idle_timeout"]["state"] == "Printing"
    except (KeyError, TypeError, ValueError) as exc:
        raise PrinterStateError() from exc
    if heating or running_command or still_for < idle_seconds:
        raise KlipperBusyError()


def _query_objects(url: str, names: tuple[str, ...], *, timeout: int, urlopen: UrlOpenFn) -> dict:
    parts = urllib.parse.urlsplit(url)
    query = "&".join(urllib.parse.quote(name, safe="") for name in names)
    try:
        with urlopen(urllib.parse.urlunsplit(parts._replace(query=query)), timeout=timeout) as response:
            status = json.load(response)["result"]["status"]
    except (OSError, urllib.error.URLError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise PrinterStateError() from exc
    if not isinstance(status, dict):
        raise PrinterStateError()
    return status


def _finite(value) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(value)
    return float(value)


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
