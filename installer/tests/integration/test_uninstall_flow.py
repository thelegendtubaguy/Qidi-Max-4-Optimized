from __future__ import annotations

import io
import unittest

from installer.runtime.cli import resolve_runtime_paths
from installer.runtime.compatibility import load_supported_upgrade_sources
from installer.runtime.errors import InstalledPackageValidationError
from installer.runtime.manifest import load_manifest
from installer.runtime.reporter import PlainReporter
from installer.runtime.runner import run_install
from installer.runtime.uninstall import run_uninstall
from installer.tests.helpers import REPO_ROOT, build_env, copy_base_runtime, moonraker_server


class UninstallFlowTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        self.compatibility = load_supported_upgrade_sources(
            REPO_ROOT / "installer/supported_upgrade_sources.yaml"
        )

    def _install_first(self):
        printer_root = copy_base_runtime()
        with moonraker_server("standby") as url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=url),
            )
            run_install(paths, self.manifest, PlainReporter(io.StringIO()))
        return printer_root

    def test_happy_path_uninstall(self):
        printer_root = self._install_first()
        stream = io.StringIO()
        with moonraker_server("standby") as url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=url),
            )
            result = run_uninstall(
                paths,
                self.manifest,
                self.compatibility,
                PlainReporter(stream),
            )
        self.assertFalse((paths.config_root / "tltg_optimized_state.yaml").exists())
        self.assertFalse((paths.config_root / "tltg-optimized-macros").exists())
        printer_cfg = (paths.config_root / "printer.cfg").read_text(encoding="utf-8")
        self.assertNotIn("[include tltg-optimized-macros/*.cfg]", printer_cfg)
        self.assertIn("homing_speed: 50", printer_cfg)
        output = stream.getvalue()
        self.assertIn("stage 1/5", output)
        self.assertIn("Uninstalled.", output)
        self.assertIn("Restart Klipper to apply changes.", output)
        self.assertTrue(result.backup_zip_path.exists())

    def test_uninstall_fails_closed_when_markers_exist_without_valid_state(self):
        printer_root = copy_base_runtime()
        (printer_root / "config/tltg-optimized-macros").mkdir(parents=True)
        with moonraker_server("standby") as url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=url),
            )
            with self.assertRaises(InstalledPackageValidationError):
                run_uninstall(
                    paths,
                    self.manifest,
                    self.compatibility,
                    PlainReporter(io.StringIO()),
                )
