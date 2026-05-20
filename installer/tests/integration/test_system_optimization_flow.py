from __future__ import annotations

import io
import json
import unittest
from pathlib import Path

from installer.runtime.cli import resolve_runtime_paths
from installer.runtime.manifest import load_manifest
from installer.runtime.models import SystemOptimizationCliOptions
from installer.runtime.reporter import PlainReporter
from installer.runtime.runner import run_install
from installer.runtime.system_optimizations import SYSTEM_ROOT_ENV
from installer.tests.helpers import REPO_ROOT, build_env, copy_base_runtime, moonraker_urlopen, temp_path


class SystemOptimizationFlowTests(unittest.TestCase):
    def test_install_dry_run_leaves_fake_system_tree_unchanged(self):
        printer_root = copy_base_runtime()
        system_root = _fake_system_root()
        before = _snapshot_tree(system_root)
        env = build_env(printer_root, moonraker_url="http://moonraker.invalid")
        env[SYSTEM_ROOT_ENV] = str(system_root)
        paths = resolve_runtime_paths(bundle_root=REPO_ROOT, environ=env)
        manifest = load_manifest(REPO_ROOT / "installer/package.yaml")
        stream = io.StringIO()

        result = run_install(
            paths,
            manifest,
            PlainReporter(stream),
            dry_run=True,
            urlopen=moonraker_urlopen(),
            environ=env,
            system_options=SystemOptimizationCliOptions(disable_ai_detection=True),
        )

        self.assertTrue(result.dry_run)
        self.assertEqual(_snapshot_tree(system_root), before)
        self.assertFalse((printer_root / manifest.state_file).exists())
        output = stream.getvalue()
        self.assertIn("System optimizations dry-run:", output)
        self.assertIn("would apply dns", output)
        self.assertIn("would apply service_algo_app.service", output)


def _fake_system_root() -> Path:
    system_root = temp_path("system-optimization-flow-")
    (system_root / "etc/resolvconf/resolv.conf.d").mkdir(parents=True)
    (system_root / "etc/resolv.conf").write_text("nameserver 114.114.114.114\n", encoding="utf-8")
    (system_root / "etc/resolvconf/resolv.conf.d/head").write_text("nameserver 8.8.8.8\n", encoding="utf-8")
    (system_root / "etc/resolvconf/resolv.conf.d/tail").write_text("", encoding="utf-8")
    (system_root / "etc/apt").mkdir(parents=True)
    (system_root / "etc/apt/sources.list").write_text("old apt\n", encoding="utf-8")
    gif = system_root / "home/qidi/QIDI_Client/access/account/process.gif"
    gif.parent.mkdir(parents=True)
    gif.write_bytes(b"old")
    (system_root / "systemd").mkdir()
    for service in ("xl2tpd", "bluetooth", "algo_app.service"):
        (system_root / "systemd" / f"{service}.json").write_text(
            json.dumps({"exists": True, "service": service, "enabled": "enabled", "active": "active"}, sort_keys=True),
            encoding="utf-8",
        )
    return system_root


def _snapshot_tree(root: Path) -> dict[str, tuple[str, str | bytes, int | None]]:
    snapshot: dict[str, tuple[str, str | bytes, int | None]] = {}
    for item in sorted(root.rglob("*")):
        relative = item.relative_to(root).as_posix()
        if item.is_symlink():
            snapshot[relative] = ("symlink", item.readlink().as_posix(), None)
        elif item.is_file():
            snapshot[relative] = ("file", item.read_bytes(), item.stat().st_mode & 0o777)
        elif item.is_dir():
            snapshot[relative] = ("dir", b"", item.stat().st_mode & 0o777)
    return snapshot
