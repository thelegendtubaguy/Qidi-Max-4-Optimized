from __future__ import annotations

import hashlib
import io
import json
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch

from installer.runtime import box_firmware
from installer.runtime.auto_update import LOCK_HELD_ENV
from installer.runtime.cli import main, parse_args, resolve_runtime_paths
from installer.runtime.errors import InstallerError
from installer.runtime.models import InstallResult
from installer.runtime.reporter import create_reporter
from installer.runtime.safety import BOX_RECOVERY_MARKER, ensure_no_recovery_sentinel
from installer.tests.helpers import REPO_ROOT, build_env, copy_base_runtime, temp_path
from scripts import flash_box_firmware as protocol
from scripts.build_box_firmware import patch_box

USB = {"mcu_box1": "2-1.4.2", "mcu_box2": "2-1.4.1.2"}


def synthetic_manifest():
    manifest = json.loads((REPO_ROOT / "firmware/max4-box-shutdown-fix-v1.json").read_text())
    box = manifest["box"]
    stock = bytearray(box["size"])
    for entry in box["patches"]:
        if "before" in entry:
            offset = int(entry["offset"], 0)
            value = bytes.fromhex(entry["before"])
            stock[offset:offset + len(value)] = value
    for entry in box["patches"]:
        if "before_sha256" in entry:
            offset = int(entry["offset"], 0)
            entry["before_sha256"] = hashlib.sha256(stock[offset:offset + len(bytes.fromhex(entry["after"]))]).hexdigest()
    image = bytearray(stock)
    for entry in box["patches"]:
        offset = int(entry["offset"], 0)
        value = bytes.fromhex(entry["after"])
        image[offset:offset + len(value)] = value
    box["stock_sha256"] = hashlib.sha256(stock).hexdigest()
    box["patched_sha256"] = hashlib.sha256(image).hexdigest()
    boot = bytes(range(256)) * 128
    manifest["bootloaders"] = [{"sha256": hashlib.sha256(boot).hexdigest(), "identity_reply": "0112"}]
    return manifest, bytes(stock), boot


class Printer:
    def __init__(self, manifest, stock, boot, apps, *, failure=None):
        self.manifest, self.boot, self.failure = manifest, boot, failure
        self.apps = {name: (patch_box(stock, manifest) if kind == "patched" else stock) for name, kind in apps.items()}
        self.states = {"klipper.service": "active", "qidi-client.service": "active",
                       "tltg-optimized-auto-update.timer": "inactive"}
        self.original = dict(self.states)
        self.transfers = []
        self.print_state = "standby"
        self.chamber = 0

    def urlopen(self, url, timeout=5):
        status = {"print_stats": {"state": self.print_state}, "webhooks": {"state": "ready"},
                  "idle_timeout": {"state": "Ready"},
                  "heaters": {"available_heaters": ["extruder", "heater_bed", "heater_generic chamber"]},
                  "extruder": {"target": 0}, "heater_bed": {"target": 0}, "heater_generic chamber": {"target": self.chamber}}
        for name, app in self.apps.items():
            kind = protocol.image_identity(app, self.manifest)
            status["mcu " + name] = {"mcu_version": self.manifest["box"]["patched_version" if kind == "patched" else "stock_version"]}
        return io.BytesIO(json.dumps({"result": {"status": status}}).encode())

    def run(self, command, **kwargs):
        command = list(command)

        def result(code=0, output=""):
            return subprocess.CompletedProcess(command, code, stdout=output, stderr="")

        if command[:4] == ["sudo", "-S", "-p", ""]:
            command = command[4:]
        if command == ["-v"]:
            return result()
        if command[:2] == ["systemctl", "show"]:
            return result(output="LoadState=loaded\nActiveState=" + self.states[command[2]] + "\n")
        if command[0] == "systemctl":
            self.states[command[2]] = "inactive" if command[1] == "stop" else "active"
            return result()
        assert command[1].endswith("/scripts/flash_box_firmware.py"), command
        assert all(state == "inactive" for state in self.states.values()), "serial access while services run"
        name = {usb: box for box, usb in USB.items()}[command[command.index("--usb") + 1]]
        if command[2] == "snapshot":
            destination = Path(command[command.index("--output-dir") + 1])
            destination.mkdir()
            boot = self.boot if self.failure != "unknown-boot" else bytes(0x8000)
            report = protocol.save_snapshot(destination, boot, self.apps[name] + bytes(1024), self.manifest)
            ok = report["supported_bootloader"] and report["application"] != "unrecognized"
            return result(0 if ok else protocol.UNSUPPORTED)
        if command[2] == "transfer":
            self.transfers.append((name, "--rescue" in command))
            if self.failure == "transfer" and not self.transfers[-1][1]:
                self.apps[name] = b""
                return result(1)
            self.apps[name] = Path(command[command.index("--image") + 1]).read_bytes()
            return result()
        raise AssertionError(command)


class BoxFirmwareFlowTests(unittest.TestCase):
    def fixture(self, apps, **kwargs):
        root = temp_path("box-firmware-flow-")
        manifest, stock, boot = synthetic_manifest()
        bundle = root / "bundle"
        (bundle / "scripts").mkdir(parents=True)
        (bundle / "firmware").mkdir()
        (bundle / "scripts/flash_box_firmware.py").write_text("# fixture")
        (bundle / "firmware/max4-box-shutdown-fix-v1.json").write_text(json.dumps(manifest))
        data = root / "printer_data"
        (data / "config").mkdir(parents=True)
        (data / "config/box.cfg").write_text("".join(f"[mcu {name}]\nserial: /dev/serial/by-id/{name}\n\n" for name in apps))
        (root / "klippy-env/bin").mkdir(parents=True)
        (root / "klippy-env/bin/python").write_text("")
        paths = resolve_runtime_paths(bundle_root=bundle, environ=build_env(data, moonraker_url="http://printer.invalid/printer/objects/query"))
        printer = Printer(manifest, stock, boot, apps, **kwargs)
        reporter = create_reporter(io.StringIO(), prefer_plain=True, bundle_root=REPO_ROOT, environ={})
        return paths, printer, reporter

    def execute(self, paths, printer, reporter, action, answer="FLASH\n", **kwargs):
        return box_firmware.run_box_firmware(
            paths=paths, reporter=reporter, action=action, input_stream=io.StringIO(answer),
            run=printer.run, urlopen=printer.urlopen, sleep=lambda seconds: None,
            clock=iter(range(0, 10 ** 6, 10)).__next__, resolve_usb=lambda serial: USB[serial.rsplit("/", 1)[1]], **kwargs)

    def test_install_and_restore_flash_only_boxes_that_need_it_and_verify(self):
        paths, printer, reporter = self.fixture({"mcu_box1": "stock", "mcu_box2": "patched"})
        self.assertEqual(self.execute(paths, printer, reporter, "install"), 0)
        self.assertEqual(printer.transfers, [("mcu_box1", False)])
        self.assertEqual({protocol.image_identity(app, printer.manifest) for app in printer.apps.values()}, {"patched"})
        self.assertEqual(printer.states, printer.original)
        self.assertFalse((paths.printer_data_root / BOX_RECOVERY_MARKER).exists())
        verification, = (paths.printer_data_root / box_firmware.BACKUP_DIRECTORY).glob("*/mcu_box1/verification.json")
        self.assertTrue(json.loads(verification.read_text())["verified"])
        self.assertEqual(self.execute(paths, printer, reporter, "restore", boxes=[2]), 0)
        self.assertEqual(printer.transfers[-1], ("mcu_box2", False))
        self.assertEqual(protocol.image_identity(printer.apps["mcu_box2"], printer.manifest), "stock")
        self.assertEqual(printer.states, printer.original)

    def test_unsupported_bootloader_is_captured_without_programming(self):
        paths, printer, reporter = self.fixture({"mcu_box1": "stock"}, failure="unknown-boot")
        self.assertEqual(self.execute(paths, printer, reporter, "install"), 0)
        self.assertEqual(printer.transfers, [])
        self.assertEqual(printer.states, printer.original)
        self.assertFalse((paths.printer_data_root / BOX_RECOVERY_MARKER).exists())
        self.assertIn("not changed: unsupported bootloader", reporter.stream.getvalue())

    def test_unsafe_states_and_cancellation_never_touch_services(self):
        for case in ("printing", "chamber-hot", "cancel", "automatic-update"):
            with self.subTest(case=case):
                paths, printer, reporter = self.fixture({"mcu_box1": "stock"})
                printer.print_state = "printing" if case == "printing" else "standby"
                printer.chamber = 60 if case == "chamber-hot" else 0
                environ = {LOCK_HELD_ENV: "1"} if case == "automatic-update" else None
                if case == "cancel":
                    self.assertEqual(self.execute(paths, printer, reporter, "install", answer="flash\n"), 1)
                else:
                    with self.assertRaises(InstallerError):
                        self.execute(paths, printer, reporter, "install", environ=environ)
                self.assertEqual(printer.transfers, [])
                self.assertEqual(printer.states, printer.original)

    def test_failed_write_blocks_installer_until_rescue_restores_stock(self):
        paths, printer, reporter = self.fixture({"mcu_box1": "stock"}, failure="transfer")
        with self.assertRaises(box_firmware.BoxFirmwareError):
            self.execute(paths, printer, reporter, "install")
        self.assertTrue((paths.printer_data_root / BOX_RECOVERY_MARKER).is_file())
        self.assertTrue(all(state == "inactive" for state in printer.states.values()))
        self.assertIn("rescue --box 1", reporter.stream.getvalue())
        with self.assertRaises(InstallerError):
            ensure_no_recovery_sentinel(paths.recovery_sentinel_path)
        with self.assertRaises(InstallerError):
            self.execute(paths, printer, reporter, "install")
        self.assertEqual(self.execute(paths, printer, reporter, "rescue", boxes=[1]), 0)
        self.assertEqual(printer.transfers[-1], ("mcu_box1", True))
        self.assertEqual(protocol.image_identity(printer.apps["mcu_box1"], printer.manifest), "stock")
        self.assertEqual(printer.states, printer.original)
        self.assertFalse((paths.printer_data_root / BOX_RECOVERY_MARKER).exists())

    def test_box_firmware_is_only_reachable_through_its_own_mode(self):
        self.assertEqual(parse_args(["box-firmware", "install", "--box", "1"]).box, [1])
        for argv in (["box-firmware"], ["box-firmware", "install", "--yes"], ["install", "--box", "1"], ["install", "install"]):
            with self.subTest(argv=argv), self.assertRaises(SystemExit):
                parse_args(argv)
        root = copy_base_runtime()
        env = build_env(root, moonraker_url="http://printer.invalid")
        with patch("installer.runtime.cli.run_install", return_value=InstallResult((), (), "label", None)), \
                patch("installer.runtime.cli.run_box_firmware", side_effect=AssertionError("Unexpected Box firmware access")):
            self.assertEqual(main(["install", "--yes", "--plain"], bundle_root=REPO_ROOT, environ=env, stream=io.StringIO()), 0)


if __name__ == "__main__":
    unittest.main()
