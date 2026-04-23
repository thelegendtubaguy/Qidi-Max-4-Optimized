from __future__ import annotations

import io
import unittest

from installer.runtime.backup import create_config_backup
from installer.runtime.cli import main
from installer.tests.helpers import REPO_ROOT, build_env, copy_base_runtime


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
