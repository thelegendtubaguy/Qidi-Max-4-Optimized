#!/usr/bin/env python3
from __future__ import annotations

import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

CORE_TESTS = (
    "installer.tests.integration.test_install_flow.InstallFlowTests.test_happy_path_install",
    "installer.tests.integration.test_install_flow.InstallFlowTests.test_install_patches_virtual_sdcard_on_error_with_inline_comment",
    "installer.tests.integration.test_install_flow.InstallFlowTests.test_box_extras_is_not_required_for_install",
    "installer.tests.integration.test_install_flow.InstallFlowTests.test_install_prompts_to_enable_detected_qidi_box",
    "installer.tests.integration.test_install_flow.InstallFlowTests.test_install_preserves_disabled_detected_qidi_box_when_declined",
    "installer.tests.integration.test_install_flow.InstallFlowTests.test_install_prompts_to_correct_value_t_slot_mismatches",
    "installer.tests.integration.test_install_flow.InstallFlowTests.test_install_preserves_value_t_slot_mismatches_when_declined",
    "installer.tests.integration.test_install_flow.InstallFlowTests.test_reinstall_preserves_section_restore_ledger",
    "installer.tests.integration.test_install_flow.InstallFlowTests.test_homing_override_whitespace_and_comment_changes_are_allowed",
    "installer.tests.integration.test_install_flow.InstallFlowTests.test_modified_homing_override_fails_closed",
    "installer.tests.integration.test_install_flow.InstallFlowTests.test_missing_patch_target_fails_closed",
    "installer.tests.integration.test_macro_call_graph.MacroCallGraphTests.test_current_config_tree_macro_call_graph_is_acyclic",
    "installer.tests.integration.test_macro_call_graph.MacroCallGraphTests.test_optimized_macro_tree_call_graph_is_acyclic",
    "installer.tests.integration.test_macro_call_graph.MacroCallGraphTests.test_installed_runtime_macro_call_graph_is_acyclic",
    "installer.tests.integration.test_gcode_path_contract.GcodePathContractTests.test_gcode_path_contracts_and_generated_views_are_current",
    "installer.tests.integration.test_optimized_macro_contract.OptimizedMacroContractTests.test_start_filament_prep_enables_bed_mesh_before_branching",
    "installer.tests.integration.test_optimized_macro_contract.OptimizedMacroContractTests.test_start_filament_prep_uses_purge_temp_for_box_load_and_rear_purge",
    "installer.tests.integration.test_optimized_macro_contract.OptimizedMacroContractTests.test_cancel_on_error_reenables_bed_mesh_without_moving",
    "installer.tests.integration.test_optimized_macro_contract.OptimizedMacroContractTests.test_optimized_g29_always_calibrates_kamp_mesh",
    "installer.tests.integration.test_optimized_macro_contract.OptimizedMacroContractTests.test_safe_z_home_raw_path_is_not_reentrant",
    "installer.tests.integration.test_optimized_macro_contract.OptimizedMacroContractTests.test_no_box_start_path_wipes_and_scrapes_without_rear_purge",
    "installer.tests.integration.test_uninstall_flow.UninstallFlowTests.test_happy_path_uninstall",
    "installer.tests.integration.test_uninstall_flow.UninstallFlowTests.test_uninstall_preserves_user_modified_homing_override",
    "installer.tests.integration.test_uninstall_flow.UninstallFlowTests.test_uninstall_fails_closed_when_markers_exist_without_valid_state",
    "installer.tests.integration.test_dry_run_flow.DryRunFlowTests.test_install_dry_run_happy_path_leaves_runtime_tree_unchanged",
    "installer.tests.integration.test_dry_run_flow.DryRunFlowTests.test_uninstall_dry_run_happy_path_leaves_runtime_tree_unchanged",
    "installer.tests.unit.test_restore_helper.RestoreHelperTests.test_restore_helper_supports_direct_restore_stages_before_live_write_and_restores_full_snapshot_without_clearing_sentinel",
    "installer.tests.unit.test_cli.CliTests.test_clear_recovery_sentinel_requires_restored_backup_match",
    "installer.tests.unit.test_cli.CliTests.test_keyboard_interrupt_returns_130_without_traceback",
    "installer.tests.unit.test_cli.CliTests.test_install_cancellation_returns_zero_without_writing",
    "installer.tests.unit.test_cli.CliTests.test_uninstall_cancellation_returns_zero_without_writing",
    "installer.tests.unit.test_cli.CliTests.test_install_demo_tui_returns_zero_without_writing",
    "installer.tests.unit.test_cli.CliTests.test_uninstall_demo_tui_returns_zero_without_writing",
    "installer.tests.unit.test_interaction.InteractionTests.test_maybe_restart_klipper_accepts_y_and_posts_restart_request",
    "installer.tests.unit.test_interaction.InteractionTests.test_maybe_restart_klipper_accepts_yes_and_posts_restart_request",
    "installer.tests.unit.test_auto_update.AutoUpdateTests.test_enable_auto_updates_installs_systemd_units_through_sudo",
    "installer.tests.unit.test_auto_update.AutoUpdateTests.test_enable_auto_updates_prompts_when_default_sudo_password_fails",
    "installer.tests.unit.test_rollback.RollbackTests.test_rollback_failure_writes_recovery_sentinel",
)


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromNames(CORE_TESTS)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
