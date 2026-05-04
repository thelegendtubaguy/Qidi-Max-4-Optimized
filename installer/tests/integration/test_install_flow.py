from __future__ import annotations

import io
import unittest

from installer.runtime import klipper_cfg
from installer.runtime.cli import resolve_runtime_paths
from installer.runtime.errors import PreflightTargetsError
from installer.runtime.manifest import load_manifest
from installer.runtime.reporter import PlainReporter
from installer.runtime.runner import run_install
from installer.tests.helpers import REPO_ROOT, build_env, copy_base_runtime, MOONRAKER_QUERY_URL, moonraker_urlopen


class InstallFlowTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest(REPO_ROOT / "installer/package.yaml")

    def _homing_override(self, printer_root):
        return klipper_cfg.resolve_unique_section(
            (printer_root / "config/klipper-macros-qd/kinematics.cfg").read_text(
                encoding="utf-8"
            ),
            "homing_override",
        ).text

    def _homing_override_exists(self, printer_root):
        try:
            self._homing_override(printer_root)
        except klipper_cfg.TargetResolutionError as exc:
            if exc.reason == "missing":
                return False
            raise
        return True

    def test_happy_path_install(self):
        printer_root = copy_base_runtime()
        stream = io.StringIO()
        paths = resolve_runtime_paths(
            bundle_root=REPO_ROOT,
            environ=build_env(printer_root, moonraker_url=MOONRAKER_QUERY_URL),
        )
        result = run_install(paths, self.manifest, reporter=PlainReporter(stream), urlopen=moonraker_urlopen())

        self.assertTrue((paths.config_root / "tltg_optimized_state.yaml").exists())
        printer_cfg = (paths.config_root / "printer.cfg").read_text(encoding="utf-8")
        self.assertIn("[include tltg-optimized-macros/*.cfg]", printer_cfg)
        self.assertIn("homing_speed: 65", printer_cfg)
        self.assertEqual(
            klipper_cfg.resolve_unique_option(printer_cfg, "z_tilt", "speed").value,
            "600",
        )
        self.assertEqual(
            klipper_cfg.resolve_unique_option(printer_cfg, "bed_mesh", "speed").value,
            "600",
        )
        self.assertIn("on_error_gcode: OPTIMIZED_CANCEL_PRINT_ON_ERROR", printer_cfg)
        self.assertFalse(self._homing_override_exists(printer_root))
        optimized_kinematics = paths.config_root / "tltg-optimized-macros/kinematics.cfg"
        self.assertIn("[homing_override]", optimized_kinematics.read_text(encoding="utf-8"))
        self.assertTrue((paths.config_root / "tltg-optimized-macros").exists())
        output = stream.getvalue()
        self.assertIn("stage 1/5", output)
        self.assertIn("Installed.", output)
        self.assertIn("Restart Klipper to apply changes.", output)
        self.assertTrue(result.backup_zip_path.exists())

    def test_install_patches_virtual_sdcard_on_error_with_inline_comment(self):
        printer_root = copy_base_runtime()
        printer_cfg_path = printer_root / "config/printer.cfg"
        printer_cfg_path.write_text(
            printer_cfg_path.read_text(encoding="utf-8").replace(
                "on_error_gcode: CANCEL_PRINT\n",
                "on_error_gcode: CANCEL_PRINT # 出错时取消打印\n",
                1,
            ),
            encoding="utf-8",
        )
        paths = resolve_runtime_paths(
            bundle_root=REPO_ROOT,
            environ=build_env(printer_root, moonraker_url=MOONRAKER_QUERY_URL),
        )
        run_install(paths, self.manifest, reporter=PlainReporter(io.StringIO()), urlopen=moonraker_urlopen())

        printer_cfg = printer_cfg_path.read_text(encoding="utf-8")
        resolved = klipper_cfg.resolve_unique_option(
            printer_cfg, "virtual_sdcard", "on_error_gcode"
        )
        self.assertEqual(resolved.value, "OPTIMIZED_CANCEL_PRINT_ON_ERROR")
        self.assertIn(
            "on_error_gcode: OPTIMIZED_CANCEL_PRINT_ON_ERROR # 出错时取消打印",
            printer_cfg,
        )

    def test_box_extras_is_not_required_for_install(self):
        printer_root = copy_base_runtime()
        (printer_root / "config/box.cfg").unlink()
        stream = io.StringIO()
        paths = resolve_runtime_paths(
            bundle_root=REPO_ROOT,
            environ=build_env(printer_root, moonraker_url=MOONRAKER_QUERY_URL),
        )
        result = run_install(paths, self.manifest, reporter=PlainReporter(stream), urlopen=moonraker_urlopen())

        self.assertTrue((paths.config_root / "tltg_optimized_state.yaml").exists())
        self.assertTrue(result.backup_zip_path.exists())
        self.assertIn("Installed.", stream.getvalue())

    def test_install_prompts_to_enable_detected_qidi_box(self):
        printer_root = copy_base_runtime()
        saved_variables_path = printer_root / "config/saved_variables.cfg"
        saved_variables_path.write_text(
            "[Variables]\nbox_count = 1\nenable_box = 0\n",
            encoding="utf-8",
        )
        stream = io.StringIO()
        paths = resolve_runtime_paths(
            bundle_root=REPO_ROOT,
            environ=build_env(printer_root, moonraker_url=MOONRAKER_QUERY_URL),
        )
        run_install(
            paths,
            self.manifest,
            reporter=PlainReporter(stream),
            input_stream=io.StringIO("y\ny\nn\nn\n"),
            urlopen=moonraker_urlopen(),
        )

        saved_variables = saved_variables_path.read_text(encoding="utf-8")
        enabled = klipper_cfg.resolve_unique_option(saved_variables, "Variables", "enable_box")
        self.assertEqual(enabled.value, "1")
        state_text = (paths.config_root / "tltg_optimized_state.yaml").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("enable_box", state_text)
        output = stream.getvalue()
        self.assertIn("Would you like to enable QIDI Box support now?", output)
        self.assertIn("QIDI Box support enabled in saved_variables.cfg.", output)

    def test_install_preserves_disabled_detected_qidi_box_when_declined(self):
        printer_root = copy_base_runtime()
        saved_variables_path = printer_root / "config/saved_variables.cfg"
        saved_variables_path.write_text(
            "[Variables]\nbox_count = 1\nenable_box = 0\n",
            encoding="utf-8",
        )
        stream = io.StringIO()
        paths = resolve_runtime_paths(
            bundle_root=REPO_ROOT,
            environ=build_env(printer_root, moonraker_url=MOONRAKER_QUERY_URL),
        )
        run_install(
            paths,
            self.manifest,
            reporter=PlainReporter(stream),
            input_stream=io.StringIO("y\nn\nn\n"),
            urlopen=moonraker_urlopen(),
        )

        saved_variables = saved_variables_path.read_text(encoding="utf-8")
        enabled = klipper_cfg.resolve_unique_option(saved_variables, "Variables", "enable_box")
        self.assertEqual(enabled.value, "0")
        output = stream.getvalue()
        self.assertIn("Would you like to enable QIDI Box support now?", output)
        self.assertIn("QIDI Box support left disabled.", output)

    def test_install_prompts_to_correct_value_t_slot_mismatches(self):
        printer_root = copy_base_runtime()
        saved_variables_path = printer_root / "config/saved_variables.cfg"
        saved_variables_path.write_text(
            "[Variables]\n"
            "box_count = 1\n"
            "enable_box = 1\n"
            "value_t0 = 'slot0'\n"
            "value_t1 = 'slot3'\n"
            "value_t2 = 'slot2'\n"
            "value_t3 = 'slot0'\n",
            encoding="utf-8",
        )
        stream = io.StringIO()
        paths = resolve_runtime_paths(
            bundle_root=REPO_ROOT,
            environ=build_env(printer_root, moonraker_url=MOONRAKER_QUERY_URL),
        )
        run_install(
            paths,
            self.manifest,
            reporter=PlainReporter(stream),
            input_stream=io.StringIO("y\ny\nn\nn\n"),
            urlopen=moonraker_urlopen(),
        )

        saved_variables = saved_variables_path.read_text(encoding="utf-8")
        self.assertEqual(
            klipper_cfg.resolve_unique_option(saved_variables, "Variables", "value_t0").value,
            "'slot0'",
        )
        self.assertEqual(
            klipper_cfg.resolve_unique_option(saved_variables, "Variables", "value_t1").value,
            "'slot1'",
        )
        self.assertEqual(
            klipper_cfg.resolve_unique_option(saved_variables, "Variables", "value_t2").value,
            "'slot2'",
        )
        self.assertEqual(
            klipper_cfg.resolve_unique_option(saved_variables, "Variables", "value_t3").value,
            "'slot3'",
        )
        state_text = (paths.config_root / "tltg_optimized_state.yaml").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("value_t", state_text)
        output = stream.getvalue()
        self.assertIn("Tool numbers do not line up with slot numbers", output)
        self.assertIn("value_t1: slot3 -> slot1", output)
        self.assertIn("value_t3: slot0 -> slot3", output)
        self.assertIn("Tool-slot mappings corrected in saved_variables.cfg.", output)

    def test_install_preserves_value_t_slot_mismatches_when_declined(self):
        printer_root = copy_base_runtime()
        saved_variables_path = printer_root / "config/saved_variables.cfg"
        saved_variables_path.write_text(
            "[Variables]\n"
            "box_count = 1\n"
            "enable_box = 1\n"
            "value_t0 = 'slot0'\n"
            "value_t1 = 'slot3'\n",
            encoding="utf-8",
        )
        stream = io.StringIO()
        paths = resolve_runtime_paths(
            bundle_root=REPO_ROOT,
            environ=build_env(printer_root, moonraker_url=MOONRAKER_QUERY_URL),
        )
        run_install(
            paths,
            self.manifest,
            reporter=PlainReporter(stream),
            input_stream=io.StringIO("y\nn\nn\n"),
            urlopen=moonraker_urlopen(),
        )

        saved_variables = saved_variables_path.read_text(encoding="utf-8")
        self.assertEqual(
            klipper_cfg.resolve_unique_option(saved_variables, "Variables", "value_t1").value,
            "'slot3'",
        )
        output = stream.getvalue()
        self.assertIn("Tool numbers do not line up with slot numbers", output)
        self.assertIn("Tool-slot mappings left unchanged.", output)

    def test_reinstall_preserves_section_restore_ledger(self):
        printer_root = copy_base_runtime()
        original_section = self._homing_override(printer_root)
        paths = resolve_runtime_paths(
            bundle_root=REPO_ROOT,
            environ=build_env(printer_root, moonraker_url=MOONRAKER_QUERY_URL),
        )
        run_install(paths, self.manifest, PlainReporter(io.StringIO()), urlopen=moonraker_urlopen())
        paths = resolve_runtime_paths(
            bundle_root=REPO_ROOT,
            environ=build_env(printer_root, moonraker_url=MOONRAKER_QUERY_URL),
        )
        run_install(paths, self.manifest, PlainReporter(io.StringIO()), urlopen=moonraker_urlopen())

        state_text = (paths.config_root / "tltg_optimized_state.yaml").read_text(encoding="utf-8")
        self.assertIn(original_section.splitlines()[0], state_text)
        self.assertFalse(self._homing_override_exists(printer_root))

    def test_homing_override_whitespace_and_comment_changes_are_allowed(self):
        printer_root = copy_base_runtime()
        kinematics = printer_root / "config/klipper-macros-qd/kinematics.cfg"
        kinematics.write_text(
            kinematics.read_text(encoding="utf-8")
            .replace("#axes:xy", "# local comment-only change", 1)
            .replace("G4 P400", "      G4      P400", 1),
            encoding="utf-8",
        )
        paths = resolve_runtime_paths(
            bundle_root=REPO_ROOT,
            environ=build_env(printer_root, moonraker_url=MOONRAKER_QUERY_URL),
        )
        run_install(paths, self.manifest, PlainReporter(io.StringIO()), urlopen=moonraker_urlopen())
        self.assertFalse(self._homing_override_exists(printer_root))

    def test_modified_homing_override_fails_closed(self):
        printer_root = copy_base_runtime()
        kinematics = printer_root / "config/klipper-macros-qd/kinematics.cfg"
        kinematics.write_text(
            kinematics.read_text(encoding="utf-8").replace(
                "SET_VELOCITY_LIMIT ACCEL=500",
                "SET_VELOCITY_LIMIT ACCEL=501",
                1,
            ),
            encoding="utf-8",
        )
        paths = resolve_runtime_paths(
            bundle_root=REPO_ROOT,
            environ=build_env(printer_root, moonraker_url=MOONRAKER_QUERY_URL),
        )
        with self.assertRaises(PreflightTargetsError) as exc:
            run_install(paths, self.manifest, PlainReporter(io.StringIO()), urlopen=moonraker_urlopen())
        self.assertEqual(exc.exception.report.patch_target_issues[0].reason, "user_modified")
        self.assertFalse((paths.config_root / "tltg_optimized_state.yaml").exists())

    def test_missing_patch_target_fails_closed(self):
        printer_root = copy_base_runtime()
        printer_cfg = printer_root / "config/printer.cfg"
        printer_cfg.write_text(
            printer_cfg.read_text(encoding="utf-8").replace("homing_speed: 50\n", "", 1),
            encoding="utf-8",
        )
        paths = resolve_runtime_paths(
            bundle_root=REPO_ROOT,
            environ=build_env(printer_root, moonraker_url=MOONRAKER_QUERY_URL),
        )
        with self.assertRaises(PreflightTargetsError) as exc:
            run_install(paths, self.manifest, PlainReporter(io.StringIO()), urlopen=moonraker_urlopen())
        self.assertEqual(exc.exception.report.patch_target_issues[0].reason, "missing")
