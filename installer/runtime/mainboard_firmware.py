"""Max 4 mainboard closed-loop reply fix: status, install, restore, and rescue.

Run only through mainboard-firmware.sh. Install, update, and automatic updates
never call this module, and --yes cannot authorize it.
"""
from __future__ import annotations

import json
import re
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

from .auto_update import LOCK_HELD_ENV
from .box_firmware import SERVICES, _write_image, usb_path_for_serial
from .errors import FirmwareDetectionError, InstallerError
from .firmware import detect_firmware
from .fs_atomic import atomic_delete, atomic_write_text, fsync_directory
from .path_safety import ensure_runtime_path_has_no_symlink_components
from .safety import MAINBOARD_RECOVERY_MARKER, ensure_no_pending_firmware
from .sudo import authenticate_sudo, run_sudo
from .thr_firmware import ThrFirmwareError, wait_for_thr_printer_ready

SUBJECT = "Mainboard firmware"
MANIFEST = "firmware/max4-mcu-closed-loop-replies-v1.json"
BACKUP_DIRECTORY = ".tltg_mainboard_firmware_backups"
CONFIRMATION = "FLASH"
APP_RETURN_SECONDS = 30
RESCUE_WAIT_SECONDS = 60
MCU_SECTION = re.compile(r"^\[mcu\]\s*$")
SERIAL_LINE = re.compile(r"^serial\s*[:=]\s*(\S+)")
WARNING = "Mainboard firmware: keep the printer powered on until this finishes."


class MainboardFirmwareError(InstallerError):
    pass


def mainboard_serial(paths) -> str | None:
    for name in ("MCU_ID.cfg", "printer.cfg"):
        path = paths.config_root / name
        if not path.is_file():
            continue
        in_mcu = False
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            stripped = line.strip()
            if stripped.startswith("["):
                in_mcu = bool(MCU_SECTION.match(stripped))
            elif in_mcu:
                serial = SERIAL_LINE.match(stripped)
                if serial:
                    return serial.group(1)
    return None


def _version(paths, urlopen) -> str | None:
    parts = urllib.parse.urlsplit(paths.moonraker_url)
    url = urllib.parse.urlunsplit(parts._replace(query="mcu=mcu_version"))
    try:
        with urlopen(url, timeout=5) as response:
            return (json.load(response)["result"]["status"].get("mcu") or {}).get("mcu_version")
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return None


def _describe(version: str | None, manifest: dict) -> str:
    mcu = manifest["mcu"]
    if version == mcu["patched_version"]:
        return "closed-loop reply fix installed (" + version + ")"
    if version == mcu["stock_version"]:
        return "QIDI stock firmware (" + version + ")"
    if version is None:
        return "not connected or Klipper not ready"
    return "unsupported firmware (" + version + ")"


def _require_max4(paths) -> None:
    try:
        soc_file = detect_firmware(paths.firmware_manifest_path).soc_file
    except FirmwareDetectionError:
        soc_file = None
    if not (soc_file or "").startswith("QD_MAX4_"):
        raise MainboardFirmwareError("The mainboard closed-loop reply fix is only for the QIDI Max 4.")


def _stock_image(paths, manifest) -> bytes | None:
    from scripts.flash_box_firmware import image_identity
    candidates = sorted((paths.printer_data_root / BACKUP_DIRECTORY).glob("*/before/application.bin"))
    candidates += sorted((paths.printer_data_root.parent / "update").glob("QD_MAX4_MCU_" + manifest["mcu"]["stock_version"] + "_*.bin"))
    for candidate in candidates:
        try:
            data = candidate.read_bytes()
        except OSError:
            continue
        if image_identity(data, manifest) == "stock":
            return data
    return None


def run_mainboard_firmware(
    *, paths, reporter, action, input_stream=None, environ=None,
    run=None, urlopen=urllib.request.urlopen, sleep=time.sleep, clock=time.monotonic,
    resolve_usb=usb_path_for_serial,
) -> int:
    from scripts import build_mcu_firmware
    from scripts import flash_box_firmware as protocol

    run = subprocess.run if run is None else run
    env = {} if environ is None else environ
    manifest = build_mcu_firmware.load_manifest(paths.bundle_root / MANIFEST)
    marker = paths.printer_data_root / MAINBOARD_RECOVERY_MARKER

    if action == "status":
        reporter.line("Mainboard: " + _describe(_version(paths, urlopen), manifest))
        if marker.exists():
            reporter.line("A mainboard firmware operation did not finish; run ./mainboard-firmware.sh rescue. Record: " + str(marker))
        return 0

    if env.get(LOCK_HELD_ENV) == "1":
        raise MainboardFirmwareError("Mainboard firmware programming is not allowed in automatic-update child installs.")
    if paths.restart_marker_path.exists():
        raise MainboardFirmwareError("Complete pending Klipper source activation before mainboard firmware programming.")
    ensure_no_pending_firmware(paths.recovery_sentinel_path, allow_mainboard=action == "rescue")
    _require_max4(paths)
    python = paths.printer_data_root.parent / "klippy-env/bin/python"
    tool = paths.bundle_root / "scripts/flash_mcu_firmware.py"
    if not tool.is_file() or tool.is_symlink() or not python.is_file():
        raise MainboardFirmwareError("Mainboard firmware requires the packaged tool and the existing klippy-env Python.")
    backup_root = paths.printer_data_root / BACKUP_DIRECTORY
    for target in (marker, backup_root):
        ensure_runtime_path_has_no_symlink_components(printer_data_root=paths.printer_data_root, target=target)

    target = "patched" if action == "install" else "stock"
    stock_image = None
    if action in ("restore", "rescue"):
        stock_image = _stock_image(paths, manifest)
        if stock_image is None:
            raise MainboardFirmwareError("No verified copy of QIDI's mainboard firmware " + manifest["mcu"]["stock_version"]
                                         + " was found in the mainboard firmware backups or ~/update.")
    if action == "rescue":
        previous_dirs = sorted(backup_root.glob("*/before/bootloader.bin"))
        if not previous_dirs:
            raise MainboardFirmwareError("No earlier backup of the mainboard's bootloader; rescue needs one from a previous mainboard-firmware run.")
        rescue_backup = previous_dirs[-1].parent
        record = rescue_backup.parent / "mainboard.json"
        usb = json.loads(record.read_text()).get("usb") if record.is_file() else None
        usb = usb or resolve_usb(mainboard_serial(paths))
        if usb is None:
            raise MainboardFirmwareError("Cannot find the mainboard's USB position.")
    else:
        usb = resolve_usb(mainboard_serial(paths))
        version = _version(paths, urlopen)
        reporter.line("Mainboard: " + _describe(version, manifest))
        wanted = manifest["mcu"]["patched_version" if target == "patched" else "stock_version"]
        if version == wanted:
            reporter.line("Nothing to flash.")
            return 0
        if usb is None or version is None:
            raise MainboardFirmwareError("The mainboard is not connected, or Klipper is not ready.")
        if version not in (manifest["mcu"]["stock_version"], manifest["mcu"]["patched_version"]):
            raise MainboardFirmwareError("The mainboard runs firmware this fix does not support: " + version)

    verb = {"install": "Install the closed-loop reply fix on", "restore": "Restore QIDI's stock firmware on",
            "rescue": "Rescue and restore QIDI's stock firmware on"}[action]
    reporter.line(WARNING)
    reporter.line(f"{verb} the mainboard. Klipper and the touchscreen stop for about three minutes; "
                  "the printer can't move or heat until they start again.")
    if input_stream is None:
        raise MainboardFirmwareError("mainboard-firmware needs an interactive terminal to confirm.")
    reporter.emit_prompt(question=f"Type {CONFIRMATION} to continue", instruction="Anything else cancels.")
    if input_stream.readline().strip() != CONFIRMATION:
        reporter.line("Cancelled. No mainboard firmware was changed.")
        return 1

    try:
        if action != "rescue":
            wait_for_thr_printer_ready(paths, urlopen=urlopen, sleep=sleep, clock=clock, reporter=reporter, subject=SUBJECT)
    except ThrFirmwareError as exc:
        raise MainboardFirmwareError(str(exc)) from exc
    states = {}
    for service in SERVICES:
        result = run(["systemctl", "show", service, "--property=LoadState,ActiveState"], capture_output=True, text=True, timeout=5)
        values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        if service.endswith(".timer") and values.get("LoadState") == "not-found":
            continue
        if result.returncode or values.get("LoadState") != "loaded" or values.get("ActiveState") not in {"active", "inactive"}:
            raise MainboardFirmwareError("Cannot establish serial service ownership: " + service)
        states[service] = values["ActiveState"]
    if action == "rescue" and marker.is_file():
        try:
            states = json.loads(marker.read_text()).get("services") or states
        except ValueError:
            pass
    password = authenticate_sudo(run=run, environ=env, reporter=reporter, input_stream=input_stream)
    backup_root.mkdir(mode=0o700, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="mainboard-", dir=backup_root))
    fsync_directory(backup_root)
    record = {"backup_directory": str(directory), "services": states, "action": action, "phase": "stopping_services", "usb": usb}
    atomic_write_text(marker, json.dumps(record, indent=2) + "\n", mode=0o600)
    atomic_write_text(directory / "mainboard.json", json.dumps({"usb": usb}) + "\n", mode=0o600)
    reporter.line("Mainboard firmware recovery files: " + str(directory))
    outcome = None
    pending = False

    def command(operation, *arguments, allow=()):
        result = run([str(python), str(tool), operation, *map(str, arguments), "--printer-idle-confirmed"],
                     capture_output=True, text=True, timeout=960)
        atomic_write_text(directory / (operation + ".stdout"), result.stdout or "", mode=0o600)
        atomic_write_text(directory / (operation + ".stderr"), result.stderr or "", mode=0o600)
        if result.returncode and result.returncode not in allow:
            raise MainboardFirmwareError("Mainboard " + operation + " failed; see " + str(directory))
        return result

    def service_action(verb_name, service):
        result = run_sudo(["systemctl", verb_name, service], run=run, password=password, timeout=60)
        if result.returncode:
            raise MainboardFirmwareError("Could not " + verb_name + " " + service)

    try:
        for service in reversed(SERVICES):
            if states.get(service) == "active":
                service_action("stop", service)
        if action == "rescue":
            before = rescue_backup
            image = stock_image
            reporter.line("Waiting for the mainboard's bootloader...")
            record.update(phase="programming")
            atomic_write_text(marker, json.dumps(record, indent=2) + "\n", mode=0o600)
            pending = True
            command("transfer", "--usb", usb, "--image", _write_image(directory, image),
                    "--backup-dir", before, "--confirm-write", "--rescue", "--wait", RESCUE_WAIT_SECONDS)
        else:
            before = directory / "before"
            reporter.line("Mainboard: reading and admitting its bootloader and firmware...")
            snapshot = command("snapshot", "--usb", usb, "--output-dir", before, allow=(protocol.UNSUPPORTED,))
            if snapshot.returncode == protocol.UNSUPPORTED:
                outcome = "not changed: unsupported bootloader or firmware; shareable summary " + str(before / "report.json")
            else:
                boot, app = protocol.load_backup(before, manifest)
                if protocol.image_identity(app, manifest) == target:
                    outcome = "already " + ("installed" if target == "patched" else "stock") + " (verified by readback)"
                else:
                    image = build_mcu_firmware.patch_mcu(app, manifest) if target == "patched" else stock_image
                    record.update(phase="programming")
                    atomic_write_text(marker, json.dumps(record, indent=2) + "\n", mode=0o600)
                    pending = True
                    reporter.line("Mainboard: flashing; keep the printer powered on...")
                    command("transfer", "--usb", usb, "--image", _write_image(directory, image),
                            "--backup-dir", before, "--confirm-write")
        if outcome is None:
            reporter.line("Mainboard: reading back its firmware...")
            after = directory / "after"
            command("snapshot", "--usb", usb, "--output-dir", after, "--wait", APP_RETURN_SECONDS)
            evidence = protocol.verify_readback(image, after, manifest,
                                                expected_bootloader=(before / "bootloader.bin").read_bytes())
            atomic_write_text(directory / "verification.json", json.dumps(evidence, indent=2) + "\n", mode=0o600)
            outcome = ("closed-loop reply fix installed" if target == "patched" else "QIDI stock firmware restored") + " and verified"
            pending = False
            record.update(phase="verified")
            atomic_write_text(marker, json.dumps(record, indent=2) + "\n", mode=0o600)
    except Exception as exc:
        failure = exc
    else:
        failure = None
    if pending:
        reporter.line("The mainboard firmware is unverified. Klipper and the touchscreen stay stopped. "
                      "Run ./mainboard-firmware.sh rescue and follow its prompt.")
        raise MainboardFirmwareError("Mainboard firmware operation failed: " + str(failure) + ". Recovery files: " + str(directory)) from failure
    try:
        for service in SERVICES:
            if states.get(service) == "active":
                service_action("start", service)
        if states.get("klipper.service") == "active":
            wait_for_thr_printer_ready(paths, urlopen=urlopen, sleep=sleep, clock=clock, subject=SUBJECT)
        atomic_delete(marker)
    except BaseException as exc:
        raise MainboardFirmwareError("Mainboard firmware service restoration is incomplete; recovery record retained: " + str(marker)) from exc
    if failure is not None:
        raise MainboardFirmwareError("Mainboard firmware operation stopped before any write: " + str(failure))
    reporter.line("Mainboard: " + outcome)
    return 0
