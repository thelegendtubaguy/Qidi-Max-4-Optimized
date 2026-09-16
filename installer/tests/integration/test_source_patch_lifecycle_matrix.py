from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import tarfile
import unittest
from pathlib import Path
from unittest import mock

from installer.runtime import klipper_cfg
from installer.runtime.box_enablement import (
    SavedVariablePersistenceError,
    maybe_reconcile_tool_slots_after_box_count_change,
    maybe_write_required_tool_slot_variables,
    saved_variable_verify_marker_path,
)
from installer.runtime.auto_update import (
    AutoUpdateError,
    LOCK_HELD_ENV,
    _installation_requires_reconciliation,
    disable_auto_updates,
    enable_auto_updates,
    enrollment_path,
    run_auto_update_check,
    state_path,
)
from installer.runtime.backup import (
    create_config_backup,
    load_backup_snapshot,
    load_external_backup_entries,
    snapshot_runtime_tree,
)
from installer.runtime.cli import main as cli_main, resolve_runtime_paths
from installer.runtime.compatibility import load_supported_upgrade_sources
from installer.runtime.errors import ActivePrintError, ExternalFileError, PrinterStateError
from installer.runtime.manifest import load_manifest
from installer.runtime.models import (
    InstalledState,
    ManagedTreeState,
    PatchLedgerEntry,
)
from installer.runtime.reporter import PlainReporter
from installer.runtime.restore_helper import run_restore_helper
from installer.runtime.runner import run_install
from installer.runtime.state_file import load_installed_state, write_installed_state
from installer.runtime.uninstall import run_uninstall
from installer.tests.helpers import (
    MOONRAKER_QUERY_URL,
    REPO_ROOT,
    _JsonResponse,
    build_env,
    copy_base_runtime,
    homing_fixture_bytes,
    homing_sync_reset_fixture_bytes,
    moonraker_urlopen,
    temp_path,
)


DESIRED_HOMING_SHA256 = "32a8545c440a640b67d1f88f0bbc6ed86b0302c96efda3af8a39ebf22e25fda3"
SYNC_RESET_DESIRED_HOMING_SHA256 = "09a57808075b7022ad65619f5a23deeec80c5d682a43e8ee101f8d62c984f33a"
SOURCE_CASES = (
    ("01.01.06.03", "standard", DESIRED_HOMING_SHA256),
    ("01.01.06.04", "standard", DESIRED_HOMING_SHA256),
    ("01.01.06.04", "sync-reset", SYNC_RESET_DESIRED_HOMING_SHA256),
    ("01.01.06.05", "sync-reset", SYNC_RESET_DESIRED_HOMING_SHA256),
)


class SourcePatchLifecycleMatrixTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        self.compatibility = load_supported_upgrade_sources(
            REPO_ROOT / "installer/supported_upgrade_sources.yaml"
        )

    def _fixture(self, firmware: str, *, source_variant: str = "standard"):
        printer_root = copy_base_runtime()
        if firmware != "01.01.06.03":
            shutil.copytree(
                REPO_ROOT
                / "installer/stock/qidi-max4-defaults/firmwares"
                / firmware
                / "config",
                printer_root / "config",
                dirs_exist_ok=True,
            )
        (printer_root / "firmware_manifest.json").write_text(
            json.dumps({"SOC": {"version": firmware}}), encoding="utf-8"
        )
        paths = resolve_runtime_paths(
            bundle_root=REPO_ROOT,
            environ=build_env(
                printer_root,
                moonraker_url="http://moonraker.invalid/printer/objects/query?print_stats",
            ),
        )
        stock_source = (
            homing_sync_reset_fixture_bytes()
            if source_variant == "sync-reset"
            else homing_fixture_bytes(firmware)
        )
        source = paths.managed_klipper_root / "klippy/extras/homing.py"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(stock_source)
        return printer_root, paths, stock_source

    def _fixture_urlopen(self, printer_root, *, state="standby"):
        return moonraker_urlopen(
            state,
            saved_variables_path=printer_root / "config/saved_variables.cfg",
        )

    def _run_install(self, paths, *, environ=None):
        return run_install(
            paths,
            self.manifest,
            PlainReporter(io.StringIO()),
            urlopen=moonraker_urlopen(
                saved_variables_path=paths.config_root / "saved_variables.cfg"
            ),
            environ=environ,
        )

    def _assert_homing_speed(self, printer_root: Path, value: str) -> None:
        text = (printer_root / "config/printer.cfg").read_text(encoding="utf-8")
        for stepper in ("stepper_x", "stepper_y"):
            self.assertEqual(
                klipper_cfg.resolve_unique_option(text, stepper, "homing_speed").value,
                value,
            )

    def _assert_homing_retract_speed(self, printer_root: Path, value: str) -> None:
        text = (printer_root / "config/printer.cfg").read_text(encoding="utf-8")
        for stepper in ("stepper_x", "stepper_y"):
            self.assertEqual(
                klipper_cfg.resolve_unique_option(text, stepper, "homing_retract_speed").value,
                value,
            )

    def test_fresh_stock_install_applies_source_and_records_preimage_for_all_variants(self):
        for firmware, source_variant, desired_sha256 in SOURCE_CASES:
            with self.subTest(firmware=firmware, source_variant=source_variant):
                printer_root, paths, stock_source = self._fixture(
                    firmware, source_variant=source_variant
                )
                self._run_install(paths)

                self._assert_homing_speed(printer_root, "65")
                self._assert_homing_retract_speed(printer_root, "500.0")
                self.assertEqual(
                    hashlib.sha256(
                        (paths.managed_klipper_root / "klippy/extras/homing.py").read_bytes()
                    ).hexdigest(),
                    desired_sha256,
                )
                state = load_installed_state(
                    printer_root / "config/tltg_optimized_state.yaml"
                )
                self.assertEqual(len(state.source_patches), 1)
                entry = state.source_patches[0]
                self.assertEqual(entry.firmware, firmware)
                self.assertEqual(entry.original_bytes, stock_source)
                self.assertEqual(entry.original_sha256, hashlib.sha256(stock_source).hexdigest())
                self.assertEqual(len(state.external_files), 1)
                external = state.external_files[0]
                self.assertEqual(external.id, "tltg_pa_calibration_extra")
                self.assertEqual(external.installed_sha256, self.manifest.install.external_files[0].sha256)
                self.assertEqual(
                    (paths.managed_klipper_root / external.destination).read_bytes(),
                    (REPO_ROOT / "installer/klipper/extras/tltg_pa_calibration.py").read_bytes(),
                )

    def test_reinstall_backup_captures_managed_external_file(self):
        _, paths, _ = self._fixture("01.01.06.03")
        self._run_install(paths)

        reinstall = self._run_install(paths)

        assert reinstall.backup_zip_path is not None
        allowed = {
            patch.id: patch.destination
            for patch in self.manifest.install.source_patches
        }
        allowed.update(
            {
                spec.id: spec.destination
                for spec in self.manifest.install.external_files
            }
        )
        _, entries = load_external_backup_entries(
            backup_zip_path=reinstall.backup_zip_path,
            allowed_entries=allowed,
            require_manifest=True,
        )
        self.assertEqual({entry[0] for entry in entries}, set(allowed))

    def test_external_file_collision_fails_before_runtime_writes(self):
        printer_root, paths, stock_source = self._fixture("01.01.06.03")
        destination = (
            paths.managed_klipper_root / "klippy/extras/tltg_pa_calibration.py"
        )
        destination.write_text("user-owned\n", encoding="utf-8")

        with self.assertRaises(ExternalFileError):
            self._run_install(paths)

        self.assertEqual(destination.read_text(encoding="utf-8"), "user-owned\n")
        self.assertEqual(
            (paths.managed_klipper_root / "klippy/extras/homing.py").read_bytes(),
            stock_source,
        )
        self.assertFalse((paths.config_root / "tltg_optimized_state.yaml").exists())
        self.assertFalse((paths.config_root / "tltg-optimized-macros").exists())

    def test_install_initializes_absent_filament_retention_and_preserves_zero(self):
        for existing, expected in ((None, "1"), ("0", "0")):
            with self.subTest(existing=existing):
                printer_root, paths, _ = self._fixture("01.01.06.03")
                saved_variables_path = printer_root / "config/saved_variables.cfg"
                if existing is not None:
                    text = saved_variables_path.read_text(encoding="utf-8")
                    saved_variables_path.write_text(
                        text + f"tltg_keep_loaded_between_prints = {existing}\n",
                        encoding="utf-8",
                    )

                self._run_install(paths)

                saved_variables = saved_variables_path.read_text(encoding="utf-8")
                self.assertEqual(
                    klipper_cfg.resolve_unique_option(
                        saved_variables,
                        "Variables",
                        "tltg_keep_loaded_between_prints",
                    ).value,
                    expected,
                )

    def test_noninteractive_box_reconciliation_adds_missing_mappings_without_replacing_existing_ones(self):
        printer_root, paths, _ = self._fixture("01.01.06.03")
        saved_variables_path = printer_root / "config/saved_variables.cfg"
        saved_variables_path.write_text(
            "[Variables]\n"
            "box_count = 2\n"
            "enable_box = 1\n"
            "value_t0 = 'slot0'\n"
            "value_t1 = 'slot3'\n"
            "value_t2 = 'slot2'\n"
            "value_t3 = 'slot3'\n",
            encoding="utf-8",
        )

        self._run_install(paths)

        saved_variables = saved_variables_path.read_text(encoding="utf-8")
        self.assertEqual(
            klipper_cfg.resolve_unique_option(
                saved_variables, "Variables", "value_t1"
            ).value,
            "'slot3'",
        )
        for tool in range(4, 8):
            self.assertEqual(
                klipper_cfg.resolve_unique_option(
                    saved_variables, "Variables", f"value_t{tool}"
                ).value,
                f"'slot{tool}'",
            )
        self.assertNotIn(
            "value_t",
            (paths.config_root / "tltg_optimized_state.yaml").read_text(
                encoding="utf-8"
            ),
        )

        saved_variables_path.write_text(
            klipper_cfg.set_option_value(saved_variables, "Variables", "box_count", "3"),
            encoding="utf-8",
        )
        reporter = PlainReporter(io.StringIO())
        urlopen = self._fixture_urlopen(printer_root)
        self.assertTrue(maybe_reconcile_tool_slots_after_box_count_change(
            paths=paths, reporter=reporter, urlopen=urlopen
        ))
        reconciled = saved_variables_path.read_text(encoding="utf-8")
        for tool in range(12):
            self.assertEqual(
                klipper_cfg.resolve_unique_option(
                    reconciled, "Variables", f"value_t{tool}"
                ).value,
                "'slot3'" if tool == 1 else f"'slot{tool}'",
            )
        self.assertFalse(maybe_reconcile_tool_slots_after_box_count_change(
            paths=paths, reporter=reporter, urlopen=urlopen
        ))
        self.assertEqual(saved_variables_path.read_text(encoding="utf-8"), reconciled)

    def test_missing_mapping_recheck_preserves_new_nonempty_choice(self):
        printer_root, paths, _ = self._fixture("01.01.06.03")
        saved_variables_path = printer_root / "config/saved_variables.cfg"
        saved_variables_path.write_text(
            "[Variables]\nbox_count = 1\nenable_box = 1\n",
            encoding="utf-8",
        )
        base_urlopen = self._fixture_urlopen(printer_root)
        object_queries = 0
        gcode_scripts = []

        def urlopen(request, timeout=0):
            nonlocal object_queries
            url = getattr(request, "full_url", str(request))
            if "printer/objects/query?save_variables" in url:
                object_queries += 1
                if object_queries == 2:
                    saved_variables_path.write_text(
                        saved_variables_path.read_text(encoding="utf-8")
                        + "value_t0 = 'operator-choice'\n",
                        encoding="utf-8",
                    )
            if "/printer/gcode/script" in url:
                gcode_scripts.append(json.loads(request.data.decode("utf-8"))["script"])
            return base_urlopen(request, timeout=timeout)

        self.assertTrue(
            maybe_write_required_tool_slot_variables(
                paths=paths, reporter=PlainReporter(io.StringIO()), urlopen=urlopen
            )
        )
        self.assertFalse(any("VARIABLE=value_t0" in script for script in gcode_scripts))
        self.assertEqual(
            klipper_cfg.resolve_unique_option(
                saved_variables_path.read_text(encoding="utf-8"), "Variables", "value_t0"
            ).value,
            "'operator-choice'",
        )

    def test_source_restart_rejects_changed_authorized_saved_values(self):
        printer_root, paths, _ = self._fixture("01.01.06.03")
        saved_variables_path = printer_root / "config/saved_variables.cfg"
        saved_variables_path.write_text(
            "[Variables]\nbox_count = 1\nenable_box = 0\nvalue_t0 = 'custom0'\n",
            encoding="utf-8",
        )
        base_urlopen = self._fixture_urlopen(printer_root)

        def urlopen(request, timeout=0):
            url = getattr(request, "full_url", str(request))
            response = base_urlopen(request, timeout=timeout)
            if url.endswith("/machine/services/restart"):
                saved_variables_path.write_text(
                    saved_variables_path.read_text(encoding="utf-8").replace(
                        "enable_box = 1", "enable_box = 0"
                    ),
                    encoding="utf-8",
                )
            return response

        with self.assertRaises(SavedVariablePersistenceError):
            run_install(
                paths,
                self.manifest,
                PlainReporter(io.StringIO()),
                input_stream=io.StringIO("Y\nN\n"),
                urlopen=urlopen,
            )

        with self.assertRaises(SavedVariablePersistenceError):
            run_install(
                paths,
                self.manifest,
                PlainReporter(io.StringIO()),
                input_stream=io.StringIO("Y\nN\n"),
                urlopen=urlopen,
            )

        marker_path = saved_variable_verify_marker_path(paths)
        expected_marker = json.loads(marker_path.read_text(encoding="utf-8"))
        self.assertEqual(expected_marker["schema_version"], 1)
        self.assertEqual(expected_marker["values"]["enable_box"], "1")
        self.assertTrue(
            (paths.managed_klipper_root / "klippy/extras/homing.py").is_file()
        )

        with self.assertRaises(SavedVariablePersistenceError):
            self._run_install_with_urlopen(paths, self._fixture_urlopen(printer_root))
        self.assertEqual(
            json.loads(marker_path.read_text(encoding="utf-8")), expected_marker
        )

        saved_variables_path.write_text(
            saved_variables_path.read_text(encoding="utf-8").replace(
                "enable_box = 0", "enable_box = 1"
            ),
            encoding="utf-8",
        )
        marker_bytes = marker_path.read_bytes()
        run_install(
            paths,
            self.manifest,
            PlainReporter(io.StringIO()),
            dry_run=True,
            urlopen=self._fixture_urlopen(printer_root),
        )
        self.assertEqual(marker_path.read_bytes(), marker_bytes)

        saved_variables_path.write_text(
            saved_variables_path.read_text(encoding="utf-8").replace(
                "enable_box = 1", "enable_box = 0"
            ),
            encoding="utf-8",
        )
        with mock.patch(
            "installer.runtime.uninstall.atomic_delete", side_effect=OSError("marker delete failed")
        ):
            with self.assertRaises(OSError):
                run_uninstall(
                    paths,
                    self.manifest,
                    self.compatibility,
                    PlainReporter(io.StringIO()),
                    input_stream=io.StringIO("Y\n"),
                    urlopen=self._fixture_urlopen(printer_root),
                )
        self.assertEqual(marker_path.read_bytes(), marker_bytes)
        self.assertTrue((printer_root / "config/tltg_optimized_state.yaml").exists())

        run_uninstall(
            paths,
            self.manifest,
            self.compatibility,
            PlainReporter(io.StringIO()),
            input_stream=io.StringIO("Y\n"),
            urlopen=self._fixture_urlopen(printer_root),
        )
        self.assertFalse(marker_path.exists())
        self.assertFalse((printer_root / "config/tltg_optimized_state.yaml").exists())

        self._run_install_with_urlopen(paths, self._fixture_urlopen(printer_root))
        self.assertTrue((printer_root / "config/tltg_optimized_state.yaml").exists())

        saved_variables = saved_variables_path.read_text(encoding="utf-8")
        self.assertEqual(
            klipper_cfg.resolve_unique_option(saved_variables, "Variables", "value_t0").value,
            "'custom0'",
        )
        self.assertEqual(
            klipper_cfg.resolve_unique_option(
                saved_variables, "Variables", "tltg_keep_loaded_between_prints"
            ).value,
            "1",
        )
        for tool in range(1, 4):
            self.assertEqual(
                klipper_cfg.resolve_unique_option(
                    saved_variables, "Variables", f"value_t{tool}"
                ).value,
                f"'slot{tool}'",
            )

    def test_saved_variable_write_failure_stops_install_without_file_fallback(self):
        printer_root, paths, _ = self._fixture("01.01.06.03")
        saved_variables_path = printer_root / "config/saved_variables.cfg"
        before = saved_variables_path.read_bytes()
        base_urlopen = self._fixture_urlopen(printer_root)

        def failing_urlopen(request, timeout=0):
            if "/printer/gcode/script" in getattr(request, "full_url", str(request)):
                raise OSError("Moonraker unavailable")
            return base_urlopen(request, timeout=timeout)

        with self.assertRaises(SavedVariablePersistenceError):
            self._run_install_with_urlopen(paths, failing_urlopen)
        self.assertEqual(saved_variables_path.read_bytes(), before)

    def _run_install_with_urlopen(self, paths, urlopen):
        return run_install(
            paths,
            self.manifest,
            PlainReporter(io.StringIO()),
            urlopen=urlopen,
        )

    def test_prior_managed_homing_values_migrate_for_all_variants(self):
        for firmware, source_variant, _ in SOURCE_CASES:
            with self.subTest(firmware=firmware, source_variant=source_variant):
                printer_root, paths, stock_source = self._fixture(
                    firmware, source_variant=source_variant
                )
                cfg = printer_root / "config/printer.cfg"
                cfg.write_text(
                    cfg.read_text(encoding="utf-8")
                    .replace("homing_speed: 50", "homing_speed: 100")
                    .replace("homing_retract_speed: 200.0", "homing_retract_speed: 1000.0"),
                    encoding="utf-8",
                )
                write_installed_state(
                    printer_root / "config/tltg_optimized_state.yaml",
                    InstalledState(
                        schema_version=1,
                        package_id="qidi-max4-optimized",
                        package_version=self.manifest.package.version,
                        runtime_firmware=firmware,
                        backup_label="prior-install",
                        installed_at="2026-06-15T00:00:00Z",
                        managed_tree=ManagedTreeState(
                            "config/tltg-optimized-macros", ()
                        ),
                        patch_ledger=(
                            PatchLedgerEntry(
                                "stepper_x_homing_speed",
                                "config/printer.cfg",
                                "stepper_x",
                                "homing_speed",
                                "50",
                                "100",
                                "applied",
                            ),
                            PatchLedgerEntry(
                                "stepper_y_homing_speed",
                                "config/printer.cfg",
                                "stepper_y",
                                "homing_speed",
                                "50",
                                "100",
                                "applied",
                            ),
                            PatchLedgerEntry(
                                "stepper_x_homing_retract_speed",
                                "config/printer.cfg",
                                "stepper_x",
                                "homing_retract_speed",
                                "200.0",
                                "1000.0",
                                "applied",
                            ),
                            PatchLedgerEntry(
                                "stepper_y_homing_retract_speed",
                                "config/printer.cfg",
                                "stepper_y",
                                "homing_retract_speed",
                                "200.0",
                                "1000.0",
                                "applied",
                            ),
                        ),
                    ),
                )

                self._run_install(paths)

                self._assert_homing_speed(printer_root, "65")
                self._assert_homing_retract_speed(printer_root, "500.0")
                state = load_installed_state(
                    printer_root / "config/tltg_optimized_state.yaml"
                )
                speeds = {
                    entry.id: entry
                    for entry in state.patch_ledger
                    if entry.id
                    in {"stepper_x_homing_speed", "stepper_y_homing_speed"}
                }
                self.assertEqual({entry.expected for entry in speeds.values()}, {"50"})
                self.assertEqual({entry.desired for entry in speeds.values()}, {"65"})
                self.assertEqual(state.source_patches[0].original_bytes, stock_source)

    def test_auto_update_child_initializes_defaults_and_advances_checksum_for_all_variants(self):
        for firmware, source_variant, desired_sha256 in SOURCE_CASES:
            with self.subTest(firmware=firmware, source_variant=source_variant):
                printer_root, _, _ = self._fixture(
                    firmware, source_variant=source_variant
                )
                bundle_root = temp_path("auto-update-lifecycle-") / "tltg-optimized-macros"
                bundle_root.mkdir()
                (bundle_root / "install.sh").write_text("#!/bin/sh\n", encoding="utf-8")
                paths = resolve_runtime_paths(
                    bundle_root=bundle_root,
                    environ=build_env(
                        printer_root,
                        moonraker_url="http://moonraker.invalid/printer/objects/query?print_stats",
                    ),
                )
                archive = _release_archive()
                checksum = hashlib.sha256(archive).hexdigest()
                state_path(paths).write_text(
                    json.dumps({"latest_checksum": "0" * 64}), encoding="utf-8"
                )
                enrollment_path(paths).write_text("1\n", encoding="utf-8")
                process = {"id": 100}
                child_calls = []
                fallback_urlopen = self._fixture_urlopen(printer_root)

                def urlopen(request, timeout=0):
                    url = getattr(request, "full_url", str(request))
                    if url.endswith(".sha256"):
                        return _BytesResponse(f"{checksum} bundle\n".encode())
                    if url.endswith(".tar.gz"):
                        return _BytesResponse(archive)
                    if url.endswith("/printer/info"):
                        return _JsonResponse(
                            {"result": {"state": "ready", "process_id": process["id"]}}
                        )
                    if url.endswith("/machine/services/restart"):
                        process["id"] += 1
                        return _JsonResponse({"result": "ok"})
                    return fallback_urlopen(request, timeout=timeout)

                def child_run(command, **kwargs):
                    child_calls.append((command, kwargs))
                    self.assertEqual(kwargs["env"][LOCK_HELD_ENV], "1")
                    child_paths = resolve_runtime_paths(
                        bundle_root=REPO_ROOT,
                        environ=build_env(
                            printer_root,
                            moonraker_url="http://moonraker.invalid/printer/objects/query?print_stats",
                        ),
                    )
                    run_install(
                        child_paths,
                        self.manifest,
                        PlainReporter(io.StringIO()),
                        urlopen=urlopen,
                        environ=kwargs["env"],
                    )
                    return subprocess.CompletedProcess(command, 0)

                result = run_auto_update_check(
                    paths=paths,
                    reporter=PlainReporter(io.StringIO()),
                    environ={
                        "TLTG_AUTO_UPDATE_CHECKSUM_URL": "https://example.invalid/latest.sha256",
                        "TLTG_AUTO_UPDATE_ARCHIVE_URL": "https://example.invalid/latest.tar.gz",
                    },
                    urlopen=urlopen,
                    run=child_run,
                )

                self.assertEqual(result.action, "updated")
                self.assertEqual(len(child_calls), 1)
                saved_variables = (printer_root / "config/saved_variables.cfg").read_text(
                    encoding="utf-8"
                )
                self.assertEqual(
                    klipper_cfg.resolve_unique_option(
                        saved_variables,
                        "Variables",
                        "tltg_keep_loaded_between_prints",
                    ).value,
                    "1",
                )
                self.assertEqual(
                    json.loads(state_path(paths).read_text(encoding="utf-8"))["latest_checksum"],
                    checksum,
                )
                self.assertEqual(
                    hashlib.sha256(
                        (
                            printer_root
                            / "klipper/klippy/extras/homing.py"
                        ).read_bytes()
                    ).hexdigest(),
                    desired_sha256,
                )
                self.assertFalse(paths.restart_marker_path.exists())

    def test_auto_update_enrollment_survives_config_cleanup_and_is_cleared_before_sudo(self):
        printer_root, paths, _ = self._fixture("01.01.06.03")
        checksum = "a" * 64

        with mock.patch("installer.runtime.auto_update.shutil.which", return_value="/usr/bin/tool"):
            enable_auto_updates(
                paths=paths,
                reporter=PlainReporter(io.StringIO()),
                urlopen=lambda url, timeout=0: _BytesResponse(
                    f"{checksum} bundle\n".encode()
                ),
                run=lambda command, **kwargs: subprocess.CompletedProcess(command, 0),
            )

        self.assertEqual(enrollment_path(paths).read_text(encoding="utf-8"), "1\n")
        self.assertEqual(enrollment_path(paths).stat().st_mode & 0o777, 0o600)
        shutil.rmtree(printer_root / "config")
        (printer_root / "config").mkdir()
        self.assertTrue(enrollment_path(paths).exists())

        def failed_sudo(command, **kwargs):
            return subprocess.CompletedProcess(command, 1)

        with mock.patch("installer.runtime.auto_update.shutil.which", return_value="/usr/bin/tool"):
            with self.assertRaises(AutoUpdateError):
                disable_auto_updates(
                    paths=paths,
                    reporter=PlainReporter(io.StringIO()),
                    run=failed_sudo,
                )
        self.assertFalse(enrollment_path(paths).exists())

    def test_unenrolled_current_checksum_does_not_repair_saved_variables(self):
        printer_root, paths, _ = self._fixture("01.01.06.03")
        checksum = "a" * 64
        before = (printer_root / "config/saved_variables.cfg").read_bytes()
        state_path(paths).write_text(json.dumps({"latest_checksum": checksum}), encoding="utf-8")
        base_urlopen = self._fixture_urlopen(printer_root)
        gcode_scripts = []

        def urlopen(request, timeout=0):
            if getattr(request, "full_url", str(request)).endswith(".sha256"):
                return _BytesResponse(f"{checksum} bundle\n".encode())
            if "/printer/gcode/script" in getattr(request, "full_url", str(request)):
                gcode_scripts.append(request.data)
            return base_urlopen(request, timeout=timeout)

        result = run_auto_update_check(
            paths=paths,
            reporter=PlainReporter(io.StringIO()),
            environ={"TLTG_AUTO_UPDATE_CHECKSUM_URL": "https://example.invalid/latest.sha256"},
            urlopen=urlopen,
        )
        self.assertEqual(result.action, "initialized")
        self.assertEqual(gcode_scripts, [])
        self.assertEqual((printer_root / "config/saved_variables.cfg").read_bytes(), before)

        printer_root, paths, _ = self._fixture("01.01.06.03")
        self._run_install(paths)
        saved_variables_path = printer_root / "config/saved_variables.cfg"
        saved_variables_path.write_text(
            saved_variables_path.read_text(encoding="utf-8").replace(
                "tltg_keep_loaded_between_prints = 1\n", ""
            ),
            encoding="utf-8",
        )
        checksum = "a" * 64
        enrollment_path(paths).write_text("1\n", encoding="utf-8")
        state_path(paths).write_text(json.dumps({"latest_checksum": checksum}), encoding="utf-8")
        base_urlopen = self._fixture_urlopen(printer_root)

        def urlopen(request, timeout=0):
            if getattr(request, "full_url", str(request)).endswith(".sha256"):
                return _BytesResponse(f"{checksum} bundle\n".encode())
            return base_urlopen(request, timeout=timeout)

        result = run_auto_update_check(
            paths=paths,
            reporter=PlainReporter(io.StringIO()),
            environ={"TLTG_AUTO_UPDATE_CHECKSUM_URL": "https://example.invalid/latest.sha256"},
            urlopen=urlopen,
        )
        self.assertEqual(result.action, "already-current")
        self.assertEqual(
            klipper_cfg.resolve_unique_option(
                saved_variables_path.read_text(encoding="utf-8"),
                "Variables",
                "tltg_keep_loaded_between_prints",
            ).value,
            "1",
        )

    def test_unattended_saved_variable_repair_skips_active_and_unavailable_printers(self):
        printer_root, paths, _ = self._fixture("01.01.06.03")
        self._run_install(paths)
        before = (printer_root / "config/saved_variables.cfg").read_bytes()
        checksum = "a" * 64
        enrollment_path(paths).write_text("1\n", encoding="utf-8")
        state_path(paths).write_text(json.dumps({"latest_checksum": checksum}), encoding="utf-8")

        active_base_urlopen = self._fixture_urlopen(printer_root, state="printing")

        def active_urlopen(request, timeout=0):
            if getattr(request, "full_url", str(request)).endswith(".sha256"):
                return _BytesResponse(f"{checksum} bundle\n".encode())
            return active_base_urlopen(request, timeout=timeout)

        def unavailable_urlopen(request, timeout=0):
            url = getattr(request, "full_url", str(request))
            if url.endswith(".sha256"):
                return _BytesResponse(f"{checksum} bundle\n".encode())
            return _JsonResponse({"result": {}})

        for urlopen, expected_action in (
            (active_urlopen, "skipped-active-print"),
            (unavailable_urlopen, "skipped-unknown-printer-state"),
        ):
            result = run_auto_update_check(
                paths=paths,
                reporter=PlainReporter(io.StringIO()),
                environ={
                    "TLTG_AUTO_UPDATE_CHECKSUM_URL": "https://example.invalid/latest.sha256",
                    "TLTG_AUTO_UPDATE_ARCHIVE_URL": "https://example.invalid/latest.tar.gz",
                },
                urlopen=urlopen,
            )
            self.assertEqual(result.action, expected_action)
        self.assertEqual((printer_root / "config/saved_variables.cfg").read_bytes(), before)

    def test_unenrolled_changed_checksum_records_latest_without_installing(self):
        printer_root, paths, _ = self._fixture("01.01.06.03")
        old_checksum = "1" * 64
        checksum = "2" * 64
        state_path(paths).write_text(
            json.dumps({"latest_checksum": old_checksum}), encoding="utf-8"
        )
        opened_urls = []

        def urlopen(request, timeout=0):
            url = getattr(request, "full_url", str(request))
            opened_urls.append(url)
            if url.endswith(".sha256"):
                return _BytesResponse(f"{checksum} bundle\n".encode())
            if "printer/objects/query" in url:
                return _JsonResponse(
                    {"result": {"status": {"print_stats": {"state": "standby"}}}}
                )
            self.fail(f"Unexpected URL: {url}")

        result = run_auto_update_check(
            paths=paths,
            reporter=PlainReporter(io.StringIO()),
            environ={
                "TLTG_AUTO_UPDATE_CHECKSUM_URL": "https://example.invalid/latest.sha256",
                "TLTG_AUTO_UPDATE_ARCHIVE_URL": "https://example.invalid/latest.tar.gz",
            },
            urlopen=urlopen,
        )

        self.assertEqual(result.action, "initialized")
        self.assertEqual(
            json.loads(state_path(paths).read_text(encoding="utf-8"))["latest_checksum"],
            checksum,
        )
        self.assertFalse(any(url.endswith(".tar.gz") for url in opened_urls))

    def test_enrolled_installation_health_detects_firmware_owned_drift(self):
        firmware = "01.01.06.05"
        printer_root, paths, _ = self._fixture(
            firmware, source_variant="sync-reset"
        )
        self._run_install(paths)

        self.assertFalse(_installation_requires_reconciliation(paths))
        (printer_root / "config/printer.cfg").write_bytes(
            (
                REPO_ROOT
                / "installer/stock/qidi-max4-defaults/firmwares"
                / firmware
                / "config/printer.cfg"
            ).read_bytes()
        )
        self.assertTrue(_installation_requires_reconciliation(paths))

    def test_enrolled_auto_update_recovers_after_firmware_config_cleanup(self):
        firmware = "01.01.06.05"
        printer_root, installed_paths, _ = self._fixture(
            firmware, source_variant="sync-reset"
        )
        self._run_install(installed_paths)
        enrollment_path(installed_paths).write_text("1\n", encoding="utf-8")

        saved_variables = (printer_root / "config/saved_variables.cfg").read_bytes()
        box_config = (printer_root / "config/box.cfg").read_bytes()
        shutil.rmtree(printer_root / "config")
        shutil.copytree(
            REPO_ROOT
            / "installer/stock/qidi-max4-defaults/firmwares"
            / firmware
            / "config",
            printer_root / "config",
        )
        (printer_root / "config/saved_variables.cfg").write_bytes(saved_variables)
        (printer_root / "config/box.cfg").write_bytes(box_config)
        (installed_paths.managed_klipper_root / "klippy/extras/homing.py").write_bytes(
            homing_sync_reset_fixture_bytes()
        )

        bundle_root = temp_path("auto-update-recovery-") / "tltg-optimized-macros"
        bundle_root.mkdir()
        (bundle_root / "install.sh").write_text("#!/bin/sh\n", encoding="utf-8")
        paths = resolve_runtime_paths(
            bundle_root=bundle_root,
            environ=build_env(
                printer_root,
                moonraker_url="http://moonraker.invalid/printer/objects/query?print_stats",
            ),
        )
        self.assertTrue(enrollment_path(paths).exists())
        self.assertFalse(state_path(paths).exists())

        archive = _release_archive()
        checksum = hashlib.sha256(archive).hexdigest()
        process = {"id": 100}
        fallback_urlopen = self._fixture_urlopen(printer_root)

        def urlopen(request, timeout=0):
            url = getattr(request, "full_url", str(request))
            if url.endswith(".sha256"):
                return _BytesResponse(f"{checksum} bundle\n".encode())
            if url.endswith(".tar.gz"):
                return _BytesResponse(archive)
            if url.endswith("/printer/info"):
                return _JsonResponse(
                    {"result": {"state": "ready", "process_id": process["id"]}}
                )
            if url.endswith("/machine/services/restart"):
                process["id"] += 1
                return _JsonResponse({"result": "ok"})
            return fallback_urlopen(request, timeout=timeout)

        def child_run(command, **kwargs):
            child_paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(
                    printer_root,
                    moonraker_url="http://moonraker.invalid/printer/objects/query?print_stats",
                ),
            )
            run_install(
                child_paths,
                self.manifest,
                PlainReporter(io.StringIO()),
                urlopen=urlopen,
                environ=kwargs["env"],
            )
            return subprocess.CompletedProcess(command, 0)

        result = run_auto_update_check(
            paths=paths,
            reporter=PlainReporter(io.StringIO()),
            environ={
                **build_env(
                    printer_root,
                    moonraker_url="http://moonraker.invalid/printer/objects/query?print_stats",
                ),
                "TLTG_AUTO_UPDATE_CHECKSUM_URL": "https://example.invalid/latest.sha256",
                "TLTG_AUTO_UPDATE_ARCHIVE_URL": "https://example.invalid/latest.tar.gz",
            },
            urlopen=urlopen,
            run=child_run,
        )

        self.assertEqual(result.action, "reconciled")
        self.assertEqual(
            json.loads(state_path(paths).read_text(encoding="utf-8"))["latest_checksum"],
            checksum,
        )
        self.assertTrue((printer_root / "config/tltg_optimized_state.yaml").exists())
        self.assertIn(
            "[include tltg-optimized-macros/*.cfg]",
            (printer_root / "config/printer.cfg").read_text(encoding="utf-8"),
        )
        self.assertEqual(
            hashlib.sha256(
                (paths.managed_klipper_root / "klippy/extras/homing.py").read_bytes()
            ).hexdigest(),
            SYNC_RESET_DESIRED_HOMING_SHA256,
        )

    def test_uninstall_without_config_markers_still_disables_enrollment(self):
        printer_root, paths, _ = self._fixture("01.01.06.03")
        enrollment_path(paths).write_text("1\n", encoding="utf-8")
        calls = []

        def disable(*, paths, reporter, input_stream, require_sudo):
            calls.append(require_sudo)
            enrollment_path(paths).unlink()

        with mock.patch(
            "installer.runtime.uninstall.auto_updates_configured", return_value=False
        ), mock.patch(
            "installer.runtime.uninstall.disable_auto_updates", side_effect=disable
        ):
            result = run_uninstall(
                paths,
                self.manifest,
                self.compatibility,
                PlainReporter(io.StringIO()),
                urlopen=moonraker_urlopen(),
            )

        self.assertIsNone(result.backup_label)
        self.assertEqual(calls, [False])
        self.assertFalse(enrollment_path(paths).exists())

    def test_auto_update_checksum_mismatch_preserves_bundle_and_release_state(self):
        printer_root, _, _ = self._fixture("01.01.06.03")
        bundle_root = temp_path("auto-update-mismatch-") / "tltg-optimized-macros"
        bundle_root.mkdir()
        (bundle_root / "old.txt").write_text("old bundle", encoding="utf-8")
        paths = resolve_runtime_paths(
            bundle_root=bundle_root,
            environ=build_env(
                printer_root,
                moonraker_url="http://moonraker.invalid/printer/objects/query?print_stats",
            ),
        )
        old_checksum = "1" * 64
        advertised_checksum = "2" * 64
        state_path(paths).write_text(
            json.dumps({"latest_checksum": old_checksum}), encoding="utf-8"
        )
        enrollment_path(paths).write_text("1\n", encoding="utf-8")
        child_calls = []

        def urlopen(request, timeout=0):
            url = getattr(request, "full_url", str(request))
            if url.endswith(".sha256"):
                return _BytesResponse(f"{advertised_checksum} bundle\n".encode())
            if url.endswith(".tar.gz"):
                return _BytesResponse(b"not the advertised archive")
            if "printer/objects/query" in url:
                return _JsonResponse(
                    {"result": {"status": {"print_stats": {"state": "standby"}}}}
                )
            self.fail(f"Unexpected URL: {url}")

        with self.assertRaises(AutoUpdateError):
            run_auto_update_check(
                paths=paths,
                reporter=PlainReporter(io.StringIO()),
                environ={
                    "TLTG_AUTO_UPDATE_CHECKSUM_URL": "https://example.invalid/latest.sha256",
                    "TLTG_AUTO_UPDATE_ARCHIVE_URL": "https://example.invalid/latest.tar.gz",
                },
                urlopen=urlopen,
                run=lambda command, **kwargs: (
                    child_calls.append(command)
                    or subprocess.CompletedProcess(command, 0)
                ),
            )

        self.assertEqual(child_calls, [])
        self.assertEqual(
            json.loads(state_path(paths).read_text(encoding="utf-8"))[
                "latest_checksum"
            ],
            old_checksum,
        )
        self.assertEqual(
            (bundle_root / "old.txt").read_text(encoding="utf-8"), "old bundle"
        )

    def test_source_write_failure_rolls_back_source_and_marker_for_all_variants(self):
        for firmware, source_variant, _ in SOURCE_CASES:
            with self.subTest(firmware=firmware, source_variant=source_variant):
                printer_root, paths, stock_source = self._fixture(
                    firmware, source_variant=source_variant
                )
                with mock.patch(
                    "installer.runtime.runner.mirror_tree",
                    side_effect=RuntimeError("force failure after source deployment"),
                ):
                    with self.assertRaisesRegex(RuntimeError, "force failure"):
                        self._run_install(paths)

                self.assertEqual(
                    (paths.managed_klipper_root / "klippy/extras/homing.py").read_bytes(),
                    stock_source,
                )
                self.assertFalse(
                    (
                        paths.managed_klipper_root
                        / "klippy/extras/tltg_pa_calibration.py"
                    ).exists()
                )
                self.assertFalse(paths.restart_marker_path.exists())
                self.assertFalse(
                    (printer_root / "config/tltg_optimized_state.yaml").exists()
                )

    def test_restore_rejects_non_idle_printer_after_confirmation_without_replacement(self):
        printer_root, paths, _ = self._fixture("01.01.06.03")
        install = self._run_install(paths)
        assert install.backup_zip_path is not None
        printer_config = printer_root / "config/printer.cfg"
        printer_config.write_text("[printer]\nmodified: yes\n", encoding="utf-8")
        before = printer_config.read_bytes()

        for state in ("printing", "paused", None):
            with self.subTest(state=state):
                with self.assertRaises((ActivePrintError, PrinterStateError)):
                    run_restore_helper(
                        paths,
                        self.manifest,
                        stream=io.StringIO(),
                        input_stream=io.StringIO("RESTORE\n"),
                        backup_path=str(install.backup_zip_path),
                        urlopen=moonraker_urlopen(state),
                    )
                self.assertEqual(printer_config.read_bytes(), before)

    def test_interrupt_after_configuration_write_rolls_back_and_preserves_live_saved_variables(self):
        printer_root, paths, _ = self._fixture("01.01.06.03")
        saved_variables_path = printer_root / "config/saved_variables.cfg"
        saved_before = saved_variables_path.read_bytes()
        printer_before = (printer_root / "config/printer.cfg").read_bytes()

        with mock.patch(
            "installer.runtime.runner.mirror_tree", side_effect=KeyboardInterrupt
        ):
            with self.assertRaises(KeyboardInterrupt):
                self._run_install(paths)

        self.assertEqual((printer_root / "config/printer.cfg").read_bytes(), printer_before)
        self.assertNotEqual(saved_variables_path.read_bytes(), saved_before)
        self.assertIn(
            b"tltg_keep_loaded_between_prints = 1", saved_variables_path.read_bytes()
        )
        self.assertFalse(paths.restart_marker_path.exists())
        self.assertFalse((printer_root / "config/tltg_optimized_state.yaml").exists())

    def test_interrupt_after_configuration_commit_preserves_committed_state(self):
        printer_root, paths, _ = self._fixture("01.01.06.03")
        with mock.patch(
            "installer.runtime.runner.maybe_apply_system_optimizations",
            side_effect=KeyboardInterrupt,
        ):
            with self.assertRaises(KeyboardInterrupt):
                self._run_install(paths)

        self.assertTrue((printer_root / "config/tltg_optimized_state.yaml").exists())
        self._assert_homing_speed(printer_root, "65")
        self.assertTrue(paths.restart_marker_path.exists())

    def test_source_inclusive_restore_restores_stock_source_for_all_variants(self):
        for firmware, source_variant, _ in SOURCE_CASES:
            with self.subTest(firmware=firmware, source_variant=source_variant):
                printer_root, paths, stock_source = self._fixture(
                    firmware, source_variant=source_variant
                )
                install = self._run_install(paths)
                assert install.backup_zip_path is not None
                expected_config = load_backup_snapshot(
                    backup_zip_path=install.backup_zip_path, source_directory="config"
                )
                (printer_root / "config/printer.cfg").write_text(
                    "[printer]\nmodified: yes\n", encoding="utf-8"
                )

                result = run_restore_helper(
                    paths,
                    self.manifest,
                    stream=io.StringIO(),
                    input_stream=io.StringIO("RESTORE\nY\n"),
                    backup_path=str(install.backup_zip_path),
                    urlopen=moonraker_urlopen(),
                )

                self.assertEqual(result, 0)
                self.assertEqual(
                    snapshot_runtime_tree(
                        printer_data_root=printer_root, source_directory="config"
                    ),
                    expected_config,
                )
                self.assertEqual(
                    (paths.managed_klipper_root / "klippy/extras/homing.py").read_bytes(),
                    stock_source,
                )
                self.assertFalse(
                    (
                        paths.managed_klipper_root
                        / "klippy/extras/tltg_pa_calibration.py"
                    ).exists()
                )
                self.assertFalse(paths.restart_marker_path.exists())

    def test_clear_recovery_sentinel_accepts_managed_external_archive(self):
        printer_root, paths, _ = self._fixture("01.01.06.03")
        self._run_install(paths)
        patch = self.manifest.install.source_patches[0]
        external = self.manifest.install.external_files[0]
        backup_label = (
            "tltg-optimized-macros-before-optimize-"
            "01.01.06.03-26.08.06.3-20260806T000000Z"
        )
        archive = create_config_backup(
            printer_data_root=printer_root,
            source_directory="config",
            backup_label=backup_label,
            external_files=(
                (
                    patch.id,
                    patch.destination,
                    paths.managed_klipper_root / patch.destination,
                ),
                (
                    external.id,
                    external.destination,
                    paths.managed_klipper_root / external.destination,
                ),
            ),
            external_firmware="01.01.06.03",
        )
        paths.recovery_sentinel_path.write_text(
            "\n".join(
                (
                    "error: injected rollback failure",
                    f"backup_label: {backup_label}",
                    f"backup_zip_path: {archive}",
                    "",
                )
            ),
            encoding="utf-8",
        )

        result = cli_main(
            ["clear-recovery-sentinel", "--plain"],
            stream=io.StringIO(),
            bundle_root=REPO_ROOT,
            environ=build_env(printer_root, moonraker_url=MOONRAKER_QUERY_URL),
        )

        self.assertEqual(result, 0)
        self.assertFalse(paths.recovery_sentinel_path.exists())

    def test_restore_recreates_external_file_declared_by_archived_state(self):
        printer_root, paths, _ = self._fixture("01.01.06.03")
        self._run_install(paths)
        patch = self.manifest.install.source_patches[0]
        external = self.manifest.install.external_files[0]
        archive = create_config_backup(
            printer_data_root=printer_root,
            source_directory="config",
            backup_label=(
                "tltg-optimized-macros-before-optimize-"
                "01.01.06.03-26.08.06.3-20260806T000000Z"
            ),
            external_files=(
                (
                    patch.id,
                    patch.destination,
                    paths.managed_klipper_root / patch.destination,
                ),
                (
                    external.id,
                    external.destination,
                    paths.managed_klipper_root / external.destination,
                ),
            ),
            external_firmware="01.01.06.03",
        )
        destination = (
            paths.managed_klipper_root / "klippy/extras/tltg_pa_calibration.py"
        )
        destination.unlink()

        result = run_restore_helper(
            paths,
            self.manifest,
            stream=io.StringIO(),
            input_stream=io.StringIO("RESTORE\nY\n"),
            backup_path=str(archive),
            urlopen=moonraker_urlopen(),
        )

        self.assertEqual(result, 0)
        self.assertEqual(
            destination.read_bytes(),
            (REPO_ROOT / "installer/klipper/extras/tltg_pa_calibration.py").read_bytes(),
        )
        self.assertFalse(paths.restart_marker_path.exists())

    def test_uninstall_external_file_drift_fails_before_runtime_writes(self):
        printer_root, paths, _ = self._fixture("01.01.06.03")
        self._run_install(paths)
        destination = (
            paths.managed_klipper_root / "klippy/extras/tltg_pa_calibration.py"
        )
        destination.write_text("changed after install\n", encoding="utf-8")

        with self.assertRaises(ExternalFileError):
            run_uninstall(
                paths,
                self.manifest,
                self.compatibility,
                PlainReporter(io.StringIO()),
                input_stream=io.StringIO("Y\n"),
                urlopen=moonraker_urlopen(),
            )

        self.assertEqual(
            destination.read_text(encoding="utf-8"), "changed after install\n"
        )
        self.assertTrue((paths.config_root / "tltg_optimized_state.yaml").exists())
        self.assertTrue((paths.config_root / "tltg-optimized-macros").exists())

    def test_uninstall_restores_stock_config_and_source_for_all_variants(self):
        for firmware, source_variant, _ in SOURCE_CASES:
            with self.subTest(firmware=firmware, source_variant=source_variant):
                printer_root, paths, stock_source = self._fixture(
                    firmware, source_variant=source_variant
                )
                self._run_install(paths)

                responses = io.StringIO("Y\nunused\n")
                base_urlopen = moonraker_urlopen()
                idle_checks = 0

                def uninstall_urlopen(request, timeout=0):
                    nonlocal idle_checks
                    url = getattr(request, "full_url", str(request))
                    if "/printer/objects/query" in url:
                        idle_checks += 1
                    return base_urlopen(request, timeout=timeout)

                uninstall = run_uninstall(
                    paths,
                    self.manifest,
                    self.compatibility,
                    PlainReporter(io.StringIO()),
                    input_stream=responses,
                    urlopen=uninstall_urlopen,
                )

                assert uninstall.backup_zip_path is not None
                allowed = {
                    patch.id: patch.destination
                    for patch in self.manifest.install.source_patches
                }
                allowed.update(
                    {
                        spec.id: spec.destination
                        for spec in self.manifest.install.external_files
                    }
                )
                _, archived = load_external_backup_entries(
                    backup_zip_path=uninstall.backup_zip_path,
                    allowed_entries=allowed,
                    require_manifest=True,
                )
                self.assertEqual({entry[0] for entry in archived}, set(allowed))
                self.assertEqual(idle_checks, 2)
                self.assertEqual(responses.readline(), "unused\n")
                self._assert_homing_speed(printer_root, "50")
                self.assertEqual(
                    (paths.managed_klipper_root / "klippy/extras/homing.py").read_bytes(),
                    stock_source,
                )
                self.assertFalse(
                    (
                        paths.managed_klipper_root
                        / "klippy/extras/tltg_pa_calibration.py"
                    ).exists()
                )
                self.assertFalse(
                    (printer_root / "config/tltg_optimized_state.yaml").exists()
                )
                saved_variables = (
                    printer_root / "config/saved_variables.cfg"
                ).read_text(encoding="utf-8")
                self.assertEqual(
                    klipper_cfg.resolve_unique_option(
                        saved_variables,
                        "Variables",
                        "tltg_keep_loaded_between_prints",
                    ).value,
                    "1",
                )


class _BytesResponse:
    def __init__(self, body: bytes):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return False

    def read(self):
        return self.body


def _release_archive() -> bytes:
    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz") as archive:
        payload = b"#!/bin/sh\nexit 0\n"
        member = tarfile.TarInfo("tltg-optimized-macros/install.sh")
        member.mode = 0o755
        member.size = len(payload)
        archive.addfile(member, io.BytesIO(payload))
    return buffer.getvalue()
