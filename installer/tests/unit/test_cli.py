from __future__ import annotations

import io
import unittest
from unittest.mock import call, patch

from installer.runtime.backup import create_config_backup
from installer.runtime.cli import main, resolve_runtime_paths
from installer.runtime.manifest import load_manifest
from installer.runtime.naming import INSTALL_BACKUP_LABEL_PREFIX, UNINSTALL_BACKUP_LABEL_PREFIX
from installer.runtime.reporter import PlainReporter
from installer.runtime.runner import run_install
from installer.tests.helpers import REPO_ROOT, build_env, copy_base_runtime, moonraker_server, snapshot_tree


class CliTests(unittest.TestCase):
    def test_clear_recovery_sentinel_requires_restored_backup_match(self):
        printer_root = copy_base_runtime()
        backup_zip = create_config_backup(
            printer_data_root=printer_root,
            source_directory="config",
            backup_label="recorded-backup",
        )
        sentinel = printer_root / ".tltg_optimized_recovery_required"
        sentinel.write_text(
            "error: write failed\n"
            f"backup_label: recorded-backup\n"
            f"backup_zip_path: {backup_zip}\n",
            encoding="utf-8",
        )
        printer_cfg = printer_root / "config/printer.cfg"
        original = printer_cfg.read_text(encoding="utf-8")
        printer_cfg.write_text(original + "\n# drift\n", encoding="utf-8")

        stream = io.StringIO()
        rc = main(
            ["clear-recovery-sentinel"],
            stream=stream,
            bundle_root=REPO_ROOT,
            environ=build_env(printer_root, moonraker_url="http://127.0.0.1:9/unused"),
        )
        self.assertEqual(rc, 1)
        self.assertTrue(sentinel.exists())
        self.assertIn("Recovery sentinel can only be cleared", stream.getvalue())

        printer_cfg.write_text(original, encoding="utf-8")
        stream = io.StringIO()
        rc = main(
            ["clear-recovery-sentinel"],
            stream=stream,
            bundle_root=REPO_ROOT,
            environ=build_env(printer_root, moonraker_url="http://127.0.0.1:9/unused"),
        )
        self.assertEqual(rc, 0)
        self.assertFalse(sentinel.exists())
        self.assertIn("Recovery sentinel cleared.", stream.getvalue())

    def test_install_cancellation_returns_zero_without_writing(self):
        printer_root = copy_base_runtime()
        stream = io.StringIO()
        with moonraker_server("standby") as url:
            rc = main(
                ["install", "--plain"],
                stream=stream,
                input_stream=io.StringIO("no\n"),
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=url),
            )

        self.assertEqual(rc, 0)
        self.assertFalse((printer_root / "config/tltg_optimized_state.yaml").exists())
        self.assertFalse((printer_root / "config/tltg-optimized-macros").exists())
        self.assertFalse(list(printer_root.glob(f"{INSTALL_BACKUP_LABEL_PREFIX}-*.zip")))
        output = stream.getvalue()
        self.assertIn("Would you like us to take a backup of your configs and proceed with installation?", output)
        self.assertIn("Installation cancelled.", output)

    def test_uninstall_cancellation_returns_zero_without_writing(self):
        printer_root = copy_base_runtime()
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        with moonraker_server("standby") as url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=url),
            )
            run_install(paths, manifest, PlainReporter(io.StringIO()))

        stream = io.StringIO()
        with moonraker_server("standby") as url:
            rc = main(
                ["uninstall", "--plain"],
                stream=stream,
                input_stream=io.StringIO("no\n"),
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=url),
            )

        self.assertEqual(rc, 0)
        self.assertTrue((printer_root / "config/tltg_optimized_state.yaml").exists())
        self.assertTrue((printer_root / "config/tltg-optimized-macros").exists())
        self.assertFalse(list(printer_root.glob(f"{UNINSTALL_BACKUP_LABEL_PREFIX}-*.zip")))
        output = stream.getvalue()
        self.assertIn("Are you sure you want to uninstall?", output)
        self.assertIn("Uninstall cancelled.", output)

    def test_install_demo_tui_returns_zero_without_writing(self):
        printer_root = copy_base_runtime()
        before = snapshot_tree(printer_root)
        stream = io.StringIO()
        with patch("installer.runtime.demo.time.sleep") as sleep_mock:
            rc = main(
                ["install", "--plain", "--demo-tui"],
                stream=stream,
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url="http://127.0.0.1:9/unused"),
            )

        self.assertEqual(rc, 0)
        self.assertEqual(snapshot_tree(printer_root), before)
        self.assertFalse((printer_root / "config/tltg_optimized_state.yaml").exists())
        self.assertFalse((printer_root / "config/tltg-optimized-macros").exists())
        self.assertFalse(list(printer_root.glob(f"{INSTALL_BACKUP_LABEL_PREFIX}-*.zip")))
        self.assertEqual(sleep_mock.call_args_list, [call(5.0)] * 5)
        output = stream.getvalue()
        self.assertIn("stage 1/5", output)
        self.assertIn("stage 5/5", output)
        self.assertIn("Installed.", output)
        self.assertNotIn("Would you like us to take a backup of your configs and proceed with installation?", output)

    def test_uninstall_demo_tui_returns_zero_without_writing(self):
        printer_root = copy_base_runtime()
        before = snapshot_tree(printer_root)
        stream = io.StringIO()
        with patch("installer.runtime.demo.time.sleep") as sleep_mock:
            rc = main(
                ["uninstall", "--plain", "--demo-tui"],
                stream=stream,
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url="http://127.0.0.1:9/unused"),
            )

        self.assertEqual(rc, 0)
        self.assertEqual(snapshot_tree(printer_root), before)
        self.assertFalse((printer_root / "config/tltg_optimized_state.yaml").exists())
        self.assertFalse((printer_root / "config/tltg-optimized-macros").exists())
        self.assertFalse(list(printer_root.glob(f"{UNINSTALL_BACKUP_LABEL_PREFIX}-*.zip")))
        self.assertEqual(sleep_mock.call_args_list, [call(5.0)] * 5)
        output = stream.getvalue()
        self.assertIn("stage 1/5", output)
        self.assertIn("checking installed package", output)
        self.assertIn("Uninstalled.", output)
        self.assertNotIn("Nothing to uninstall.", output)
        self.assertNotIn("Are you sure you want to uninstall?", output)
