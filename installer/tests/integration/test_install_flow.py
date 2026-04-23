from __future__ import annotations

import io
import unittest

from installer.runtime.cli import resolve_runtime_paths
from installer.runtime.errors import PreflightTargetsError
from installer.runtime.manifest import load_manifest
from installer.runtime.reporter import PlainReporter
from installer.runtime.runner import run_install
from installer.tests.helpers import REPO_ROOT, build_env, copy_base_runtime, moonraker_server


class InstallFlowTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest(REPO_ROOT / "installer/package.yaml")

    def test_happy_path_install(self):
        printer_root = copy_base_runtime()
        stream = io.StringIO()
        with moonraker_server("standby") as url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=url),
            )
            result = run_install(paths, self.manifest, reporter=PlainReporter(stream))

        self.assertTrue((paths.config_root / "tltg_optimized_state.yaml").exists())
        printer_cfg = (paths.config_root / "printer.cfg").read_text(encoding="utf-8")
        self.assertIn("[include tltg-optimized-macros/*.cfg]", printer_cfg)
        self.assertIn("homing_speed: 65", printer_cfg)
        self.assertTrue((paths.config_root / "tltg-optimized-macros").exists())
        output = stream.getvalue()
        self.assertIn("stage 1/5", output)
        self.assertIn("Installed.", output)
        self.assertIn("Restart Klipper to apply changes.", output)
        self.assertTrue(result.backup_zip_path.exists())

    def test_missing_patch_target_fails_closed(self):
        printer_root = copy_base_runtime()
        printer_cfg = printer_root / "config/printer.cfg"
        printer_cfg.write_text(
            printer_cfg.read_text(encoding="utf-8").replace("homing_speed: 50\n", "", 1),
            encoding="utf-8",
        )
        with moonraker_server("standby") as url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=url),
            )
            with self.assertRaises(PreflightTargetsError) as exc:
                run_install(paths, self.manifest, PlainReporter(io.StringIO()))
        self.assertEqual(exc.exception.report.patch_target_issues[0].reason, "missing")
