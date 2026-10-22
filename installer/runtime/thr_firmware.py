from __future__ import annotations

import json
import math
import os
import subprocess
import tempfile
import time
import urllib.parse
import urllib.request
from pathlib import Path

from . import messages
from .auto_update import LOCK_HELD_ENV
from .errors import InstallerError
from .firmware import detect_firmware_version
from .fs_atomic import atomic_delete, atomic_write_bytes, atomic_write_text, fsync_directory
from .path_safety import ensure_runtime_path_has_no_symlink_components
from .safety import THR_RECOVERY_MARKER
from .sudo import authenticate_sudo, run_sudo


class ThrFirmwareError(InstallerError):
    pass


class ThrPrinterNotReady(ThrFirmwareError):
    pass


READY_TIMEOUT_SECONDS = 120


WARNING = (
    "THR firmware: do not power off the printer until this finishes. "
    "Rerun input shaper calibration before printing."
)


def _query(paths, names, urlopen):
    parts = urllib.parse.urlsplit(paths.moonraker_url)
    url = urllib.parse.urlunsplit(parts._replace(query="&".join(urllib.parse.quote(n, safe="") for n in names)))
    with urlopen(url, timeout=5) as response:
        status = json.load(response)["result"]["status"]
    if status["print_stats"]["state"] not in {"standby", "complete", "cancelled", "error"}:
        raise ThrFirmwareError("THR firmware requires an idle printer.")
    if status["webhooks"]["state"] != "ready" or status["idle_timeout"]["state"] not in {"Ready", "Idle"}:
        raise ThrPrinterNotReady("THR firmware requires Klipper ready and idle.")
    return status


def strip_input_shaper_calibration(text):
    header = text.find("\n#*# <---------------------- SAVE_CONFIG ---------------------->")
    if header < 0:
        return text
    lines = text[header:].splitlines(keepends=True)
    kept, in_section = [], False
    for line in lines:
        content = line[4:].strip() if line.startswith("#*# ") else None
        if content and content.startswith("["):
            in_section = content == "[input_shaper]"
        elif in_section and content:
            continue
        kept.append(line)
    return text[:header] + "".join(kept)


def _clear_input_shaper_calibration(paths, directory, reporter):
    printer_cfg = paths.config_root / "printer.cfg"
    try:
        ensure_runtime_path_has_no_symlink_components(printer_data_root=paths.printer_data_root, target=printer_cfg)
        text = printer_cfg.read_text()
        cleared = strip_input_shaper_calibration(text)
        if cleared == text:
            return
        atomic_write_text(directory / "printer.cfg", text, mode=0o600)
        atomic_write_text(printer_cfg, cleared)
    except (OSError, InstallerError):
        reporter.line("Could not clear the saved input shaper calibration from printer.cfg; rerun input shaper calibration to replace it.")
        return
    reporter.line("Cleared the saved input shaper calibration from printer.cfg; input shaping stays off until you recalibrate.")


def check_thr_printer_ready(paths, *, urlopen=urllib.request.urlopen):
    try:
        names = ("print_stats", "webhooks", "idle_timeout", "heaters")
        status = _query(paths, names, urlopen)
        heaters = status["heaters"]["available_heaters"]
        if (not isinstance(heaters, list) or not 1 <= len(heaters) <= 32
                or not all(isinstance(n, str) and n for n in heaters)
                or len(set(heaters)) != len(heaters)
                or not {"extruder", "heater_bed", "heater_generic chamber"}.issubset(heaters)):
            raise ValueError("Incomplete heater registry")
        status = _query(paths, (*names, *heaters), urlopen)
        if status["heaters"]["available_heaters"] != heaters:
            raise ValueError("Heater registry changed during preflight")
        for name in heaters:
            target = status[name]["target"]
            if (isinstance(target, bool) or not isinstance(target, (int, float))
                    or not math.isfinite(target) or target != 0):
                raise ThrFirmwareError("THR firmware requires every heater target at zero: " + name)
    except ThrFirmwareError:
        raise
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise ThrPrinterNotReady("Could not verify idle/ready state and all heater targets for THR firmware.") from exc


def wait_for_thr_printer_ready(paths, *, urlopen, sleep, clock, reporter=None):
    deadline = clock() + READY_TIMEOUT_SECONDS
    waiting = False
    while True:
        try:
            return check_thr_printer_ready(paths, urlopen=urlopen)
        except ThrPrinterNotReady:
            if clock() >= deadline:
                raise
            if reporter is not None and not waiting:
                reporter.line("Waiting for Klipper to be ready before THR firmware...")
            waiting = True
            sleep(1)


def confirm_thr_firmware(*, paths, reporter, explicit=False, dry_run=False, input_stream=None, environ=None):
    env = {} if environ is None else environ
    if explicit or dry_run or input_stream is None or env.get(LOCK_HELD_ENV) == "1":
        return explicit
    if detect_firmware_version(paths.firmware_manifest_path) != "01.01.07.01":
        return False
    reporter.emit_prompt(question=messages.THR_FIRMWARE_PROMPT, instruction=messages.THR_FIRMWARE_PROMPT_INSTRUCTION)
    return input_stream.readline().strip().upper() in {"Y", "YES"}


def validate_thr_firmware_request(*, paths, environ):
    if environ.get(LOCK_HELD_ENV) == "1":
        raise ThrFirmwareError("THR firmware programming is not allowed in automatic-update child installs.")
    if detect_firmware_version(paths.firmware_manifest_path) != "01.01.07.01":
        raise ThrFirmwareError("The THR FIFO firmware option supports only Max 4 firmware 01.01.07.01.")


def flash_thr_firmware(
    *, paths, reporter, dry_run=False, input_stream=None, environ=None,
    run=None, urlopen=urllib.request.urlopen, sleep=time.sleep, clock=time.monotonic,
):
    from scripts import flash_thr_firmware as protocol
    from scripts.build_thr_firmware import patch_thr

    run = subprocess.run if run is None else run
    env = {} if environ is None else environ
    validate_thr_firmware_request(paths=paths, environ=env)
    if paths.restart_marker_path.exists():
        raise ThrFirmwareError("Complete pending Klipper source activation before THR firmware programming.")
    reporter.line(WARNING)
    wait_for_thr_printer_ready(paths, urlopen=urlopen, sleep=sleep, clock=clock, reporter=reporter)
    if dry_run:
        reporter.line("THR firmware dry-run: would back up and admit THR, skip an already-patched image, or flash and verify the FIFO fix. No UART or services accessed.")
        return

    manifest = json.loads((paths.bundle_root / "firmware/max4-thr-lis2dw-fifo-v1.json").read_text())
    tool = paths.bundle_root / "scripts/flash_thr_firmware.py"
    python = paths.printer_data_root.parent / "klippy-env/bin/python"
    if not tool.is_file() or tool.is_symlink() or not python.is_file():
        raise ThrFirmwareError("THR firmware requires the packaged tool and existing klippy-env Python.")
    marker = paths.printer_data_root / THR_RECOVERY_MARKER
    backup_root = paths.printer_data_root / ".tltg_thr_firmware_backups"
    for target in (marker, backup_root):
        ensure_runtime_path_has_no_symlink_components(printer_data_root=paths.printer_data_root, target=target)
    if marker.exists():
        raise ThrFirmwareError("Unresolved THR firmware operation: " + str(marker))
    states = {}
    for service in protocol.SERVICES:
        result = run(["systemctl", "show", service, "--property=LoadState,ActiveState"], capture_output=True, text=True, timeout=5)
        values = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
        if service == "tltg-optimized-auto-update.timer" and values.get("LoadState") == "not-found":
            continue
        if result.returncode or values.get("LoadState") != "loaded" or values.get("ActiveState") not in {"active", "inactive"}:
            raise ThrFirmwareError("Cannot establish serial service ownership: " + service)
        states[service] = values["ActiveState"]
    password = authenticate_sudo(run=run, environ=env, reporter=reporter, input_stream=input_stream)
    wait_for_thr_printer_ready(paths, urlopen=urlopen, sleep=sleep, clock=clock, reporter=reporter)
    backup_root.mkdir(mode=0o700, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="thr-", dir=backup_root))
    fsync_directory(backup_root)
    record = {"backup_directory": str(directory), "services": states, "phase": "stopping_services"}
    atomic_write_text(marker, json.dumps(record, indent=2) + "\n", mode=0o600)
    reporter.line("THR recovery files: " + str(directory))
    firmware_may_have_changed = False
    verified = False
    unsupported_summary = None

    def command(operation, *arguments, allow_unsupported=False):
        result = run(
            [str(python), str(tool), operation, *map(str, arguments), "--printer-idle-confirmed"],
            capture_output=True, text=True, timeout=960,
        )
        atomic_write_text(directory / (operation + ".stdout"), result.stdout or "", mode=0o600)
        atomic_write_text(directory / (operation + ".stderr"), result.stderr or "", mode=0o600)
        if result.returncode and not (allow_unsupported and result.returncode == protocol.UNSUPPORTED_BOOTLOADER):
            raise ThrFirmwareError("THR " + operation + " failed; see recovery files: " + str(directory))
        return result

    def service_action(action, service):
        result = run_sudo(["systemctl", action, service], run=run, password=password, timeout=60)
        if result.returncode:
            raise ThrFirmwareError("Could not " + action + " " + service)

    try:
        for service in reversed(protocol.SERVICES):
            if service in states:
                service_action("stop", service)
        before = directory / "before"
        reporter.line("Reading and admitting THR application and bootloader...")
        snapshot = command("snapshot", "--output-dir", before, allow_unsupported=True)
        if snapshot.returncode == protocol.UNSUPPORTED_BOOTLOADER:
            boot = (before / "bootloader.bin").read_bytes()
            region = (before / "application-region.bin").read_bytes()
            summary = json.loads((before / "report.json").read_text())
            if (len(boot) != 0x8000 or len(region) != 0x18000
                    or protocol.digest(boot) in protocol.thr_bootloaders.ADMITTED_BOOTLOADERS
                    or summary.get("bootloader_sha256") != protocol.digest(boot)
                    or summary.get("application_region_sha256") != protocol.digest(region)):
                raise ThrFirmwareError("Incomplete unsupported-bootloader capture")
            fsync_directory(before)
            fsync_directory(directory)
            unsupported_summary = before / "report.json"
            return
        boot, app = protocol.load_backup(before, manifest)
        for path in before.iterdir():
            with path.open("rb") as handle:
                os.fsync(handle.fileno())
        fsync_directory(before)
        fsync_directory(directory)
        if protocol.digest(app) == manifest["thr"]["patched_sha256"]:
            evidence = protocol.verify_readback(app, before, manifest)
            reporter.line("THR FIFO fix is already installed; no reset, erase, or transfer required.")
        else:
            image = patch_thr(app, manifest)
            image_path = directory / "patched-thr.bin"
            atomic_write_bytes(image_path, image, mode=0o600)
            record["phase"] = "programming"
            atomic_write_text(marker, json.dumps(record, indent=2) + "\n", mode=0o600)
            firmware_may_have_changed = True
            reporter.line("Flashing the admitted THR FIFO fix; keep printer power on...")
            command("transfer", "--image", image_path, "--backup-dir", before, "--reset", "--confirm-write")
            sleep(12)
            after = directory / "after"
            reporter.line("Reading back the complete THR application and bootloader...")
            command("snapshot", "--output-dir", after)
            evidence = protocol.verify_readback(image, after, manifest, expected_bootloader=boot)
        atomic_write_text(directory / "verification.json", json.dumps(evidence, indent=2) + "\n", mode=0o600)
        verified = True
        if firmware_may_have_changed:
            _clear_input_shaper_calibration(paths, directory, reporter)
    except Exception as exc:
        raise ThrFirmwareError("THR firmware operation failed; configuration installation is retained. Recovery files: " + str(directory) + ". " + str(exc)) from exc
    finally:
        if verified or not firmware_may_have_changed:
            try:
                if states.get("klipper.service") == "active":
                    reporter.line(messages.KLIPPER_SERVICE_RESTARTING)
                for service in protocol.SERVICES:
                    if states.get(service) == "active":
                        service_action("start", service)
                if states.get("klipper.service") == "active":
                    wait_for_thr_printer_ready(paths, urlopen=urlopen, sleep=sleep, clock=clock)
                atomic_delete(marker)
            except BaseException as exc:
                raise ThrFirmwareError("THR service restoration/readiness is incomplete; recovery marker retained: " + str(marker)) from exc
            if unsupported_summary is not None:
                reporter.line("The THR FIFO fix is unavailable for this bootloader. Your THR firmware was not changed. Please attach this shareable summary to a GitHub issue at https://github.com/thelegendtubaguy/Qidi-Max-4-Optimized/issues: " + str(unsupported_summary))
        else:
            reporter.line("THR firmware is unverified. Serial-owning services remain stopped. Recovery files: " + str(directory))
            reporter.line("Recover and verify THR before removing the firmware blocker: " + str(marker))
    reporter.line("THR FIFO firmware verified; bootloader unchanged and previous service states restored.")
    if firmware_may_have_changed:
        reporter.line("Rerun input shaper calibration before printing. The installer has not run calibration.")
