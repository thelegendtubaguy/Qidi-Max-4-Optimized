from __future__ import annotations

import io
import unittest
from unittest.mock import call, patch

from installer.runtime.backup import create_config_backup
from installer.runtime.errors import LockAcquisitionError
from installer.runtime.cli import main, resolve_runtime_paths
from installer.runtime.manifest import load_manifest
from installer.runtime.naming import INSTALL_BACKUP_LABEL_PREFIX, UNINSTALL_BACKUP_LABEL_PREFIX
from installer.runtime.reporter import PlainReporter
from installer.runtime.runner import run_install
from installer.tests.helpers import REPO_ROOT, build_env, copy_base_runtime, MOONRAKER_QUERY_URL, moonraker_server, moonraker_urlopen, snapshot_tree


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

    def test_auto_update_check_honors_recovery_sentinel_before_running(self):
        printer_root = copy_base_runtime()
        (printer_root / ".tltg_optimized_recovery_required").write_text("recovery required\n", encoding="utf-8")
        stream = io.StringIO()
        with patch("installer.runtime.cli.run_auto_update_check") as auto_update_check:
            rc = main(
                ["auto-update-check", "--plain", "--yes"],
                stream=stream,
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url="http://127.0.0.1:9/unused"),
            )

        self.assertEqual(rc, 1)
        auto_update_check.assert_not_called()
        self.assertIn("Previous recovery did not complete. Restore from backup before continuing.", stream.getvalue())

    def test_auto_update_check_honors_installer_lock_before_running(self):
        printer_root = copy_base_runtime()
        stream = io.StringIO()
        with patch("installer.runtime.cli.acquire", side_effect=LockAcquisitionError("locked")), patch(
            "installer.runtime.cli.run_auto_update_check"
        ) as auto_update_check:
            rc = main(
                ["auto-update-check", "--plain", "--yes"],
                stream=stream,
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url="http://127.0.0.1:9/unused"),
            )

        self.assertEqual(rc, 1)
        auto_update_check.assert_not_called()
        self.assertIn("locked", stream.getvalue())

    def test_keyboard_interrupt_returns_130_without_traceback(self):
        printer_root = copy_base_runtime()
        stream = io.StringIO()
        with moonraker_server("standby") as url:
            with patch("installer.runtime.cli.run_install", side_effect=KeyboardInterrupt):
                rc = main(
                    ["install", "--plain", "--yes"],
                    stream=stream,
                    bundle_root=REPO_ROOT,
                    environ=build_env(printer_root, moonraker_url=url),
                )

        self.assertEqual(rc, 130)
        output = stream.getvalue()
        self.assertIn("Interrupted. No further installer actions will run.", output)
        self.assertNotIn("Traceback", output)

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

    def test_install_prompts_auto_updates_before_restart(self):
        printer_root = copy_base_runtime()
        stream = io.StringIO()
        with moonraker_server("standby") as url:
            rc = main(
                ["install", "--plain"],
                stream=stream,
                input_stream=io.StringIO("yes\nno\nno\n"),
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=url),
            )

        self.assertEqual(rc, 0)
        output = stream.getvalue()
        auto_prompt_index = output.index(
            "Would you like to enable hourly automatic optimized config updates using a systemd timer?"
        )
        restart_prompt_index = output.index("Would you like me to restart Klipper to apply changes?")
        self.assertLess(auto_prompt_index, restart_prompt_index)
        self.assertIn("Auto-updates not enabled.", output)
        self.assertIn("Restart Klipper to apply changes.", output)

    def test_uninstall_cancellation_returns_zero_without_writing(self):
        printer_root = copy_base_runtime()
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        paths = resolve_runtime_paths(
            bundle_root=REPO_ROOT,
            environ=build_env(printer_root, moonraker_url=MOONRAKER_QUERY_URL),
        )
        run_install(paths, manifest, PlainReporter(io.StringIO()), urlopen=moonraker_urlopen())

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

    def test_uninstall_disables_auto_updates_before_restart_prompt(self):
        printer_root = copy_base_runtime()
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        paths = resolve_runtime_paths(
            bundle_root=REPO_ROOT,
            environ=build_env(printer_root, moonraker_url=MOONRAKER_QUERY_URL),
        )
        run_install(paths, manifest, PlainReporter(io.StringIO()), urlopen=moonraker_urlopen())

        def fake_disable_auto_updates(*, paths, reporter, input_stream, require_sudo):
            reporter.line("Auto-updates disabled.")

        stream = io.StringIO()
        with moonraker_server("standby") as url:
            with patch("installer.runtime.uninstall.auto_updates_configured", return_value=True), patch(
                "installer.runtime.uninstall.disable_auto_updates",
                side_effect=fake_disable_auto_updates,
            ):
                rc = main(
                    ["uninstall", "--plain"],
                    stream=stream,
                    input_stream=io.StringIO("yes\nno\n"),
                    bundle_root=REPO_ROOT,
                    environ=build_env(printer_root, moonraker_url=url),
                )

        self.assertEqual(rc, 0)
        output = stream.getvalue()
        disable_index = output.index("Auto-updates disabled.")
        restart_prompt_index = output.index("Would you like me to restart Klipper to apply changes?")
        self.assertLess(disable_index, restart_prompt_index)
        self.assertIn("Restart Klipper to apply changes.", output)

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
