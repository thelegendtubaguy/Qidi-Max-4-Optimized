from __future__ import annotations

import io
import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from installer.runtime import backup as backup_runtime
from installer.runtime import klipper_cfg
from installer.runtime.backup import BackupArchiveError, create_config_backup, restore_staged_snapshot_tree
from installer.runtime.cli import resolve_runtime_paths
from installer.runtime.errors import ManagedTreeSourceError, PathSafetyError, PreflightTargetsError
from installer.runtime.manifest import load_manifest
from installer.runtime.mirror import validate_managed_tree_source
from installer.runtime.models import InstalledState, ManagedTreeState
from installer.runtime.reporter import PlainReporter
from installer.runtime.runner import run_install
from installer.runtime.state_file import write_installed_state
from installer.tests.helpers import REPO_ROOT, build_env, copy_base_runtime, moonraker_server, snapshot_tree


class InstallerHardeningTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest(REPO_ROOT / "installer/package.yaml")

    def test_managed_tree_source_must_exist_before_backup_or_runtime_write(self):
        printer_root = copy_base_runtime()
        missing_installer_root = Path(tempfile.mkdtemp(prefix="missing-installer-root-"))
        with moonraker_server("standby") as url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=url),
            )
            paths = type(paths)(
                bundle_root=paths.bundle_root,
                installer_root=missing_installer_root,
                printer_data_root=paths.printer_data_root,
                config_root=paths.config_root,
                firmware_manifest_path=paths.firmware_manifest_path,
                moonraker_url=paths.moonraker_url,
                lock_path=paths.lock_path,
                recovery_sentinel_path=paths.recovery_sentinel_path,
                backup_root=paths.backup_root,
            )
            before = snapshot_tree(printer_root)
            with self.assertRaises(ManagedTreeSourceError):
                run_install(paths, self.manifest, PlainReporter(io.StringIO()))

        self.assertEqual(snapshot_tree(printer_root), before)
        self.assertFalse(any(printer_root.glob("*.zip")))

    def test_managed_tree_source_must_contain_manifest_required_files(self):
        source_root = Path(tempfile.mkdtemp(prefix="managed-tree-source-"))
        (source_root / "bed_mesh.cfg").write_text("[gcode_macro g29]\n", encoding="utf-8")

        with self.assertRaises(ManagedTreeSourceError):
            validate_managed_tree_source(
                source_root,
                required_files=("bed_mesh.cfg", "kinematics.cfg"),
            )

    def test_install_postflight_verifies_managed_tree_content_hashes(self):
        from installer.runtime.postflight import verify_install_postflight

        printer_root = copy_base_runtime()
        destination = printer_root / "config/tltg-optimized-macros"
        shutil.copytree(REPO_ROOT / "installer/klipper/tltg-optimized-macros", destination)
        (destination / "kinematics.cfg").write_text("corrupt\n", encoding="utf-8")
        with moonraker_server("standby") as url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=url),
            )

        with self.assertRaises(PreflightTargetsError) as raised:
            verify_install_postflight(paths=paths, manifest=self.manifest)
        self.assertIn(
            "config/tltg-optimized-macros/kinematics.cfg",
            raised.exception.report.missing_files,
        )

    def test_symlinked_managed_tree_destination_is_rejected_before_mirror(self):
        printer_root = copy_base_runtime()
        outside = Path(tempfile.mkdtemp(prefix="managed-tree-outside-"))
        (outside / "keep.cfg").write_text("keep\n", encoding="utf-8")
        (printer_root / "config/tltg-optimized-macros").symlink_to(outside, target_is_directory=True)
        with moonraker_server("standby") as url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=url),
            )
            with self.assertRaises(PathSafetyError):
                run_install(paths, self.manifest, PlainReporter(io.StringIO()))
        self.assertEqual((outside / "keep.cfg").read_text(encoding="utf-8"), "keep\n")

    def test_restore_swap_rolls_back_original_tree_if_replacement_rename_fails(self):
        printer_root = Path(tempfile.mkdtemp(prefix="restore-swap-runtime-"))
        config = printer_root / "config"
        config.mkdir()
        (config / "printer.cfg").write_text("old\n", encoding="utf-8")
        (config / "extra.cfg").write_text("extra\n", encoding="utf-8")

        staged_root = Path(tempfile.mkdtemp(prefix="restore-swap-stage-")) / "config"
        staged_root.mkdir()
        (staged_root / "printer.cfg").write_text("new\n", encoding="utf-8")

        real_replace = os.replace
        calls = []

        def fail_second_replace(src, dst):
            calls.append((Path(src), Path(dst)))
            if len(calls) == 2:
                raise OSError("replacement rename failed")
            return real_replace(src, dst)

        with mock.patch.object(backup_runtime.os, "replace", side_effect=fail_second_replace):
            with self.assertRaises(OSError):
                restore_staged_snapshot_tree(
                    staged_source_root=staged_root,
                    printer_data_root=printer_root,
                    source_directory="config",
                )

        self.assertEqual((config / "printer.cfg").read_text(encoding="utf-8"), "old\n")
        self.assertEqual((config / "extra.cfg").read_text(encoding="utf-8"), "extra\n")

    def test_backup_creation_rejects_empty_source_tree(self):
        printer_root = Path(tempfile.mkdtemp(prefix="empty-backup-runtime-"))
        (printer_root / "config").mkdir()
        with self.assertRaises(BackupArchiveError):
            create_config_backup(
                printer_data_root=printer_root,
                source_directory="config",
                backup_label="empty-backup",
            )
        self.assertFalse((printer_root / "empty-backup.zip").exists())

    def test_secure_state_file_write_forces_requested_mode_on_existing_file(self):
        state_path = Path(tempfile.mkdtemp(prefix="state-mode-")) / "state.yaml"
        state_path.write_text("old\n", encoding="utf-8")
        os.chmod(state_path, 0o644)
        state = InstalledState(
            schema_version=1,
            package_id="pkg",
            package_version="1",
            runtime_firmware="firmware",
            backup_label="backup",
            installed_at="2026-05-04T00:00:00Z",
            managed_tree=ManagedTreeState(root="config/tltg-optimized-macros", files=()),
            patch_ledger=(),
        )

        write_installed_state(state_path, state)

        self.assertEqual(state_path.stat().st_mode & 0o777, 0o600)

    def test_optimized_include_is_written_only_after_stock_homing_override_delete(self):
        printer_root = copy_base_runtime()
        with moonraker_server("standby") as url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=url),
            )
            real_atomic_write_text = run_install.__globals__["atomic_write_text"]

            def assert_ordered_write(path, text, *args, **kwargs):
                if path == printer_root / "config/printer.cfg" and "[include tltg-optimized-macros/*.cfg]" in text:
                    with self.assertRaises(klipper_cfg.TargetResolutionError):
                        klipper_cfg.resolve_unique_section(
                            (printer_root / "config/klipper-macros-qd/kinematics.cfg").read_text(
                                encoding="utf-8"
                            ),
                            "homing_override",
                        )
                return real_atomic_write_text(path, text, *args, **kwargs)

            with mock.patch("installer.runtime.runner.atomic_write_text", side_effect=assert_ordered_write):
                run_install(paths, self.manifest, PlainReporter(io.StringIO()))
