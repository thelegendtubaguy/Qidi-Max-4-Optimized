from __future__ import annotations

import copy
import io
import json
import os
import shutil
import unittest
from pathlib import Path
from subprocess import CompletedProcess
from unittest import mock

from installer.runtime import system_optimizations
from installer.runtime import fluidd_box_filaments as fluidd_patch
from installer.runtime.fluidd_box_filaments import OPERATION as FLUIDD_BOX_OPERATION, PATCH_MARKER
from installer.runtime.fluidd_filament_config import OPERATION as FILAMENT_CONFIG_OPERATION
from installer.runtime.cli import resolve_runtime_paths
from installer.runtime.compatibility import load_supported_upgrade_sources
from installer.runtime.errors import InstalledPackageValidationError
from installer.runtime.manifest import load_manifest
from installer.runtime.models import SystemOptimizationCliOptions
from installer.runtime.reporter import PlainReporter
from installer.runtime.runner import run_install
from installer.runtime.state_file import StateValidationError, load_installed_state, write_installed_state
from installer.runtime.system_optimizations import (
    SYSTEM_ROOT_ENV,
    SystemOptimizationApplyError,
    SystemOptimizationRecoveryError,
    _compact_host_ledger,
    _replace_system_ledger,
    apply_system_optimizations,
    _journal_path,
    recover_pending_system_optimization,
    validate_system_ledger,
)
from installer.runtime.uninstall import run_uninstall
from installer.tests.helpers import (
    REPO_ROOT,
    build_env,
    copy_base_runtime,
    fake_host_run,
    fake_system_root,
    moonraker_urlopen,
    snapshot_tree,
)


class SystemOptimizationFlowTests(unittest.TestCase):
    def test_system_optimization_dry_run_install_and_uninstall_lifecycle(self):
        printer_root = copy_base_runtime()
        system_root = fake_system_root(include_moonraker_cache=True, include_fluidd_bundle=True, include_filament_config=True)
        host_run = fake_host_run(system_root)
        moonraker = system_root / "home/qidi/moonraker/moonraker/components/file_manager/file_manager.py"
        moonraker.write_bytes(moonraker.read_bytes().replace(b"\n", b"\r\n"))
        moonraker_before = moonraker.read_bytes()
        moonraker.chmod(0o640)
        fluidd = system_root / "home/qidi/fluidd/assets/index-DlFvHGAh.js"
        fluidd_before = fluidd.read_bytes()
        before = snapshot_tree(system_root)
        env = build_env(printer_root, moonraker_url="http://moonraker.invalid")
        env[SYSTEM_ROOT_ENV] = str(system_root)
        boot_id = printer_root / "boot-id"
        boot_id.write_text("boot-one\n", encoding="utf-8")
        env["TLTG_OPTIMIZED_BOOT_ID_PATH"] = str(boot_id)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        compatibility = load_supported_upgrade_sources(
            REPO_ROOT / "installer/supported_upgrade_sources.yaml"
        )
        stream = io.StringIO()

        result = run_install(
            paths,
            manifest,
            PlainReporter(stream),
            dry_run=True,
            urlopen=moonraker_urlopen(),
            environ=env,
            system_options=SystemOptimizationCliOptions(disable_ai_detection=True),
            run=host_run,
        )

        self.assertTrue(result.dry_run)
        self.assertEqual(snapshot_tree(system_root), before)
        self.assertFalse((printer_root / manifest.state_file).exists())
        self.assertIn("System optimizations dry-run:", stream.getvalue())

        install_responses = io.StringIO("yes\nyes\nno\nunused\n")
        base_urlopen = moonraker_urlopen(
            saved_variables_path=paths.config_root / "saved_variables.cfg"
        )
        install_idle_checks = 0

        def install_urlopen(request, timeout=0):
            nonlocal install_idle_checks
            url = getattr(request, "full_url", str(request))
            if url == paths.moonraker_url:
                install_idle_checks += 1
            return base_urlopen(request, timeout=timeout)

        run_install(
            paths,
            manifest,
            PlainReporter(io.StringIO()),
            input_stream=install_responses,
            urlopen=install_urlopen,
            environ=env,
            run=host_run,
        )
        self.assertEqual(install_idle_checks, 2)
        self.assertEqual(install_responses.readline(), "unused\n")
        self.assertTrue((system_root / "etc/resolv.conf").is_symlink())
        self.assertIn(
            "deb http://deb.debian.org/debian bullseye",
            (system_root / "etc/apt/sources.list").read_text(encoding="utf-8"),
        )
        rockchip = manifest.system_optimizations.rockchip_root_sync
        dropin = system_root / rockchip.dropin.lstrip("/")
        self.assertEqual(dropin.read_text(encoding="utf-8"), rockchip.dropin_content)
        self.assertTrue(paths.host_reboot_marker_path.exists())
        state = load_installed_state(printer_root / manifest.state_file)
        self.assertIn("rockchip_root_sync", state.system_ledger["restore_preimages"])
        self.assertEqual(state.system_ledger["schema_version"], 2)
        self.assertNotIn("actions", state.system_ledger)
        self.assertIn("rockchip_root_sync", state.system_ledger["committed_transactions"])
        cache_id = system_optimizations.MOONRAKER_CACHE_OPERATION
        self.assertIn(cache_id, state.system_ledger["restore_preimages"])
        self.assertNotEqual(moonraker.read_bytes(), moonraker_before)
        self.assertIn(b"\r\n", moonraker.read_bytes())
        self.assertEqual(moonraker.stat().st_mode & 0o777, 0o640)
        self.assertIn(FLUIDD_BOX_OPERATION, state.system_ledger["restore_preimages"])
        self.assertIn(PATCH_MARKER.encode(), fluidd.read_bytes())
        filament_config = manifest.system_optimizations.fluidd_filament_config
        filament_link = printer_root / filament_config.link
        self.assertEqual(os.readlink(filament_link), filament_config.target)
        self.assertIn(FILAMENT_CONFIG_OPERATION, state.system_ledger["restore_preimages"])
        fluidd_current = fluidd.read_bytes()
        # Package 26.10.20.1 left an earlier owned Fluidd patch that updates must replace in place.
        fluidd_previous = fluidd_before.decode().replace(fluidd_patch.SLOT_PARSE_STOCK, fluidd_patch.SLOT_PARSE_PATCHED).replace(
            fluidd_patch.FILAS_LIST_STOCK, fluidd_patch._filas_list_patched_v1()
        ).encode()
        fluidd.write_bytes(fluidd_previous)
        prior_preimage = state.system_ledger["restore_preimages"][cache_id]
        fluidd_preimage = state.system_ledger["restore_preimages"][FLUIDD_BOX_OPERATION]
        cache_policy = copy.deepcopy({**state.system_ledger, "policy": {"system_optimizations": "disabled", "ai_detection": "unset"}})
        cache_policy["outcomes"][FLUIDD_BOX_OPERATION]["postflight"]["sha256"] = __import__("hashlib").sha256(fluidd_previous).hexdigest()
        reconciled = apply_system_optimizations(
            paths=paths, spec=manifest.system_optimizations, ledger=cache_policy,
            reporter=PlainReporter(io.StringIO()), input_stream=None, environ=env,
            source="auto_update_reconcile", run=host_run,
        )
        self.assertEqual(reconciled["restore_preimages"][cache_id], prior_preimage)
        self.assertEqual(fluidd.read_bytes(), fluidd_current)
        self.assertEqual(reconciled["restore_preimages"][FLUIDD_BOX_OPERATION], fluidd_preimage)
        self.assertEqual(os.readlink(filament_link), filament_config.target)
        write_installed_state(printer_root / manifest.state_file, _replace_system_ledger(state, reconciled))

        run_uninstall(
            paths,
            manifest,
            compatibility,
            PlainReporter(io.StringIO()),
            input_stream=io.StringIO("yes\nyes\nno\n"),
            urlopen=moonraker_urlopen(),
            environ=env,
            run=host_run,
        )
        self.assertFalse((printer_root / manifest.state_file).exists())
        self.assertFalse((system_root / "etc/resolv.conf").is_symlink())
        self.assertEqual(
            (system_root / "etc/resolv.conf").read_text(encoding="utf-8"),
            "nameserver 114.114.114.114\n",
        )
        self.assertEqual(
            (system_root / "etc/apt/sources.list").read_text(encoding="utf-8"),
            "old apt\n",
        )
        self.assertFalse(dropin.exists())
        self.assertEqual(moonraker.read_bytes(), moonraker_before)
        self.assertEqual(moonraker.stat().st_mode & 0o777, 0o640)
        self.assertEqual(fluidd.read_bytes(), fluidd_before)
        self.assertFalse(filament_link.is_symlink())

    def test_unreviewed_fluidd_bundle_is_preserved_without_blocking_other_patches(self):
        printer_root = copy_base_runtime()
        root = fake_system_root(include_moonraker_cache=True, include_fluidd_bundle=True)
        env = build_env(printer_root, moonraker_url="http://moonraker.invalid")
        env[SYSTEM_ROOT_ENV] = str(root)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        fluidd = root / manifest.system_optimizations.fluidd_box_filament_ids.file.lstrip("/")
        fluidd.write_text(fluidd.read_text().replace('"officiallFilasList",e)', '"officiallFilasList",e||{})'))
        original = fluidd.read_bytes()

        ledger = apply_system_optimizations(
            paths=paths, spec=manifest.system_optimizations,
            ledger={"policy": {"system_optimizations": "disabled", "ai_detection": "unset"}},
            reporter=PlainReporter(io.StringIO()), input_stream=None,
            environ=env, source="yes_install", run=fake_host_run(root),
        )

        self.assertEqual(fluidd.read_bytes(), original)
        self.assertEqual(ledger["outcomes"][FLUIDD_BOX_OPERATION]["status"], "unsupported")
        self.assertNotIn(FLUIDD_BOX_OPERATION, ledger["restore_preimages"])
        self.assertIn(system_optimizations.MOONRAKER_CACHE_OPERATION, ledger["restore_preimages"])

    def test_moonraker_cache_admission_and_restart_failure_preserve_source(self):
        for fault in ("unknown", "unknown_metascan", "symlink", "restart", "concurrent"):
            with self.subTest(fault=fault):
                printer_root = copy_base_runtime()
                root = fake_system_root(include_moonraker_cache=True)
                env = build_env(printer_root, moonraker_url="http://moonraker.invalid")
                env[SYSTEM_ROOT_ENV] = str(root)
                paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
                manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
                target = root / manifest.system_optimizations.moonraker_file_manager.file.lstrip("/")
                if fault == "unknown":
                    target.write_text(target.read_text().replace("retries = 3", "retries = 4"))
                elif fault == "unknown_metascan":
                    target.write_text(target.read_text().replace("get_str('filename')", "get_str('filename', '')"))
                original = target.read_bytes()
                if fault == "symlink":
                    other = target.with_name("operator.py")
                    target.rename(other)
                    target.symlink_to(other)
                host_run = fake_host_run(root)
                failed = False

                def run(command, **kwargs):
                    nonlocal failed
                    if not failed and list(command)[-3:] == ["systemctl", "restart", "moonraker.service"]:
                        if fault == "restart":
                            failed = True
                            return CompletedProcess(command, 1, stdout="", stderr="restart failed")
                        if fault == "concurrent":
                            failed = True
                            target.write_bytes(target.read_bytes() + b"\n# concurrent operator edit\n")
                    return host_run(command, **kwargs)

                expected_error = SystemOptimizationRecoveryError if fault == "concurrent" else SystemOptimizationApplyError
                with self.assertRaises(expected_error):
                    apply_system_optimizations(
                        paths=paths, spec=manifest.system_optimizations,
                        ledger={"policy": {"system_optimizations": "disabled", "ai_detection": "unset"}},
                        reporter=PlainReporter(io.StringIO()), input_stream=None,
                        environ=env, source="yes_install", run=run,
                    )
                if fault == "concurrent":
                    drifted = target.read_bytes()
                    self.assertTrue(drifted.endswith(b"# concurrent operator edit\n"))
                    self.assertTrue(_journal_path(paths).exists())
                    with self.assertRaises(SystemOptimizationRecoveryError):
                        recover_pending_system_optimization(
                            paths=paths, manifest=manifest, reporter=PlainReporter(io.StringIO()),
                            input_stream=None, environ=env, run=host_run,
                        )
                    self.assertEqual(target.read_bytes(), drifted)
                else:
                    self.assertEqual(target.read_bytes(), original)
                    self.assertFalse(_journal_path(paths).exists())
                self.assertEqual(target.is_symlink(), fault == "symlink")

    def test_forged_host_preimages_fail_closed_before_uninstall(self):
        printer_root = copy_base_runtime()
        system_root = fake_system_root()
        env = build_env(printer_root, moonraker_url="http://moonraker.invalid")
        env[SYSTEM_ROOT_ENV] = str(system_root)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        forged = {
            "schema_version": 2,
            "policy": {"system_optimizations": "enabled", "ai_detection": "unset"},
            "restore_preimages": {
                "apt_sources": {
                    "file": {
                        "path": "/etc/shadow",
                        "exists": True,
                        "type": "file",
                        "backup_path": "/tmp/shadow",
                        "sha256": "0" * 64,
                        "mode": "0600",
                        "uid": 0,
                        "gid": 0,
                    }
                }
            },
            "outcomes": {"apt_sources": {"status": "applied"}},
            "committed_transactions": {},
        }
        with self.assertRaisesRegex(Exception, "Host file restoration preimage is invalid"):
            validate_system_ledger(forged, manifest=manifest, paths=paths)
        journal = {"schema_version": 1, "operation": "apt_sources", "transaction_id": "x", "phase": "apply", "preimage": forged["restore_preimages"]["apt_sources"]}
        _journal_path(paths).write_text(json.dumps(journal), encoding="utf-8")
        with self.assertRaises(SystemOptimizationRecoveryError):
            recover_pending_system_optimization(
                paths=paths, manifest=manifest, reporter=PlainReporter(io.StringIO()),
                input_stream=io.StringIO(), environ=env, run=fake_host_run(system_root),
            )
        self.assertTrue(_journal_path(paths).exists())

    def test_host_ledger_migration_and_rockchip_journal_recovery(self):
        printer_root = copy_base_runtime()
        system_root = fake_system_root()
        host_run = fake_host_run(system_root)
        env = build_env(printer_root, moonraker_url="http://moonraker.invalid")
        env[SYSTEM_ROOT_ENV] = str(system_root)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        legacy = {
            "policy": {"system_optimizations": "enabled", "ai_detection": "unset"},
            "actions": [{"id": "rockchip_root_sync", "status": "applied", "transaction_id": "committed", "desired": {}}],
            "restore_preimages": {},
        }
        compacted = _compact_host_ledger(legacy)
        self.assertEqual(compacted["schema_version"], 2)
        self.assertEqual(compacted["committed_transactions"]["rockchip_root_sync"], "committed")
        self.assertNotIn("actions", compacted)

        rockchip = manifest.system_optimizations.rockchip_root_sync
        journal = {
            "schema_version": 1,
            "operation": "rockchip_root_sync",
            "transaction_id": "committed",
            "started_at": "2026-01-01T00:00:00Z",
            "phase": "captured",
            "preimage": {
                "classification": "defective_stock",
                "dropin": {"path": rockchip.dropin, "exists": False},
                "desired_dropin": rockchip.dropin_content,
                "unit": {},
                "mount_options": ["rw", "sync"],
                "marker": {"exists": False},
            },
        }
        _journal_path(paths).write_text(json.dumps(journal), encoding="utf-8")
        self.assertTrue(
            recover_pending_system_optimization(
                paths=paths,
                manifest=manifest,
                reporter=PlainReporter(io.StringIO()),
                input_stream=io.StringIO(),
                environ=env,
                run=host_run,
            )
        )
        self.assertFalse(_journal_path(paths).exists())

    def test_uninstall_preserves_user_modified_host_state(self):
        printer_root = copy_base_runtime()
        system_root = fake_system_root(include_moonraker_cache=True, include_filament_config=True)
        host_run = fake_host_run(system_root)
        env = build_env(printer_root, moonraker_url="http://moonraker.invalid")
        env[SYSTEM_ROOT_ENV] = str(system_root)
        boot = printer_root / "boot-id"
        boot.write_text("test-boot\n")
        env["TLTG_OPTIMIZED_BOOT_ID_PATH"] = str(boot)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        compatibility = load_supported_upgrade_sources(REPO_ROOT / "installer/supported_upgrade_sources.yaml")
        run_install(
            paths, manifest, PlainReporter(io.StringIO()), input_stream=io.StringIO("yes\nyes\nno\n"),
            urlopen=moonraker_urlopen(saved_variables_path=paths.config_root / "saved_variables.cfg"), environ=env,
            run=host_run,
        )
        (system_root / "etc/apt/sources.list").write_text("operator apt\n", encoding="utf-8")
        moonraker = system_root / manifest.system_optimizations.moonraker_file_manager.file.lstrip("/")
        drifted = moonraker.read_bytes() + b"\n# operator modification outside the patched class\n"
        moonraker.write_bytes(drifted)
        filament_link = printer_root / manifest.system_optimizations.fluidd_filament_config.link
        filament_link.unlink()
        filament_link.symlink_to("/home/qidi/operator_filaments")
        state = load_installed_state(printer_root / manifest.state_file)
        cache_policy = {**state.system_ledger, "policy": {"system_optimizations": "disabled", "ai_detection": "unset"}}
        reconciled = apply_system_optimizations(
            paths=paths, spec=manifest.system_optimizations, ledger=cache_policy,
            reporter=PlainReporter(io.StringIO()), input_stream=None, environ=env,
            source="auto_update_reconcile", run=host_run,
        )
        self.assertEqual(moonraker.read_bytes(), drifted)
        self.assertEqual(os.readlink(filament_link), "/home/qidi/operator_filaments")
        write_installed_state(printer_root / manifest.state_file, _replace_system_ledger(state, reconciled))
        (system_root / "etc/apt/sources.list").write_text("operator apt\n", encoding="utf-8")
        report = io.StringIO()
        run_uninstall(
            paths, manifest, compatibility, PlainReporter(report), input_stream=io.StringIO("yes\nyes\nno\n"),
            urlopen=moonraker_urlopen(), environ=env,
            run=host_run,
        )
        self.assertEqual((system_root / "etc/apt/sources.list").read_text(encoding="utf-8"), "operator apt\n")
        self.assertEqual(moonraker.read_bytes(), drifted)
        self.assertEqual(os.readlink(filament_link), "/home/qidi/operator_filaments")

    def test_legacy_host_preimages_migrate_and_restore(self):
        printer_root = copy_base_runtime()
        system_root = fake_system_root()
        host_run = fake_host_run(system_root)
        env = build_env(printer_root, moonraker_url="http://moonraker.invalid")
        env[SYSTEM_ROOT_ENV] = str(system_root)
        boot = printer_root / "boot-id"
        boot.write_text("test-boot\n", encoding="utf-8")
        env["TLTG_OPTIMIZED_BOOT_ID_PATH"] = str(boot)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        compatibility = load_supported_upgrade_sources(REPO_ROOT / "installer/supported_upgrade_sources.yaml")
        run_install(paths, manifest, PlainReporter(io.StringIO()), input_stream=io.StringIO("yes\nyes\nno\nno\n"), urlopen=moonraker_urlopen(saved_variables_path=paths.config_root / "saved_variables.cfg"), environ=env, run=host_run)
        state_path = printer_root / manifest.state_file
        state = load_installed_state(state_path)
        legacy = copy.deepcopy(state.system_ledger)
        for preimage in legacy["restore_preimages"].values():
            self._make_legacy_preimage(preimage, system_root)
        legacy.pop("schema_version")
        legacy["actions"] = [
            {"id": operation_id, "status": "applied", "transaction_id": outcome.get("transaction_id"), "desired": outcome.get("desired", {})}
            for operation_id, outcome in legacy.pop("outcomes").items()
        ]
        legacy.pop("committed_transactions")
        write_installed_state(state_path, _replace_system_ledger(state, legacy))
        run_install(paths, manifest, PlainReporter(io.StringIO()), input_stream=io.StringIO("yes\nyes\nno\nno\n"), urlopen=moonraker_urlopen(saved_variables_path=paths.config_root / "saved_variables.cfg"), environ=env, run=host_run)
        migrated = load_installed_state(state_path).system_ledger
        self.assertEqual(migrated["restore_preimages"]["apt_sources"]["file"]["sha256"], __import__("hashlib").sha256(b"old apt\n").hexdigest())
        migrated_gifs = Path(migrated["restore_preimages"]["qidiclient_static_gifs"]["backup_dir"])
        self.assertTrue(migrated_gifs.is_relative_to(paths.printer_data_root / system_optimizations.SYSTEM_BACKUP_DIR))
        # Simulate power loss after atomic state commit but before migration-journal cleanup.
        migration_target = migrated_gifs.parent
        migration_id = migration_target.name.removeprefix(system_optimizations.LEGACY_MIGRATION_PREFIX)
        (migration_target / system_optimizations.LEGACY_MIGRATION_OWNER).write_text(
            json.dumps({"kind": "legacy-system-ledger-gifs", "migration_id": migration_id}), encoding="utf-8"
        )
        (paths.printer_data_root / system_optimizations.LEGACY_MIGRATION_JOURNAL).write_text(
            json.dumps({"schema_version": 1, "kind": "legacy-system-ledger-gifs", "migration_id": migration_id, "target": str(migration_target)}), encoding="utf-8"
        )
        system_optimizations.recover_pending_legacy_system_ledger_migration(paths, state_path)
        self.assertTrue(migrated_gifs.is_dir())
        run_uninstall(paths, manifest, compatibility, PlainReporter(io.StringIO()), input_stream=io.StringIO("yes\nyes\nno\n"), urlopen=moonraker_urlopen(), environ=env, run=host_run)
        self.assertEqual((system_root / "etc/apt/sources.list").read_text(encoding="utf-8"), "old apt\n")
        self.assertEqual((system_root / "home/qidi/QIDI_Client/access/account/process.gif").read_bytes(), b"old")

    def test_legacy_migration_has_no_writes_before_preflight_dry_run_or_failed_plan(self):
        paths, manifest, env, root = self._legacy_host_context()
        state_path = paths.printer_data_root / manifest.state_file
        before_state = state_path.read_bytes()
        backup_root = paths.printer_data_root / system_optimizations.SYSTEM_BACKUP_DIR
        before = snapshot_tree(backup_root)
        with self.assertRaisesRegex(RuntimeError, "preflight stop"):
            run_install(
                paths,
                manifest,
                PlainReporter(io.StringIO()),
                dry_run=True,
                urlopen=moonraker_urlopen(),
                disk_usage=lambda _: (_ for _ in ()).throw(RuntimeError("preflight stop")),
                environ=env,
                run=fake_host_run(root),
            )
        self.assertEqual(snapshot_tree(backup_root), before)
        with mock.patch("installer.runtime.runner.build_install_plan", side_effect=RuntimeError("invalid plan")):
            with self.assertRaisesRegex(RuntimeError, "invalid plan"):
                run_install(paths, manifest, PlainReporter(io.StringIO()), urlopen=moonraker_urlopen(), environ=env, run=fake_host_run(root))
        self.assertEqual(state_path.read_bytes(), before_state)
        self.assertEqual(snapshot_tree(backup_root), before)
        self._assert_legacy_migration_interruption_recovers_unreferenced_copy(paths, manifest, env, state_path)

    def _assert_legacy_migration_interruption_recovers_unreferenced_copy(self, paths, manifest, env, state_path):
        before_state = state_path.read_bytes()
        migrated_paths = []
        system_optimizations.migrate_legacy_system_ledger(
            load_installed_state(state_path).system_ledger,
            manifest=manifest,
            paths=paths,
            environ=env,
            created_paths=migrated_paths,
        )
        self.assertEqual(len(migrated_paths), 1)
        self.assertTrue(migrated_paths[0].exists())
        self.assertTrue((paths.printer_data_root / system_optimizations.LEGACY_MIGRATION_JOURNAL).exists())
        system_optimizations.recover_pending_legacy_system_ledger_migration(paths, state_path)
        self.assertFalse(migrated_paths[0].exists())
        self.assertFalse((paths.printer_data_root / system_optimizations.LEGACY_MIGRATION_JOURNAL).exists())
        self.assertEqual(state_path.read_bytes(), before_state)

    def test_legacy_migration_cleanup_requires_owned_dedicated_target(self):
        invalid_cases = (
            ("backup-root", lambda backup_root, unrelated: {"schema_version": 1, "kind": "legacy-system-ledger-gifs", "migration_id": "a" * 32, "target": str(backup_root)}),
            ("unrelated-subtree", lambda backup_root, unrelated: {"schema_version": 1, "kind": "legacy-system-ledger-gifs", "migration_id": "b" * 32, "target": str(unrelated)}),
            ("malformed-schema", lambda backup_root, unrelated: {"schema_version": 999, "kind": "legacy-system-ledger-gifs", "migration_id": "c" * 32, "target": str(unrelated)}),
            ("missing-identity", lambda backup_root, unrelated: {"schema_version": 1, "target": str(unrelated)}),
        )
        paths, _, _, _ = self._host_context()
        backup_root = paths.printer_data_root / system_optimizations.SYSTEM_BACKUP_DIR
        unrelated = backup_root / "retained-preimage"
        unrelated.mkdir(parents=True)
        retained = unrelated / "retained.bin"
        retained.write_bytes(b"retain")
        journal = paths.printer_data_root / system_optimizations.LEGACY_MIGRATION_JOURNAL
        for name, payload_for in invalid_cases:
            with self.subTest(name=name):
                journal.write_text(json.dumps(payload_for(backup_root, unrelated)), encoding="utf-8")
                with self.assertRaises(StateValidationError):
                    system_optimizations.recover_pending_legacy_system_ledger_migration(
                        paths, paths.printer_data_root / "absent-state.yaml"
                    )
                self.assertEqual(retained.read_bytes(), b"retain")

        link = backup_root / ".ledger-migration-link"
        link.symlink_to(unrelated, target_is_directory=True)
        journal = paths.printer_data_root / system_optimizations.LEGACY_MIGRATION_JOURNAL
        journal.write_text(json.dumps({"schema_version": 1, "kind": "legacy-system-ledger-gifs", "migration_id": "a" * 32, "target": str(link)}), encoding="utf-8")
        with self.assertRaises(StateValidationError):
            system_optimizations.recover_pending_legacy_system_ledger_migration(
                paths, paths.printer_data_root / "absent-state.yaml"
            )
        self.assertEqual(retained.read_bytes(), b"retain")

        paths, _, _, _ = self._host_context()
        backup_root = paths.printer_data_root / system_optimizations.SYSTEM_BACKUP_DIR
        collision = backup_root / f"{system_optimizations.LEGACY_MIGRATION_PREFIX}{'c' * 32}"
        collision.mkdir(parents=True)
        retained = collision / "retained.bin"
        retained.write_bytes(b"retain")
        old = paths.printer_data_root / "old-gifs"
        (old / "account").mkdir(parents=True)
        (old / "account/process.gif").write_bytes(b"old")
        preimage = {
            "backup_dir": str(old),
            "replaced": ["account/process.gif"],
            "files": {"account/process.gif": {"sha256": __import__("hashlib").sha256(b"old").hexdigest()}},
        }
        migration_id = mock.Mock(hex="c" * 32)
        with mock.patch.object(system_optimizations.uuid, "uuid4", return_value=migration_id):
            with self.assertRaises(FileExistsError):
                system_optimizations._materialize_legacy_gif_preimage(preimage, paths=paths)
        self.assertEqual(retained.read_bytes(), b"retain")

    def test_forged_ledger_uninstall_has_no_backup_or_host_side_effect(self):
        paths, manifest, env, root = self._installed_host_context()
        state_path = paths.printer_data_root / manifest.state_file
        state = load_installed_state(state_path)
        forged = {
            "schema_version": 2,
            "policy": {"system_optimizations": "enabled", "ai_detection": "unset"},
            "restore_preimages": {"apt_sources": {"file": {"path": "/etc/shadow", "exists": True, "type": "file", "backup_path": "/tmp/shadow", "sha256": "0" * 64, "mode": "0600", "uid": 0, "gid": 0}}},
            "outcomes": {"apt_sources": {"status": "applied"}},
            "committed_transactions": {},
        }
        write_installed_state(state_path, _replace_system_ledger(state, forged))
        before = snapshot_tree(root)
        compatibility = load_supported_upgrade_sources(REPO_ROOT / "installer/supported_upgrade_sources.yaml")
        with mock.patch("installer.runtime.uninstall.create_config_backup") as backup, mock.patch("installer.runtime.uninstall.prune_installer_backups") as prune:
            with self.assertRaises(InstalledPackageValidationError):
                run_uninstall(paths, manifest, compatibility, PlainReporter(io.StringIO()), input_stream=io.StringIO(), urlopen=moonraker_urlopen(), environ=env, run=fake_host_run(root))
        backup.assert_not_called(); prune.assert_not_called()
        self.assertEqual(snapshot_tree(root), before)

    def test_invalid_uninstall_plan_has_no_backup_or_pruning(self):
        paths, manifest, env, root = self._installed_host_context()
        compatibility = load_supported_upgrade_sources(REPO_ROOT / "installer/supported_upgrade_sources.yaml")
        with mock.patch("installer.runtime.uninstall.build_uninstall_plan", side_effect=RuntimeError("invalid plan")), mock.patch("installer.runtime.uninstall.create_config_backup") as backup, mock.patch("installer.runtime.uninstall.prune_installer_backups") as prune:
            with self.assertRaisesRegex(RuntimeError, "invalid plan"):
                run_uninstall(paths, manifest, compatibility, PlainReporter(io.StringIO()), input_stream=io.StringIO("yes\nyes\n"), urlopen=moonraker_urlopen(), environ=env, run=fake_host_run(root))
        backup.assert_not_called(); prune.assert_not_called()

    def test_forged_legacy_rockchip_journal_never_clears(self):
        paths, manifest, env, root = self._host_context()
        legacy = {"policy": {"system_optimizations": "enabled", "ai_detection": "unset"}, "restore_preimages": {}, "outcomes": {}, "committed_transactions": {}, "actions": [{"id": "rockchip_root_sync", "status": "applied", "transaction_id": "same"}]}
        from dataclasses import replace
        # Recovery loads only an on-disk installed state; use a valid install then replace its ledger.
        paths, manifest, env, root = self._installed_host_context()
        state_path = paths.printer_data_root / manifest.state_file
        write_installed_state(state_path, replace(load_installed_state(state_path), system_ledger=legacy))
        journal = {"schema_version": 1, "operation": "rockchip_root_sync", "transaction_id": "same", "phase": "captured", "preimage": {"classification": "defective_stock", "dropin": {"path": "/etc/shadow", "exists": False}, "desired_dropin": manifest.system_optimizations.rockchip_root_sync.dropin_content, "unit": {}, "mount_options": ["rw", "sync"], "marker": {"exists": False}}}
        _journal_path(paths).write_text(json.dumps(journal), encoding="utf-8")
        with self.assertRaises(SystemOptimizationRecoveryError):
            recover_pending_system_optimization(paths=paths, manifest=manifest, reporter=PlainReporter(io.StringIO()), input_stream=io.StringIO(), environ=env, run=fake_host_run(root))
        self.assertTrue(_journal_path(paths).exists())

    def test_rockchip_restores_full_admitted_mount_preimage(self):
        paths, manifest, env, root = self._host_context()
        (root / "mounts/root.options").write_text("ro,noatime,sync\n", encoding="utf-8")
        run_install(paths, manifest, PlainReporter(io.StringIO()), input_stream=io.StringIO("yes\nyes\nno\nno\n"), urlopen=moonraker_urlopen(saved_variables_path=paths.config_root / "saved_variables.cfg"), environ=env, run=fake_host_run(root))
        compatibility = load_supported_upgrade_sources(REPO_ROOT / "installer/supported_upgrade_sources.yaml")
        run_uninstall(paths, manifest, compatibility, PlainReporter(io.StringIO()), input_stream=io.StringIO("yes\nyes\n"), urlopen=moonraker_urlopen(), environ=env, run=fake_host_run(root))
        self.assertEqual((root / "mounts/root.options").read_text(encoding="utf-8"), "ro,noatime,sync\n")

    def test_compensation_journal_blocks_until_all_services_recover(self):
        paths, manifest, env, root = self._host_context()
        calls = {"fail_apply": True, "fail_restore": True}
        base_run = fake_host_run(root)
        def run(command, **kwargs):
            actual = command[4:] if command[:4] == ["sudo", "-S", "-p", ""] else command
            if actual == ["systemctl", "disable", "--now", "bluetooth"] and calls["fail_apply"]:
                return CompletedProcess(command, 1, stdout="failed")
            if actual in (["systemctl", "enable", "xl2tpd"], ["systemctl", "start", "xl2tpd"], ["systemctl", "enable", "--now", "xl2tpd"]) and calls["fail_restore"]:
                return CompletedProcess(command, 1, stdout="failed")
            return base_run(command, **kwargs)
        ledger = {"policy": {"system_optimizations": "enabled", "ai_detection": "keep_enabled"}, "restore_preimages": {}, "actions": []}
        selected = ("service_xl2tpd", "service_bluetooth")
        with mock.patch.object(system_optimizations, "_selected_operation_ids", return_value=selected):
            with self.assertRaises(SystemOptimizationRecoveryError):
                apply_system_optimizations(paths=paths, spec=manifest.system_optimizations, ledger=ledger, reporter=PlainReporter(io.StringIO()), input_stream=io.StringIO(), environ=env, source="test", run=run)
        payload = json.loads(_journal_path(paths).read_text(encoding="utf-8"))
        self.assertIn("service_xl2tpd", payload["preimages"])
        self.assertIn("service_bluetooth", payload["preimages"])
        calls["fail_apply"] = False
        with self.assertRaises(SystemOptimizationRecoveryError):
            recover_pending_system_optimization(paths=paths, manifest=manifest, reporter=PlainReporter(io.StringIO()), input_stream=io.StringIO(), environ=env, run=run)
        self.assertTrue(_journal_path(paths).exists())
        with self.assertRaises(SystemOptimizationRecoveryError):
            apply_system_optimizations(paths=paths, spec=manifest.system_optimizations, ledger=ledger, reporter=PlainReporter(io.StringIO()), input_stream=io.StringIO(), environ=env, source="next-lifecycle", run=run)
        calls["fail_restore"] = False
        self.assertTrue(recover_pending_system_optimization(paths=paths, manifest=manifest, reporter=PlainReporter(io.StringIO()), input_stream=io.StringIO(), environ=env, run=run))
        self.assertFalse(_journal_path(paths).exists())

    def test_rockchip_drift_journal_never_replays_after_interrupt(self):
        paths, manifest, env, root = self._installed_host_context()
        state = load_installed_state(paths.printer_data_root / manifest.state_file)
        mount_options = root / "mounts/root.options"
        mount_options.write_text("ro,noatime,async\n", encoding="utf-8")
        reporter = PlainReporter(io.StringIO())
        original_line = reporter.line
        def interrupt_after_preserve(message):
            original_line(message)
            if message == "Rockchip system state was modified after install and was preserved.":
                raise KeyboardInterrupt
        with mock.patch.object(reporter, "line", side_effect=interrupt_after_preserve):
            with self.assertRaises(KeyboardInterrupt):
                system_optimizations.restore_system_optimizations(paths=paths, manifest=manifest, state=state, reporter=reporter, input_stream=io.StringIO(), environ=env, run=fake_host_run(root))
        self.assertEqual(mount_options.read_text(encoding="utf-8"), "ro,noatime,async\n")
        recover_pending_system_optimization(paths=paths, manifest=manifest, reporter=PlainReporter(io.StringIO()), input_stream=io.StringIO(), environ=env, run=fake_host_run(root))
        self.assertEqual(mount_options.read_text(encoding="utf-8"), "ro,noatime,async\n")

    def test_unsafe_or_incomplete_mount_preimage_fails_before_host_mutation(self):
        paths, manifest, env, root = self._installed_host_context()
        state = load_installed_state(paths.printer_data_root / manifest.state_file)
        original = list(state.system_ledger["restore_preimages"]["rockchip_root_sync"]["mount_options"])
        before = snapshot_tree(root)
        for mount_preimage in (["rw", "bind"], ["sync"]):
            with self.subTest(mount_preimage=mount_preimage):
                state.system_ledger["restore_preimages"]["rockchip_root_sync"]["mount_options"] = mount_preimage
                with self.assertRaisesRegex(Exception, "Rockchip restoration preimage is invalid"):
                    system_optimizations.restore_system_optimizations(
                        paths=paths,
                        manifest=manifest,
                        state=state,
                        reporter=PlainReporter(io.StringIO()),
                        input_stream=io.StringIO(),
                        environ=env,
                        run=fake_host_run(root),
                    )
                self.assertFalse(_journal_path(paths).exists())
                self.assertEqual(snapshot_tree(root), before)
        state.system_ledger["restore_preimages"]["rockchip_root_sync"]["mount_options"] = original

    def _legacy_host_context(self):
        paths, manifest, env, root = self._installed_host_context()
        state_path = paths.printer_data_root / manifest.state_file
        state = load_installed_state(state_path)
        legacy = copy.deepcopy(state.system_ledger)
        for preimage in legacy["restore_preimages"].values():
            self._make_legacy_preimage(preimage, root)
        legacy.pop("schema_version")
        legacy["actions"] = [
            {"id": operation_id, "status": "applied", "transaction_id": outcome.get("transaction_id"), "desired": outcome.get("desired", {})}
            for operation_id, outcome in legacy.pop("outcomes").items()
        ]
        legacy.pop("committed_transactions")
        write_installed_state(state_path, _replace_system_ledger(state, legacy))
        return paths, manifest, env, root

    def _host_context(self):
        printer_root = copy_base_runtime(); root = fake_system_root()
        env = build_env(printer_root, moonraker_url="http://moonraker.invalid"); env[SYSTEM_ROOT_ENV] = str(root)
        boot = printer_root / "boot-id"
        boot.write_text("test-boot\n", encoding="utf-8")
        env["TLTG_OPTIMIZED_BOOT_ID_PATH"] = str(boot)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        return paths, load_manifest(REPO_ROOT / "installer/package.yaml"), env, root

    def _installed_host_context(self):
        paths, manifest, env, root = self._host_context()
        run_install(paths, manifest, PlainReporter(io.StringIO()), input_stream=io.StringIO("yes\nyes\nno\nno\n"), urlopen=moonraker_urlopen(saved_variables_path=paths.config_root / "saved_variables.cfg"), environ=env, run=fake_host_run(root))
        return paths, manifest, env, root

    def _make_legacy_preimage(self, preimage, root):
        if not isinstance(preimage, dict): return
        if "sha256" in preimage:
            preimage.pop("sha256")
        if "backup_path" in preimage:
            return
        if "files" in preimage:
            for item in preimage["files"]: self._make_legacy_preimage(item, root)
        if "file" in preimage: self._make_legacy_preimage(preimage["file"], root)
        if preimage.get("destination"):
            source = Path(preimage["backup_dir"])
            destination = root / preimage["destination"].lstrip("/") / ".gif-backup-old"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(source, destination)
            preimage["backup_dir"] = str(destination)
            for metadata in preimage.get("files", {}).values(): metadata.pop("sha256", None)
