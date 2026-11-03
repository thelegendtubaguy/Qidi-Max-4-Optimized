from __future__ import annotations

import io
import os
import subprocess
import unittest
from pathlib import Path
from unittest import mock

from installer.runtime import ownership
from installer.runtime.models import RuntimePaths
from installer.runtime.ownership import OwnershipRepairError, repair_installer_ownership
from installer.runtime.reporter import create_reporter
from installer.tests.helpers import REPO_ROOT, temp_path


def _printer(root: Path) -> RuntimePaths:
    home = root / "home/qidi"
    printer_data = home / "printer_data"
    (printer_data / "config/tltg-optimized-macros").mkdir(parents=True)
    (printer_data / "model").mkdir()
    (home / "update").mkdir()
    (home / "tltg-optimized-macros/installer").mkdir(parents=True)
    (home / "klipper/klippy/extras").mkdir(parents=True)
    return RuntimePaths(
        bundle_root=REPO_ROOT,
        installer_root=REPO_ROOT / "installer",
        printer_data_root=printer_data,
        config_root=printer_data / "config",
        firmware_manifest_path=home / "update/firmware_manifest.json",
        moonraker_url="http://127.0.0.1:7125",
        lock_path=printer_data / ".tltg_optimized_installer.lock",
        recovery_sentinel_path=printer_data / ".tltg_optimized_recovery_required",
        backup_root=printer_data,
        klipper_root=home / "klipper",
    )


def _write(path: Path) -> Path:
    path.write_text("x\n", encoding="utf-8")
    return path


class InstallerOwnershipRepairTests(unittest.TestCase):
    def setUp(self):
        self.root = temp_path("ownership-")
        self.paths = _printer(self.root)
        self.home = self.paths.printer_data_root.parent
        self.calls: list[list[str]] = []

    def _run(self, command, **kwargs):
        self.calls.append(list(command))
        return subprocess.CompletedProcess(command, 0)

    def _repair(self, root_owned: set[Path]) -> int:
        owner = os.getuid()
        with mock.patch.object(ownership, "_owner", lambda path: 0 if path in root_owned else owner):
            return repair_installer_ownership(
                self.paths,
                reporter=create_reporter(io.StringIO(), prefer_plain=True),
                environ={},
                run=self._run,
            )

    def _chowned(self) -> dict[str, set[str]]:
        result: dict[str, set[str]] = {}
        for command in self.calls:
            if "chown" not in command:
                continue
            args = command[command.index("chown") + 1:]
            flags = " ".join(arg for arg in args[: args.index("--")] if arg.startswith("-"))
            result.setdefault(flags, set()).update(args[args.index("--") + 1:])
        return result

    def test_gives_installer_files_left_by_root_back_without_touching_qidi_files(self):
        config = self.paths.config_root
        outside = _write(self.root / "outside.cfg")
        installer_owned = {
            _write(self.paths.lock_path),
            _write(config / "tltg_optimized_state.yaml"),
            _write(config / "tltg-optimized-macros/cooling.cfg"),
            _write(self.home / "klipper/klippy/extras/tltg_box_eject.py"),
            self.home / "tltg-optimized-macros",
        }
        link = config / "tltg-link.cfg"
        link.symlink_to(outside)
        qidi_owned = {
            _write(config / "box.cfg"),
            _write(self.paths.printer_data_root / "model/part.gcode.3mf"),
            _write(self.home / "update/QD_MAX4_BOX.bin"),
            _write(self.home / "klipper/klippy/extras/box_stepper.py"),
            outside,
        }

        changed = self._repair(installer_owned | qidi_owned | {link})

        self.assertEqual(changed, len(installer_owned) + 1)
        chowned = self._chowned()
        self.assertEqual(chowned["-R -h"], {str(self.home / "tltg-optimized-macros")})
        self.assertEqual(
            chowned["-h"],
            {str(path) for path in installer_owned | {link}} - {str(self.home / "tltg-optimized-macros")},
        )
        everything = set().union(*chowned.values())
        self.assertFalse(everything & {str(path) for path in qidi_owned})

    def test_does_nothing_when_installer_files_already_belong_to_the_user(self):
        _write(self.paths.lock_path)

        self.assertEqual(self._repair(set()), 0)
        self.assertEqual(self.calls, [])

    def test_stops_when_sudo_cannot_give_files_back(self):
        lock = _write(self.paths.lock_path)

        def refuse(command, **kwargs):
            self.calls.append(list(command))
            return subprocess.CompletedProcess(command, 1)

        self._run = refuse
        with self.assertRaises(OwnershipRepairError):
            self._repair({lock})
        self.assertFalse(any("chown" in command for command in self.calls))


if __name__ == "__main__":
    unittest.main()
