"""QIDI Box firmware shutdown fix: status, install, restore, and rescue.

Run only through box-firmware.sh. Install, update, and automatic updates never
call this module, and --yes cannot authorize it.
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from .auto_update import LOCK_HELD_ENV
from .errors import InstallerError
from .fs_atomic import atomic_delete, atomic_write_text, fsync_directory
from .path_safety import ensure_runtime_path_has_no_symlink_components
from .safety import BOX_RECOVERY_MARKER, ensure_no_pending_firmware
from .sudo import authenticate_sudo, run_sudo
from .thr_firmware import ThrFirmwareError, wait_for_thr_printer_ready

SUBJECT = "Box firmware"
SERVICES = ("klipper.service", "qidi-client.service", "tltg-optimized-auto-update.timer")
BACKUP_DIRECTORY = ".tltg_box_firmware_backups"
CONFIRMATION = "FLASH"
APP_RETURN_SECONDS = 30
BOX_SECTION = re.compile(r"^\[mcu (mcu_box(\d+))\]\s*$")
SERIAL_LINE = re.compile(r"^serial\s*[:=]\s*(\S+)")
WARNING = "Box firmware: keep the printer and every Box powered on until this finishes."


class BoxFirmwareError(InstallerError):
    pass


@dataclass(frozen=True)
class Box:
    number: int
    name: str
    serial: str | None
    usb: str | None

    @property
    def label(self) -> str:
        return f"Box {self.number}"


def usb_path_for_serial(serial: str | None) -> str | None:
    if not serial:
        return None
    device = Path(os.path.realpath(serial))
    if not device.name.startswith("tty") or not device.exists():
        return None
    interface = Path(os.path.realpath(Path("/sys/class/tty") / device.name / "device")).name
    usb = interface.split(":", 1)[0]
    return usb if re.match(r"^\d+-\d+(\.\d+)*$", usb) else None


def discover_boxes(paths, *, resolve_usb=usb_path_for_serial) -> list[Box]:
    box_cfg = paths.config_root / "box.cfg"
    if not box_cfg.is_file():
        return []
    boxes, current = [], None
    for line in box_cfg.read_text(encoding="utf-8", errors="replace").splitlines():
        stripped = line.strip()
        match = BOX_SECTION.match(stripped)
        if match:
            current = [int(match.group(2)), match.group(1), None]
            boxes.append(current)
            continue
        if stripped.startswith("["):
            current = None
        elif current is not None and current[2] is None:
            serial = SERIAL_LINE.match(stripped)
            if serial:
                current[2] = serial.group(1)
    return [Box(number, name, serial, resolve_usb(serial)) for number, name, serial in sorted(boxes)]


def _versions(paths, boxes, urlopen) -> dict[str, str | None]:
    names = [f"mcu {box.name}" for box in boxes]
    parts = urllib.parse.urlsplit(paths.moonraker_url)
    url = urllib.parse.urlunsplit(parts._replace(
        query="&".join(urllib.parse.quote(name, safe="") + "=mcu_version" for name in names)))
    try:
        with urlopen(url, timeout=5) as response:
            status = json.load(response)["result"]["status"]
    except (OSError, ValueError, KeyError, TypeError):
        return {box.name: None for box in boxes}
    return {box.name: (status.get(f"mcu {box.name}") or {}).get("mcu_version") for box in boxes}


def _describe(version: str | None, manifest: dict) -> str:
    box = manifest["box"]
    if version == box["patched_version"]:
        return "shutdown fix installed (" + version + ")"
    if version == box["stock_version"]:
        return "QIDI stock firmware (" + version + ")"
    if version is None:
        return "not connected or Klipper not ready"
    return "unsupported firmware (" + version + ")"


def _select(boxes: list[Box], requested: list[int] | None) -> list[Box]:
    if not boxes:
        raise BoxFirmwareError("No USB QIDI Box is configured in box.cfg. RS-485 Boxes have no Klipper MCU to flash.")
    if not requested:
        return boxes
    known = {box.number: box for box in boxes}
    missing = sorted(set(requested) - set(known))
    if missing:
        raise BoxFirmwareError("Not a configured USB Box: " + ", ".join(map(str, missing)))
    return [known[number] for number in sorted(set(requested))]


def _stock_image(paths, manifest) -> bytes | None:
    from scripts.flash_box_firmware import image_identity
    candidates = sorted((paths.printer_data_root / BACKUP_DIRECTORY).glob("*/*/before/application.bin"))
    candidates += sorted((paths.printer_data_root.parent / "update").glob("QD_MAX4_BOX_" + manifest["box"]["stock_version"] + "_*.bin"))
    for candidate in candidates:
        try:
            data = candidate.read_bytes()
        except OSError:
            continue
        if image_identity(data, manifest) == "stock":
            return data
    return None


def run_box_firmware(
    *, paths, reporter, action, boxes=None, input_stream=None, environ=None,
    run=None, urlopen=urllib.request.urlopen, sleep=time.sleep, clock=time.monotonic,
    resolve_usb=usb_path_for_serial,
) -> int:
    from scripts import build_box_firmware
    from scripts import flash_box_firmware as protocol

    run = subprocess.run if run is None else run
    env = {} if environ is None else environ
    manifest = build_box_firmware.load_manifest(paths.bundle_root / "firmware/max4-box-shutdown-fix-v1.json")
    configured = discover_boxes(paths, resolve_usb=resolve_usb)
    marker = paths.printer_data_root / BOX_RECOVERY_MARKER

    if action == "status":
        versions = _versions(paths, configured, urlopen)
        if not configured:
            reporter.line("No USB QIDI Box is configured in box.cfg.")
        for box in configured:
            reporter.line(f"{box.label} ({box.name}): {_describe(versions[box.name], manifest)}")
        if marker.exists():
            reporter.line("A Box firmware operation did not finish; run ./box-firmware.sh rescue --box N. Record: " + str(marker))
        return 0

    if env.get(LOCK_HELD_ENV) == "1":
        raise BoxFirmwareError("Box firmware programming is not allowed in automatic-update child installs.")
    if paths.restart_marker_path.exists():
        raise BoxFirmwareError("Complete pending Klipper source activation before Box firmware programming.")
    ensure_no_pending_firmware(paths.recovery_sentinel_path, allow_box=action == "rescue")
    selected = _select(configured, boxes)
    if action == "rescue" and len(selected) != 1:
        raise BoxFirmwareError("rescue needs exactly one --box.")
    python = paths.printer_data_root.parent / "klippy-env/bin/python"
    tool = paths.bundle_root / "scripts/flash_box_firmware.py"
    if not tool.is_file() or tool.is_symlink() or not python.is_file():
        raise BoxFirmwareError("Box firmware requires the packaged tool and the existing klippy-env Python.")
    backup_root = paths.printer_data_root / BACKUP_DIRECTORY
    for target in (marker, backup_root):
        ensure_runtime_path_has_no_symlink_components(printer_data_root=paths.printer_data_root, target=target)

    target = "patched" if action == "install" else "stock"
    stock_image = None
    if action in ("restore", "rescue"):
        stock_image = _stock_image(paths, manifest)
        if stock_image is None:
            raise BoxFirmwareError("No verified copy of QIDI's Box firmware " + manifest["box"]["stock_version"]
                                   + " was found in the Box firmware backups or ~/update.")
    previous = {}
    if action == "rescue":
        box = selected[0]
        previous_dirs = sorted(backup_root.glob(f"*/{box.name}/before/bootloader.bin"))
        if not previous_dirs:
            raise BoxFirmwareError(f"No earlier backup of {box.label}'s bootloader; rescue needs one from a previous box-firmware run.")
        rescue_backup = previous_dirs[-1].parent
        usb = box.usb
        if usb is None:
            record = rescue_backup.parent / "box.json"
            usb = json.loads(record.read_text()).get("usb") if record.is_file() else None
        if usb is None:
            raise BoxFirmwareError(f"Cannot find {box.label}'s USB position.")
        plan = [(box, usb)]
    else:
        versions = _versions(paths, selected, urlopen)
        plan = []
        for box in selected:
            version = versions[box.name]
            reporter.line(f"{box.label} ({box.name}): {_describe(version, manifest)}")
            wanted = manifest["box"]["patched_version" if target == "patched" else "stock_version"]
            if version == wanted:
                previous[box.name] = "already " + ("installed" if target == "patched" else "stock")
            elif box.usb is None or version is None:
                previous[box.name] = "skipped: not connected"
            elif version not in (manifest["box"]["stock_version"], manifest["box"]["patched_version"]):
                previous[box.name] = "skipped: unsupported firmware"
            else:
                plan.append((box, box.usb))
        if not plan:
            for box in selected:
                reporter.line(f"{box.label}: {previous[box.name]}")
            reporter.line("Nothing to flash.")
            return 0

    verb = {"install": "Install the shutdown fix on", "restore": "Restore QIDI's stock firmware on",
            "rescue": "Rescue and restore QIDI's stock firmware on"}[action]
    reporter.line(WARNING)
    reporter.line(f"{verb}: " + ", ".join(box.label for box, _ in plan)
                  + ". Klipper and the touchscreen stop for about four minutes per Box.")
    if input_stream is None:
        raise BoxFirmwareError("box-firmware needs an interactive terminal to confirm.")
    reporter.emit_prompt(question=f"Type {CONFIRMATION} to continue", instruction="Anything else cancels.")
    if input_stream.readline().strip() != CONFIRMATION:
        reporter.line("Cancelled. No Box firmware was changed.")
        return 1

    try:
        if action != "rescue":
            wait_for_thr_printer_ready(paths, urlopen=urlopen, sleep=sleep, clock=clock, reporter=reporter, subject=SUBJECT)
    except ThrFirmwareError as exc:
        raise BoxFirmwareError(str(exc)) from exc
    states = {}
    for service in SERVICES:
        result = run(["systemctl", "show", service, "--property=LoadState,ActiveState"], capture_output=True, text=True, timeout=5)
        values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        if service.endswith(".timer") and values.get("LoadState") == "not-found":
            continue
        if result.returncode or values.get("LoadState") != "loaded" or values.get("ActiveState") not in {"active", "inactive"}:
            raise BoxFirmwareError("Cannot establish serial service ownership: " + service)
        states[service] = values["ActiveState"]
    if action == "rescue" and marker.is_file():
        try:
            states = json.loads(marker.read_text()).get("services") or states
        except ValueError:
            pass
    password = authenticate_sudo(run=run, environ=env, reporter=reporter, input_stream=input_stream)
    backup_root.mkdir(mode=0o700, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="box-", dir=backup_root))
    fsync_directory(backup_root)
    record = {"backup_directory": str(directory), "services": states, "action": action, "phase": "stopping_services"}
    atomic_write_text(marker, json.dumps(record, indent=2) + "\n", mode=0o600)
    reporter.line("Box firmware recovery files: " + str(directory))
    results = dict(previous)
    pending = False

    def command(box_dir, operation, *arguments, allow=()):
        result = run([str(python), str(tool), operation, *map(str, arguments), "--printer-idle-confirmed"],
                     capture_output=True, text=True, timeout=960)
        atomic_write_text(box_dir / (operation + ".stdout"), result.stdout or "", mode=0o600)
        atomic_write_text(box_dir / (operation + ".stderr"), result.stderr or "", mode=0o600)
        if result.returncode and result.returncode not in allow:
            raise BoxFirmwareError("Box " + operation + " failed; see " + str(box_dir))
        return result

    def service_action(verb_name, service):
        result = run_sudo(["systemctl", verb_name, service], run=run, password=password, timeout=60)
        if result.returncode:
            raise BoxFirmwareError("Could not " + verb_name + " " + service)

    try:
        for service in reversed(SERVICES):
            if states.get(service) == "active":
                service_action("stop", service)
        for box, usb in plan:
            box_dir = directory / box.name
            box_dir.mkdir(mode=0o700)
            atomic_write_text(box_dir / "box.json", json.dumps({"box": box.name, "usb": usb}) + "\n", mode=0o600)
            if action == "rescue":
                before = rescue_backup
                image = stock_image
                reporter.line(f"{box.label}: waiting for its bootloader. Turn {box.label} off and on again now.")
                record.update(phase="programming", box=box.name, usb=usb)
                atomic_write_text(marker, json.dumps(record, indent=2) + "\n", mode=0o600)
                pending = True
                command(box_dir, "transfer", "--usb", usb, "--image", _write_image(box_dir, image),
                        "--backup-dir", before, "--confirm-write", "--rescue", "--wait", 300)
            else:
                before = box_dir / "before"
                reporter.line(f"{box.label}: reading and admitting its bootloader and firmware...")
                snapshot = command(box_dir, "snapshot", "--usb", usb, "--output-dir", before, allow=(protocol.UNSUPPORTED,))
                if snapshot.returncode == protocol.UNSUPPORTED:
                    results[box.name] = "not changed: unsupported bootloader or firmware; shareable summary " + str(before / "report.json")
                    continue
                boot, app = protocol.load_backup(before, manifest)
                current = protocol.image_identity(app, manifest)
                if current == target:
                    results[box.name] = "already " + ("installed" if target == "patched" else "stock") + " (verified by readback)"
                    continue
                image = build_box_firmware.patch_box(app, manifest) if target == "patched" else stock_image
                record.update(phase="programming", box=box.name, usb=usb)
                atomic_write_text(marker, json.dumps(record, indent=2) + "\n", mode=0o600)
                pending = True
                reporter.line(f"{box.label}: flashing; keep it powered on...")
                command(box_dir, "transfer", "--usb", usb, "--image", _write_image(box_dir, image),
                        "--backup-dir", before, "--confirm-write")
            reporter.line(f"{box.label}: reading back its firmware...")
            after = box_dir / "after"
            command(box_dir, "snapshot", "--usb", usb, "--output-dir", after, "--wait", APP_RETURN_SECONDS)
            evidence = protocol.verify_readback(image, after, manifest,
                                                expected_bootloader=(before / "bootloader.bin").read_bytes())
            atomic_write_text(box_dir / "verification.json", json.dumps(evidence, indent=2) + "\n", mode=0o600)
            results[box.name] = ("shutdown fix installed" if target == "patched" else "QIDI stock firmware restored") + " and verified"
            pending = False
            record.update(phase="verified", box=box.name)
            atomic_write_text(marker, json.dumps(record, indent=2) + "\n", mode=0o600)
    except Exception as exc:
        failure = exc
    else:
        failure = None
    if pending:
        box = record.get("box")
        number = next((b.number for b, _ in plan if b.name == box), "N")
        reporter.line(f"{box} firmware is unverified. Klipper and the touchscreen stay stopped. "
                      f"Run ./box-firmware.sh rescue --box {number} and follow its prompt.")
        raise BoxFirmwareError("Box firmware operation failed: " + str(failure) + ". Recovery files: " + str(directory)) from failure
    try:
        for service in SERVICES:
            if states.get(service) == "active":
                service_action("start", service)
        if states.get("klipper.service") == "active":
            wait_for_thr_printer_ready(paths, urlopen=urlopen, sleep=sleep, clock=clock, subject=SUBJECT)
        atomic_delete(marker)
    except BaseException as exc:
        raise BoxFirmwareError("Box firmware service restoration is incomplete; recovery record retained: " + str(marker)) from exc
    labels = {box.name: box.label for box in configured}
    for name, outcome in results.items():
        reporter.line(f"{labels.get(name, name)}: {outcome}")
    if failure is not None:
        raise BoxFirmwareError("Box firmware operation stopped before any write: " + str(failure))
    return 0


def _write_image(directory: Path, image: bytes) -> Path:
    path = directory / "image.bin"
    with os.fdopen(os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as handle:
        handle.write(image)
        handle.flush()
        os.fsync(handle.fileno())
    return path
