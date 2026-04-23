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
    "installer.tests.integration.test_install_flow.InstallFlowTests.test_missing_patch_target_fails_closed",
    "installer.tests.integration.test_uninstall_flow.UninstallFlowTests.test_happy_path_uninstall",
    "installer.tests.integration.test_uninstall_flow.UninstallFlowTests.test_uninstall_fails_closed_when_markers_exist_without_valid_state",
    "installer.tests.integration.test_dry_run_flow.DryRunFlowTests.test_install_dry_run_happy_path_leaves_runtime_tree_unchanged",
    "installer.tests.integration.test_dry_run_flow.DryRunFlowTests.test_uninstall_dry_run_happy_path_leaves_runtime_tree_unchanged",
    "installer.tests.unit.test_restore_helper.RestoreHelperTests.test_restore_helper_supports_direct_restore_stages_before_live_write_and_restores_full_snapshot_without_clearing_sentinel",
    "installer.tests.unit.test_cli.CliTests.test_clear_recovery_sentinel_requires_restored_backup_match",
    "installer.tests.unit.test_rollback.RollbackTests.test_rollback_failure_writes_recovery_sentinel",
)


def main() -> int:
    suite = unittest.defaultTestLoader.loadTestsFromNames(CORE_TESTS)
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


if __name__ == "__main__":
    raise SystemExit(main())
