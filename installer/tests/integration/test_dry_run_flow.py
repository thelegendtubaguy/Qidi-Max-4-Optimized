from __future__ import annotations

import io
import unittest

from installer.runtime.cli import resolve_runtime_paths
from installer.runtime.compatibility import load_supported_upgrade_sources
from installer.runtime.manifest import load_manifest
from installer.runtime.reporter import PlainReporter
from installer.runtime.runner import run_install
from installer.runtime.uninstall import run_uninstall
from installer.tests.helpers import REPO_ROOT, build_env, copy_base_runtime, moonraker_server, snapshot_tree


class DryRunFlowTests(unittest.TestCase):
    def setUp(self):
        self.manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        self.compatibility = load_supported_upgrade_sources(
            REPO_ROOT / "installer/supported_upgrade_sources.yaml"
        )

    def test_install_dry_run_happy_path_leaves_runtime_tree_unchanged(self):
        printer_root = copy_base_runtime()
        before = snapshot_tree(printer_root)
        stream = io.StringIO()
        with moonraker_server("standby") as url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=url),
            )
            result = run_install(paths, self.manifest, PlainReporter(stream), dry_run=True)

        self.assertEqual(snapshot_tree(printer_root), before)
        self.assertTrue(result.dry_run)
        self.assertIsNone(result.backup_zip_path)
        self.assertFalse((paths.config_root / "tltg_optimized_state.yaml").exists())
        self.assertFalse(list(printer_root.glob("before-optimize-*.zip")))
        output = stream.getvalue()
        self.assertIn("stage 1/5", output)
        self.assertIn("preflight counters:", output)
        self.assertIn("install counters:", output)
        self.assertIn("Dry-run summary:", output)
        self.assertIn("Dry-run complete. No changes made.", output)

    def test_uninstall_dry_run_happy_path_leaves_runtime_tree_unchanged(self):
        printer_root = self._install_first()
        before = snapshot_tree(printer_root)
        stream = io.StringIO()
        with moonraker_server("standby") as url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=url),
            )
            result = run_uninstall(
                paths,
                self.manifest,
                self.compatibility,
                PlainReporter(stream),
                dry_run=True,
            )

        self.assertEqual(snapshot_tree(printer_root), before)
        self.assertTrue(result.dry_run)
        self.assertIsNone(result.backup_zip_path)
        self.assertTrue((paths.config_root / "tltg_optimized_state.yaml").exists())
        self.assertTrue((paths.config_root / "tltg-optimized-macros").exists())
        self.assertFalse(list(printer_root.glob("before-uninstall-*.zip")))
        output = stream.getvalue()
        self.assertIn("stage 1/5", output)
        self.assertIn("uninstall counters:", output)
        self.assertIn("Dry-run summary:", output)
        self.assertIn("Dry-run complete. No changes made.", output)

    def _install_first(self):
        printer_root = copy_base_runtime()
        with moonraker_server("standby") as url:
            paths = resolve_runtime_paths(
                bundle_root=REPO_ROOT,
                environ=build_env(printer_root, moonraker_url=url),
            )
            run_install(paths, self.manifest, PlainReporter(io.StringIO()))
        return printer_root
