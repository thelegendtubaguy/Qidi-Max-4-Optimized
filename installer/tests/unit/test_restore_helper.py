from __future__ import annotations

import io
import shutil
import unittest
from unittest import mock

from installer.runtime import backup as backup_runtime
from installer.runtime.backup import load_backup_snapshot, snapshot_runtime_tree
from installer.runtime.cli import resolve_runtime_paths
from installer.runtime.manifest import load_manifest
from installer.runtime.reporter import PlainReporter
from installer.runtime.restore_helper import run_restore_helper
from installer.runtime.runner import run_install
from installer.tests.helpers import REPO_ROOT, build_env, copy_base_runtime, MOONRAKER_QUERY_URL, moonraker_urlopen


class RestoreHelperTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest(REPO_ROOT / "installer/package.yaml")

    def test_restore_helper_supports_direct_restore_stages_before_live_write_and_restores_full_snapshot_without_clearing_sentinel(self):
        printer_root = copy_base_runtime()
        paths = resolve_runtime_paths(
            bundle_root=REPO_ROOT,
            environ=build_env(printer_root, moonraker_url=MOONRAKER_QUERY_URL),
        )
        install_result = run_install(paths, self.manifest, PlainReporter(io.StringIO()), urlopen=moonraker_urlopen())

        backup_zip = install_result.backup_zip_path
        self.assertIsNotNone(backup_zip)
        assert backup_zip is not None
        backup_snapshot = load_backup_snapshot(
            backup_zip_path=backup_zip,
            source_directory="config",
        )

        sentinel = printer_root / ".tltg_optimized_recovery_required"
        sentinel.write_text(
            "error: rollback failed\n"
            f"backup_label: {install_result.backup_label}\n"
            f"backup_zip_path: {backup_zip}\n",
            encoding="utf-8",
        )
        (printer_root / "config/printer.cfg").write_text("[printer]\n", encoding="utf-8")
        (printer_root / "config/box.cfg").write_text("[box_extras]\n", encoding="utf-8")
        state_path = printer_root / "config/tltg_optimized_state.yaml"
        if state_path.exists():
            state_path.unlink()
        managed_tree = printer_root / "config/tltg-optimized-macros"
        if managed_tree.exists():
            shutil.rmtree(managed_tree)
        drifted_runtime_snapshot = snapshot_runtime_tree(
            printer_data_root=printer_root,
            source_directory="config",
        )

        original_stage_backup_snapshot = backup_runtime.stage_backup_snapshot
        stage_observation: dict[str, object] = {}

        def stage_and_inspect(*args, **kwargs):
            staged = original_stage_backup_snapshot(*args, **kwargs)
            stage_observation["staged_snapshot"] = snapshot_runtime_tree(
                printer_data_root=staged.staging_root,
                source_directory="config",
            )
            self.assertEqual(stage_observation["staged_snapshot"], backup_snapshot)
            self.assertEqual(
                snapshot_runtime_tree(printer_data_root=printer_root, source_directory="config"),
                drifted_runtime_snapshot,
            )
            self.assertTrue((staged.source_root / "printer.cfg").exists())
            return staged

        stream = io.StringIO()
        with mock.patch(
            "installer.runtime.backup.stage_backup_snapshot",
            side_effect=stage_and_inspect,
        ):
            rc = run_restore_helper(
                paths,
                self.manifest,
                stream=stream,
                input_stream=io.StringIO("RESTORE\n"),
                backup_path=str(backup_zip),
            )

        self.assertEqual(rc, 0)
        self.assertEqual(stage_observation["staged_snapshot"], backup_snapshot)
        self.assertEqual(
            snapshot_runtime_tree(printer_data_root=printer_root, source_directory="config"),
            backup_snapshot,
        )
        self.assertTrue(sentinel.exists())
        output = stream.getvalue()
        self.assertIn("Warning: restore will overwrite current config changes under", output)
        self.assertIn("Recovery sentinel was not cleared.", output)
