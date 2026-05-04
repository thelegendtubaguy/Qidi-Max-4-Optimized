from __future__ import annotations

import unittest

from installer.tests.helpers import REPO_ROOT
from installer.tests.integration.test_macro_call_graph import extract_gcode_lines, iter_sections, parse_macro_definitions


OPTIMIZED_MACRO_ROOT = REPO_ROOT / "installer" / "klipper" / "tltg-optimized-macros"


class OptimizedMacroContractTests(unittest.TestCase):
    def setUp(self):
        files = tuple(sorted(OPTIMIZED_MACRO_ROOT.glob("*.cfg")))
        self.macros, duplicates = parse_macro_definitions(files)
        if duplicates:
            self.fail("Optimized macro duplicate definitions are invalid for this test.")

    def test_user_helper_macros_are_available(self):
        helpers = (OPTIMIZED_MACRO_ROOT / "helpers.cfg").read_text(encoding="utf-8")
        self.assertIn("[screws_tilt_adjust]", helpers)
        self.assertIn("screw_thread: CW-M4", helpers)

        probe_gcode = self._macro_gcode("TLTG_PROBE_ACCURACY_CENTER")
        self.assertIn("G1 X195 Y195 F24000", probe_gcode)
        self.assertIn("PROBE_ACCURACY SAMPLES={samples}", probe_gcode)
        self.assertNotIn("params.X", probe_gcode)
        self.assertNotIn("params.Y", probe_gcode)
        self.assertNotIn("params.Z", probe_gcode)
        self.assertNotIn("params.BED", probe_gcode)

        screws_gcode = self._macro_gcode("TLTG_CORNER_BED_SCREW_CHECK")
        self.assertIn("Z_TILT_ADJUST", screws_gcode)
        self.assertIn("SCREWS_TILT_CALCULATE", screws_gcode)
        self.assertNotIn("params.", screws_gcode)

    def test_start_filament_prep_enables_bed_mesh_before_branching(self):
        gcode = self._macro_gcode("OPTIMIZED_START_PRINT_FILAMENT_PREP")
        self.assertLess(gcode.index("G31"), gcode.index("SAVE_VARIABLE VARIABLE=retained_tool_ready"))
        self.assertEqual(gcode.count("BED_MESH_CALIBRATE PROFILE=kamp"), 3)
        self.assertNotIn("OPTIMIZED_G29_ZSAFE", gcode)

    def test_start_filament_prep_uses_purge_temp_for_box_load_and_rear_purge(self):
        gcode = self._macro_gcode("OPTIMIZED_START_PRINT_FILAMENT_PREP")
        self.assertIn("requires FIRSTLAYERTEMP and PURGETEMP", gcode)
        self.assertIn("first_layer_temp = params.FIRSTLAYERTEMP|int", gcode)
        self.assertIn("purge_temp = params.PURGETEMP|int", gcode)
        self.assertIn("BOX_PRINT_START EXTRUDER={tool} HOTENDTEMP={purge_temp}", gcode)
        self.assertIn("OPTIMIZED_EXTRUSION_AND_FLUSH PURGETEMP={purge_temp}", gcode)
        self.assertNotIn("params.HOTENDTEMP", gcode)
        self.assertNotIn("params.LOADTEMP", gcode)
        self.assertNotIn("load_temp", gcode)
        self.assertNotIn("hotend_temp", gcode)

    def test_cancel_on_error_reenables_bed_mesh_without_moving(self):
        gcode = self._macro_gcode("OPTIMIZED_CANCEL_PRINT_ON_ERROR")
        self.assertIn("G31", gcode)
        self.assertLess(gcode.index("G31"), gcode.index("CLEAR_PAUSE"))

    def test_optimized_g29_always_calibrates_kamp_mesh(self):
        gcode = self._macro_gcode("OPTIMIZED_G29_ZSAFE")
        self.assertIn("BED_MESH_CLEAR", gcode)
        self.assertIn("_OPTIMIZED_G29_HOME_Z_OR_FULL", gcode)
        self.assertIn("BED_MESH_CALIBRATE PROFILE=kamp", gcode)
        self.assertNotIn("bedmesh_before_print", gcode)
        self.assertNotIn("BED_MESH_PROFILE LOAD=default", gcode)
        self.assertNotIn("BED_MESH_CALIBRATE PROFILE=default", gcode)

        z_home_gcode = self._macro_gcode("_OPTIMIZED_G29_HOME_Z_OR_FULL")
        self.assertIn("_OPTIMIZED_HOME_Z_FROM_SAFE_POINT", z_home_gcode)
        self.assertNotIn("G28.6245197 Z", z_home_gcode)

    def test_safe_z_home_raw_path_is_not_reentrant(self):
        public_gcode = self._macro_gcode("_OPTIMIZED_HOME_Z_FROM_SAFE_POINT")
        self.assertIn("G28 Z", public_gcode)
        self.assertNotIn("G28.6245197 Z", public_gcode)
        self.assertNotIn("_OPTIMIZED_HOME_Z_FROM_SAFE_POINT_RAW", public_gcode)

        raw_gcode = self._macro_gcode("_OPTIMIZED_HOME_Z_FROM_SAFE_POINT_RAW")
        self.assertIn("printer.configfile.settings.printer.max_accel", raw_gcode)
        self.assertLess(raw_gcode.index("G28.6245197 Z"), raw_gcode.index("SET_VELOCITY_LIMIT ACCEL={default_accel}"))

        optimized_text = "\n".join(path.read_text(encoding="utf-8") for path in sorted(OPTIMIZED_MACRO_ROOT.glob("*.cfg")))
        self.assertEqual(optimized_text.count("G28.6245197 Z"), 1)

        homing_override = self._section_gcode(OPTIMIZED_MACRO_ROOT / "kinematics.cfg", "homing_override")
        self.assertEqual(homing_override.count("_OPTIMIZED_HOME_Z_FROM_SAFE_POINT_RAW"), 2)
        self.assertNotIn("\n      _OPTIMIZED_HOME_Z_FROM_SAFE_POINT\n", f"\n{homing_override}\n")

    def test_public_motion_helpers_restore_modal_state_and_acceleration(self):
        cut_gcode = self._macro_gcode("OPTIMIZED_CUT_FILAMENT")
        self.assertIn("saved_accel = printer.toolhead.max_accel|float", cut_gcode)
        self.assert_ordered(
            cut_gcode,
            "SAVE_GCODE_STATE NAME=optimized_cut_filament_state",
            "G90",
            "M204 S10000",
            "M83",
            "G1 E-4 F1000",
            "SET_VELOCITY_LIMIT ACCEL={saved_accel}",
            "RESTORE_GCODE_STATE NAME=optimized_cut_filament_state",
        )

        move_gcode = self._macro_gcode("OPTIMIZED_MOVE_TO_TRASH")
        self.assertIn("saved_accel = printer.toolhead.max_accel|float", move_gcode)
        self.assert_ordered(
            move_gcode,
            "SAVE_GCODE_STATE NAME=optimized_move_to_trash_state",
            "G90",
            "M204 S10000",
            "SET_VELOCITY_LIMIT ACCEL={saved_accel}",
            "RESTORE_GCODE_STATE NAME=optimized_move_to_trash_state",
        )

    def test_end_filament_prep_uses_explicit_relative_extrusion_for_e_only_moves(self):
        end_gcode = self._macro_gcode("OPTIMIZED_END_PRINT_FILAMENT_PREP")
        self.assert_ordered(
            end_gcode,
            "SAVE_GCODE_STATE NAME=optimized_end_print_filament_prep_state",
            "M83",
            "G1 E-3 F1800",
            "RESTORE_GCODE_STATE NAME=optimized_end_print_filament_prep_state",
        )

        unload_gcode = self._macro_gcode("OPTIMIZED_UNLOAD_FILAMENT")
        self.assertIn("saved_accel = printer.toolhead.max_accel|float", unload_gcode)
        self.assert_ordered(
            unload_gcode,
            "SAVE_GCODE_STATE NAME=optimized_unload_filament_state",
            "G90",
            "M83",
            "CUT_FILAMENT T={T}",
            "OPTIMIZED_MOVE_TO_TRASH",
            "UNLOAD_T{T}",
            "G1 E25 F300",
            "SET_VELOCITY_LIMIT ACCEL={saved_accel}",
            "RESTORE_GCODE_STATE NAME=optimized_unload_filament_state",
        )

    def test_no_box_start_path_wipes_and_scrapes_without_rear_purge(self):
        start_gcode = self._macro_gcode("OPTIMIZED_START_PRINT_FILAMENT_PREP")
        no_box_gcode = start_gcode[start_gcode.index("M118 Starting without QIDI Box filament prep") :]
        self.assertIn("OPTIMIZED_WIPE_AND_SCRAPE_NOZZLE TARGET={scrape_target}", no_box_gcode)
        self.assertNotIn("CLEAR_NOZZLE", no_box_gcode)

        wipe_gcode = self._macro_gcode("OPTIMIZED_WIPE_AND_SCRAPE_NOZZLE")
        self.assertNotIn("G1 E", wipe_gcode)
        self.assertIn("OPTIMIZED_WAIT_HOTEND S={scrape_target} STATUS=clear_nozzle", wipe_gcode)
        self.assertLess(wipe_gcode.index("_OPTIMIZED_HOME_Z_FROM_SAFE_POINT"), wipe_gcode.index("G1 Z-0.2 F480"))
        self.assertIn("G1 Z-0.2 F480", wipe_gcode)

    def assert_ordered(self, text: str, *needles: str):
        position = -1
        for needle in needles:
            next_position = text.index(needle, position + 1)
            self.assertGreater(next_position, position, needle)
            position = next_position

    def _macro_gcode(self, name: str) -> str:
        macro = self.macros[name]
        return "\n".join(line for _, line in macro.gcode_lines)

    def _section_gcode(self, path, name: str) -> str:
        lines = path.read_text(encoding="utf-8").splitlines()
        for section_name, header_index, end_index in iter_sections(lines):
            if section_name.lower() == name.lower():
                return "\n".join(line for _, line in extract_gcode_lines(lines, header_index + 1, end_index))
        self.fail(f"Missing section [{name}] in {path}")
